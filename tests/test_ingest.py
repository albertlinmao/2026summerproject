"""Tests for the shared ingest write path.

These use a fake PostgREST client: the bugs being guarded here are duplicate rows
and silent failures against the live database, so the tests must not need one.

Run: python -m unittest discover -s tests -v
"""
import os
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts import ingest_common as C  # noqa: E402
from scripts.ingest_common import (  # noqa: E402
    AlreadyIngested,
    AmbiguousEntity,
    IngestError,
    SupabaseRest,
    check_results_present,
    describe,
    parse_event_date,
    prepare_meet_for_write,
    resolve_event,
    resolve_meet,
)

RESULT_TABLE = "as_meet_figure_result"


class FakeRest:
    """Records writes and serves scripted reads."""

    def __init__(self, events=None, meets=None, results=None, figures=None, panels=None):
        self.events = events or []
        self.meets = meets or []
        self.results = results or []
        self.figures = figures or []
        self.panels = panels or []
        self.inserted = []
        self.deleted = []

    def select(self, table, params):
        pool = {
            "as_event": self.events,
            "as_meet": self.meets,
            RESULT_TABLE: self.results,
            "as_figure": self.figures,
            "as_meet_judge_panel": self.panels,
        }.get(table, [])
        rows = list(pool)
        for column, value in params.items():
            if column == "select" or not isinstance(value, str) or not value.startswith("eq."):
                continue
            rows = [r for r in rows if str(r.get(column)) == value[3:]]
        return rows

    def insert(self, table, rows):
        made = [{**r, "id": f"new-{table}-{i}"} for i, r in enumerate(rows)]
        self.inserted.append((table, made))
        return made

    def delete_by_ids(self, table, ids):
        attribute = {
            RESULT_TABLE: "results",
            "as_figure": "figures",
            "as_meet_judge_panel": "panels",
        }[table]
        pool = getattr(self, attribute)
        keep = [r for r in pool if r["id"] not in ids]
        removed = len(pool) - len(keep)
        setattr(self, attribute, keep)
        self.deleted.append((table, list(ids)))
        return removed


class ParseEventDateTests(unittest.TestCase):
    def test_reads_the_pdfs_own_format(self):
        self.assertEqual(parse_event_date("7 DEC 2025"), date(2025, 12, 7))

    def test_reads_iso_and_date_objects(self):
        self.assertEqual(parse_event_date("2025-12-07"), date(2025, 12, 7))
        self.assertEqual(parse_event_date(date(2025, 12, 7)), date(2025, 12, 7))

    def test_unreadable_is_none_rather_than_a_guess(self):
        for bad in (None, "", "sometime", "13 XYC 2025", "32 DEC 2025"):
            self.assertIsNone(parse_event_date(bad), bad)


class ResolveEventTests(unittest.TestCase):
    def test_matches_on_name_and_date(self):
        fake = FakeRest(events=[{"id": "e1", "event_name": "Dual", "event_date": date(2025, 12, 7)}])
        event_id, created = resolve_event(fake, {"event_name": "Dual", "event_date": "7 DEC 2025"})
        self.assertEqual(event_id, "e1")
        self.assertFalse(created)
        self.assertEqual(fake.inserted, [])

    def test_same_name_different_year_is_a_new_event(self):
        # The bug: the old lookup matched on name only, so every year of a
        # recurring meet collapsed onto one row.
        fake = FakeRest(events=[{"id": "e1", "event_name": "Dual", "event_date": date(2024, 12, 7)}])
        event_id, created = resolve_event(fake, {"event_name": "Dual", "event_date": "7 DEC 2025"})
        self.assertTrue(created)
        self.assertNotEqual(event_id, "e1")
        self.assertEqual(fake.inserted[0][0], "as_event")

    def test_refuses_when_the_date_cannot_choose(self):
        fake = FakeRest(events=[
            {"id": "e1", "event_name": "Dual", "event_date": date(2024, 12, 7)},
            {"id": "e2", "event_name": "Dual", "event_date": date(2025, 12, 7)},
        ])
        with self.assertRaises(AmbiguousEntity):
            resolve_event(fake, {"event_name": "Dual", "event_date": None})

    def test_refuses_an_ambiguous_exact_match(self):
        fake = FakeRest(events=[
            {"id": "e1", "event_name": "Dual", "event_date": date(2025, 12, 7)},
            {"id": "e2", "event_name": "Dual", "event_date": date(2025, 12, 7)},
        ])
        with self.assertRaises(AmbiguousEntity):
            resolve_event(fake, {"event_name": "Dual", "event_date": "7 DEC 2025"})

    def test_missing_event_name_stops_before_any_write(self):
        fake = FakeRest()
        with self.assertRaises(IngestError):
            resolve_event(fake, {"event_name": "", "event_date": "7 DEC 2025"})
        self.assertEqual(fake.inserted, [])


class ResolveMeetTests(unittest.TestCase):
    def test_reuses_an_existing_meet(self):
        # ingest_figures.py had no lookup at all, so every run minted another meet.
        fake = FakeRest(meets=[{"id": "m1", "name": "Age Group 12 and Under Figures", "event_id": "e1"}])
        meet_id, created = resolve_meet(fake, {"name": "Age Group 12 and Under Figures"}, "e1")
        self.assertEqual(meet_id, "m1")
        self.assertFalse(created)
        self.assertEqual(fake.inserted, [])

    def test_creates_when_absent(self):
        fake = FakeRest()
        meet_id, created = resolve_meet(fake, {"name": "New Meet"}, "e1")
        self.assertTrue(created)
        self.assertEqual(fake.inserted[0][0], "as_meet")
        self.assertEqual(fake.inserted[0][1][0]["event_id"], "e1")

    def test_does_not_reuse_another_events_meet(self):
        fake = FakeRest(meets=[{"id": "m9", "name": "Same Name", "event_id": "other"}])
        meet_id, created = resolve_meet(fake, {"name": "Same Name"}, "e1")
        self.assertTrue(created)
        self.assertNotEqual(meet_id, "m9")

    def test_refuses_a_duplicated_meet_instead_of_adding_a_third(self):
        fake = FakeRest(meets=[
            {"id": "m1", "name": "Dup", "event_id": "e1"},
            {"id": "m2", "name": "Dup", "event_id": "e1"},
        ])
        with self.assertRaises(AmbiguousEntity):
            resolve_meet(fake, {"name": "Dup"}, "e1")
        self.assertEqual(fake.inserted, [])


class PrepareMeetForWriteTests(unittest.TestCase):
    def _results(self, source):
        return [{"id": f"r{i}", "meet_id": "m1", "source_file": source} for i in range(3)]

    def test_first_import_writes_nothing_extra(self):
        fake = FakeRest()
        self.assertIsNone(prepare_meet_for_write(fake, RESULT_TABLE, "m1", "a.pdf", False))
        self.assertEqual(fake.deleted, [])

    def test_refuses_a_reingest_of_the_same_pdf(self):
        # Duplicates cannot be corrected afterwards: forbid_result_updates() blocks
        # the UPDATE that would fix them.
        fake = FakeRest(results=self._results("a.pdf"))
        with self.assertRaises(AlreadyIngested) as ctx:
            prepare_meet_for_write(fake, RESULT_TABLE, "m1", "a.pdf", False)
        self.assertIn("--replace-source", str(ctx.exception))
        self.assertEqual(fake.deleted, [], "nothing may be deleted on a refusal")

    def test_replace_deletes_only_this_pdf_and_the_meet_children(self):
        fake = FakeRest(
            results=self._results("a.pdf"),
            figures=[{"id": "f1", "meet_id": "m1"}],
            panels=[{"id": "p1", "meet_id": "m1"}],
        )
        note = prepare_meet_for_write(fake, RESULT_TABLE, "m1", "a.pdf", True)
        self.assertIn("replaced 3 result row(s)", note)
        self.assertEqual(fake.results, [])
        self.assertEqual(fake.figures, [])
        self.assertEqual(fake.panels, [])

    def test_refuses_when_another_pdf_owns_the_meet(self):
        # Two PDFs mapping to one meet: rebuilding would destroy the other file's rows.
        fake = FakeRest(results=self._results("other.pdf"))
        with self.assertRaises(IngestError) as ctx:
            prepare_meet_for_write(fake, RESULT_TABLE, "m1", "a.pdf", True)
        self.assertIn("different PDF", str(ctx.exception))
        self.assertEqual(fake.deleted, [])
        self.assertEqual(len(fake.results), 3)


class ClientFailureTests(unittest.TestCase):
    """A failed request must never be read as 'no such row, create one'."""

    def _client(self):
        return SupabaseRest("http://localhost:8000", "key")

    def test_non_200_on_select_raises(self):
        resp = unittest.mock.Mock(status_code=500, text="boom")
        with patch.object(C.requests, "request", return_value=resp):
            with self.assertRaises(IngestError) as ctx:
                self._client().select("as_event", {"select": "id"})
        self.assertIn("500", str(ctx.exception))

    def test_network_error_raises(self):
        import requests as real_requests
        with patch.object(C.requests, "request", side_effect=real_requests.ConnectionError("down")):
            with self.assertRaises(IngestError):
                self._client().select("as_event", {"select": "id"})

    def test_invalid_json_raises(self):
        resp = unittest.mock.Mock(status_code=200, text="<html>not json</html>")
        resp.json.side_effect = ValueError("no json")
        with patch.object(C.requests, "request", return_value=resp):
            with self.assertRaises(IngestError):
                self._client().select("as_event", {"select": "id"})

    def test_missing_credentials_raise_before_any_request(self):
        with self.assertRaises(IngestError):
            SupabaseRest("", "")


class PreflightTests(unittest.TestCase):
    def test_zero_results_is_refused(self):
        payload = {"event": {"event_name": "E"}, "meet": {"name": "M"}, "athletes": []}
        with self.assertRaises(IngestError) as ctx:
            check_results_present(payload, allow_empty=False)
        self.assertIn("--allow-empty", str(ctx.exception))

    def test_allow_empty_permits_it(self):
        payload = {"event": {"event_name": "E"}, "meet": {"name": "M"}, "athletes": []}
        check_results_present(payload, allow_empty=True)

    def test_describe_shows_the_parse_and_the_warnings(self):
        payload = {
            "event": {"event_name": "E", "event_date": "7 DEC 2025", "host_city": "Tukwila"},
            "meet": {"name": "M"},
            "athletes": [1, 2],
            "judges": [1],
            "warnings": ["something looks wrong"],
        }
        text = describe(payload)
        for fragment in ("E", "7 DEC 2025", "results: 2", "something looks wrong"):
            self.assertIn(fragment, text)


class RunReportTests(unittest.TestCase):
    def test_a_refusal_makes_the_run_fail(self):
        from scripts.ingest_common import RunReport
        report = RunReport()
        report.add("a.pdf", "OK")
        report.add("b.pdf", "REFUSED", "already ingested")
        self.assertEqual(report.failures, 1)
        self.assertIn("REFUSED", report.render())
        self.assertIn("1 ok", report.render())

    def test_all_ok_exits_zero(self):
        from scripts.ingest_common import RunReport
        report = RunReport()
        report.add("a.pdf", "OK")
        self.assertEqual(report.failures, 0)


class ParserHonestyTests(unittest.TestCase):
    """A score the parser could not read must not be stored as a real number."""

    def test_unreadable_scores_become_none_with_a_warning(self):
        from scripts.ingest_figures import parse_float
        warnings = []
        self.assertIsNone(parse_float("-.-", warnings))
        self.assertIsNone(parse_float("abc", warnings))
        self.assertIsNone(parse_float("", warnings))
        self.assertEqual(len(warnings), 3)
        self.assertEqual(parse_float("7.25", warnings), 7.25)

    def test_routine_sync_total_is_not_a_deduction(self):
        # The parser used to write the STC penalty into synchronization_total,
        # putting -15.9667 in a column that means a total.
        from scripts.ingest_routines import parse_routine_pdf_text
        pdf = (ROOT / "swim-meets/2026/20260321_Classic_Snohomish_WA"
                      "/Age Group 18-19 Acrobatic Routine Free Final.pdf")
        if not pdf.exists():
            self.skipTest("fixture PDF not present")
        from scripts.ingest_routines import extract_text_from_pdf
        parsed = parse_routine_pdf_text(extract_text_from_pdf(str(pdf)))
        self.assertTrue(parsed["athletes"], "fixture should yield results")
        for athlete in parsed["athletes"]:
            # Not promoted to a total...
            self.assertIsNone(athlete["synchronization_total"])
            # ...but not lost either: it stays with the STC row that produced it.
            penalties = [
                s.get("penalty") for s in athlete["routine_scores"]["synchronization_scores"]
            ]
            self.assertIn(-15.9667, penalties)

    def test_dropped_scoring_lines_are_reported(self):
        from scripts.ingest_routines import parse_routine_pdf_text, extract_text_from_pdf
        pdf = (ROOT / "swim-meets/2026/20260321_Classic_Snohomish_WA"
                      "/Age Group 18-19 Acrobatic Routine Free Final.pdf")
        if not pdf.exists():
            self.skipTest("fixture PDF not present")
        parsed = parse_routine_pdf_text(extract_text_from_pdf(str(pdf)))
        self.assertTrue(
            any("did not match" in w for w in parsed["warnings"]),
            "the dropped ACRO lines must be surfaced, not silently skipped",
        )


class ModuleImportTests(unittest.TestCase):
    def test_importable_as_a_package_and_as_a_file(self):
        # The bare `from user_mgmt_sync import ...` only resolved when the file was
        # run directly, so tests/test_ingest_figures.py could not import the module.
        import importlib
        for name in ("scripts.ingest_figures", "scripts.ingest_routines"):
            self.assertTrue(importlib.import_module(name))


class SupabaseConfigTests(unittest.TestCase):
    def test_local_stack_fallback(self):
        import tempfile
        # get_supabase_config now lives in ingest_common, so that is the ROOT_DIR
        # that has to be redirected - patching ingest_figures.ROOT_DIR no longer
        # has any effect, because the function no longer reads it.
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".env").write_text(
                "SUPABASE_URL=postgres://localhost:5432/postgres\n", encoding="utf-8"
            )
            (root / "supabase").mkdir(parents=True, exist_ok=True)
            (root / "supabase" / ".env").write_text(
                "SERVICE_ROLE_KEY=test-service-role-key\n", encoding="utf-8"
            )
            with patch.dict(os.environ, {}, clear=True):
                with patch.object(C, "ROOT_DIR", root):
                    config = C.get_supabase_config()
        self.assertEqual(config["url"], "http://localhost:8000")
        self.assertEqual(config["key"], "test-service-role-key")


if __name__ == "__main__":
    unittest.main()