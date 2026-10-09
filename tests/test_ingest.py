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

    def test_no_scoring_line_is_silently_dropped(self):
        # This test exists because the old parser dropped 7 of the 8 ACRO lines on this
        # sheet and 9 AI lines on others, then reported nothing. It used to assert that a
        # "did not match" warning was raised. The parser now reads every line, so the
        # guarantee is stronger and is asserted directly: nothing unparsed, nothing that
        # fails to reconcile, and the element panel summing to the printed cumulative.
        from scripts.ingest_routines import parse_routine_pdf_text, extract_text_from_pdf
        pdf = (ROOT / "swim-meets/2026/20260321_Classic_Snohomish_WA"
                      "/Age Group 18-19 Acrobatic Routine Free Final.pdf")
        if not pdf.exists():
            self.skipTest("fixture PDF not present")
        parsed = parse_routine_pdf_text(extract_text_from_pdf(str(pdf)))
        self.assertEqual(parsed["stats"]["unparsed"], 0,
                         f"scoring rows were dropped: {parsed['errors']}")
        self.assertEqual(parsed["stats"]["unreconciled"], 0,
                         f"scoring rows did not reconcile: {parsed['errors']}")
        self.assertEqual(parsed["errors"], [])
        athlete = parsed["athletes"][0]
        elements = athlete["routine_scores"]["element_scores"]
        self.assertEqual(len(elements), 7, "all seven ACRO rows should be read")
        self.assertAlmostEqual(
            athlete["element_total"], 41.9663, places=3,
            msg="element panel must sum the printed line totals")
        self.assertAlmostEqual(
            athlete["artisticimpression_total"], 74.0, places=3)
        self.assertAlmostEqual(athlete["routine_score"], 99.9996, places=3)


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


class ColumnMapTests(unittest.TestCase):
    """The header decides the geometry. Judge count is per meet, not per parser."""

    # Verbatim from the sample PDFs. The spacing matters: the column map is built from
    # these character offsets, so the fixtures below pair real headers with real rows.
    HEADER5 = ("Code Rank Draw Team             Ref DD    J1   J2   J3   J4   J5"
               "     Total Pen.    Total        Routine ")
    HEADER3 = ("Code Rank Draw Team             Ref DD    J1   J2   J3"
               "     Total Pen.    Total        Routine ")
    ROW5 = ("          HYBRID (0.5)           7.000 6.50 6.50 6.50 6.25 5.50 22.4583"
            "        85.7500       161.0500")

    def test_five_judge_header_is_recognised(self):
        from scripts.ingest_routines import ColumnMap
        cmap = ColumnMap.from_header(self.HEADER5)
        self.assertIsNotNone(cmap)
        self.assertEqual(cmap.judge_labels(), ["J1", "J2", "J3", "J4", "J5"])

    def test_three_judge_header_is_recognised(self):
        # The Classic Snohomish sheets have no J4/J5. Requiring five made every one of
        # their scoring rows unreadable.
        from scripts.ingest_routines import ColumnMap
        cmap = ColumnMap.from_header(self.HEADER3)
        self.assertIsNotNone(cmap)
        self.assertEqual(cmap.judge_labels(), ["J1", "J2", "J3"])

    def test_duplicate_total_columns_are_numbered_left_to_right(self):
        # "Total" appears twice: the line total and the cumulative total. Collapsing them
        # into one column is what made the old parser lose the cumulative column.
        from scripts.ingest_routines import ColumnMap
        cmap = ColumnMap.from_header(self.HEADER5)
        occurrences = [(label, occ) for label, occ, _ in cmap.columns if label == "Total"]
        self.assertEqual([occ for _, occ in occurrences], [0, 1])
        cells = cmap.cells(self.ROW5)
        self.assertEqual(cells[("Total", 0)], [22.4583])
        self.assertEqual(cells[("Total", 1)], [85.75])
        self.assertEqual(cells[("Routine", 0)], [161.05])
        self.assertEqual(cells[("J5", 0)], [5.5])
        self.assertNotIn(("Ref", 0), cells, "Ref is blank on an ordinary row")

    def test_bracketed_factor_is_not_read_as_a_column_value(self):
        # "ACRO (0.6)" on a three-judge sheet puts 0.6 under Ref, which made every row
        # look like a deduction row (dd_nominal 0.6).
        from scripts.ingest_routines import _mask_bracketed
        line = "   ACRO (0.6)    2.375 8.00 6.00 7.50 10.2125"
        masked = _mask_bracketed(line)
        self.assertEqual(len(masked), len(line))
        self.assertNotIn("0.6", masked)
        self.assertIn("2.375", masked)


class TrimmedMeanTests(unittest.TestCase):
    def test_five_judges_drop_high_and_low(self):
        from scripts.ingest_routines import _trimmed_mean
        self.assertAlmostEqual(
            _trimmed_mean([6.50, 6.50, 6.50, 6.25, 5.50]), 6.416667, places=5)

    def test_three_judges_use_the_plain_mean(self):
        # Nothing to drop with three judges: (8.00 + 6.00 + 7.50)/3 = 7.166667, and
        # 7.166667 x 2.375 x 0.6 = 10.2125, the printed total.
        from scripts.ingest_routines import _trimmed_mean
        self.assertAlmostEqual(_trimmed_mean([8.00, 6.00, 7.50]), 7.166667, places=5)
        self.assertAlmostEqual(_trimmed_mean([8.00, 6.00, 7.50]) * 2.375 * 0.6,
                               10.2125, places=3)

    def test_fewer_than_three_judges_is_not_a_mean(self):
        from scripts.ingest_routines import _trimmed_mean
        self.assertIsNone(_trimmed_mean([6.0, 7.0]))


class StcRowTests(unittest.TestCase):
    """STC labels and fault counts vary by meet; all variants are in the corpus."""

    def test_three_fault_counts(self):
        from scripts.ingest_routines import parse_stc_row
        r = parse_stc_row("  STC Small (0.1)   21   44    7   2.4000   -5.0667")
        self.assertNotIn("error", r)
        self.assertEqual(r["fault_counts"], [21, 44, 7])
        self.assertAlmostEqual(r["computed_total"], 2.4, places=3)
        self.assertTrue(r["reconciles"])
        self.assertAlmostEqual(r["penalty"], -5.0667, places=3)

    def test_two_fault_counts_when_one_judge_has_none(self):
        from scripts.ingest_routines import parse_stc_row
        r = parse_stc_row("  STC Small (0.1)    9    18   1.3500   -14.3500")
        self.assertNotIn("error", r)
        self.assertEqual(r["fault_counts"], [9, 18])
        self.assertTrue(r["reconciles"])

    def test_major_without_median(self):
        from scripts.ingest_routines import parse_stc_row
        r = parse_stc_row("  STC Major (3.0)    0    0    0   0.0000")
        self.assertNotIn("error", r)
        self.assertEqual(r["element_type"], "STC Major")

    def test_trailing_dash_means_no_deduction(self):
        from scripts.ingest_routines import parse_stc_row
        r = parse_stc_row("  STC Small (0.1)    0    0    0   0.0000    -")
        self.assertNotIn("error", r)
        self.assertEqual(r["penalty"], 0.0)

    def test_stc_total_has_no_x3(self):
        # 2.4000 = mean(21,44,7) x 0.1. Artistic impression has the x3, STC does not.
        from scripts.ingest_routines import parse_stc_row
        r = parse_stc_row("  STC Obvious (0.5)   7    0    9   2.6667")
        self.assertAlmostEqual(r["computed_total"], 2.6667, places=3)


class ToleranceTests(unittest.TestCase):
    def test_rounding_noise_is_tolerated(self):
        from scripts.ingest_routines import _close
        # A printed difficulty of 10.02 is itself rounded, so the product lands 0.0067
        # off on 13.3667 (0.05%). That is rounding, not a different scoring rule.
        self.assertTrue(_close(13.36, 13.3667))

    def test_a_different_scoring_rule_is_not_tolerated(self):
        from scripts.ingest_routines import _close
        # The four-judge panels are off by 0.34%, an order of magnitude above the noise.
        self.assertFalse(_close(21.2188, 21.2917))

    def test_missing_printed_value_never_reconciles(self):
        from scripts.ingest_routines import _close
        self.assertFalse(_close(10.0, None))


class StcIsNotAnImportBlockerTests(unittest.TestCase):
    """A category total that will not reproduce is reported, but never blocks.

    A routine can carry more than one STC panel, so the category totals are not
    required to sum to the single printed deduction. Blocking on them stopped five
    sheets that reconcile perfectly on everything that matters.
    """

    PDF = (ROOT / "swim-meets/2026/20260321_Classic_Snohomish_WA"
                  "/Age Group 15-17 Women Duet Free Final.pdf")

    def test_category_mismatch_is_a_note(self):
        from scripts.ingest_routines import extract_text_from_pdf, parse_routine_pdf_text
        if not self.PDF.exists():
            self.skipTest("fixture PDF not present")
        parsed = parse_routine_pdf_text(extract_text_from_pdf(str(self.PDF)))
        self.assertEqual(parsed["errors"], [], "must not block the import")
        self.assertEqual(parsed["stats"]["unparsed"], 0)
        self.assertEqual(parsed["stats"]["unreconciled"], 0)
        self.assertGreaterEqual(parsed["stats"]["stc_notes"], 1)
        self.assertTrue(any("STC category total" in w for w in parsed["warnings"]))
        # The deduction is still stored, and the routine score still reconciles.
        athlete = parsed["athletes"][0]
        self.assertIsNotNone(
            athlete["routine_scores"].get("synchronization_deduction"))


class SwimmerLineTests(unittest.TestCase):
    """The Swimmer column carries names, meet furniture and other rows all together.

    Relaxing the gender prefix so gender-less sheets parse also made every scoring row
    match the name pattern, so these tests pin down what must NOT become an athlete.
    """

    def names(self, line):
        from scripts.ingest_routines import parse_swimmer_line
        return [e["name"] for e in parse_swimmer_line(line)]

    def test_gender_prefix_is_still_read(self):
        self.assertEqual(self.names("F CAI Jolene"), ["CAI Jolene"])

    def test_sheet_without_a_gender_column(self):
        # 'AG 12U Female Solo Details.pdf' prints no gender column at all.
        self.assertEqual(self.names("GIRE Ellie"), ["GIRE Ellie"])

    def test_reserve_marker_welded_to_the_name(self):
        from scripts.ingest_routines import parse_swimmer_line
        self.assertTrue(parse_swimmer_line("[R]LANNING Alexandra J")[0]["is_reserve"])
        self.assertEqual(self.names("M [R] WU Vivian"), ["WU Vivian"])

    def test_missing_gender_is_not_invented(self):
        from scripts.ingest_routines import parse_swimmer_line
        self.assertIsNone(parse_swimmer_line("GIRE Ellie")[0]["gender"])

    def test_duet_splits_on_a_padded_slash(self):
        self.assertEqual(
            self.names("LIN Isabella / SIZEMOVA Daria"),
            ["LIN Isabella", "SIZEMOVA Daria"],
        )

    def test_unpadded_slash_is_an_age_range_not_a_duet(self):
        # 'LIN - 18/19 Isabella' is one swimmer in one age group.
        self.assertEqual(self.names("F LIN - 18/19 Isabella"), ["LIN - 18/19 Isabella"])

    def test_age_group_is_stripped_from_the_person_but_kept_printed(self):
        from scripts.ingest_routines import parse_swimmer_line
        entry = parse_swimmer_line("F YANOVSKIS Milana 12u")[0]
        self.assertEqual(entry["name"], "YANOVSKIS Milana 12u")
        self.assertEqual(entry["family_name"], "YANOVSKIS")
        self.assertEqual(entry["given_name"], "Milana")

    def test_age_group_welded_onto_the_surname_with_a_hyphen(self):
        from scripts.ingest_routines import parse_swimmer_line
        entry = parse_swimmer_line("KIM-12U Olivia")[0]
        self.assertEqual(entry["family_name"], "KIM")
        self.assertEqual(entry["given_name"], "Olivia")

    def test_generational_suffix_is_kept_out_of_the_given_name(self):
        from scripts.ingest_routines import split_person_name
        parts = split_person_name("LIN Isabella Jr")
        self.assertEqual(parts["family_name"], "LIN")
        self.assertEqual(parts["given_name"], "Isabella")
        self.assertEqual(parts["suffix"], "JR")

    def test_suffix_never_resolves_to_the_same_person(self):
        # The corpus has same-club 'LIN Isabella' / 'Jr' / 'Sr'. If any lookup key were
        # shared, the Jr would resolve to the parent and two swimmers' scores would be
        # averaged into one person.
        from scripts.ingest_routines import person_match_keys
        base = set(person_match_keys("LIN Isabella"))
        jr = set(person_match_keys("LIN Isabella Jr"))
        sr = set(person_match_keys("LIN Isabella Sr"))
        self.assertFalse(base & jr, base & jr)
        self.assertFalse(base & sr, base & sr)
        self.assertFalse(jr & sr, jr & sr)

    def test_person_match_keys_are_normalised(self):
        from scripts.ingest_routines import person_match_keys
        self.assertIn("lin isabella", person_match_keys("  LIN   Isabella  "))
        self.assertIn("lin isabella", person_match_keys("Isabella LIN"))

    def test_middle_initial_is_not_mistaken_for_a_given_name(self):
        from scripts.ingest_routines import split_person_name
        parts = split_person_name("AKHROMTSEV Michaella J")
        self.assertEqual(parts["family_name"], "AKHROMTSEV")
        self.assertEqual(parts["given_name"], "Michaella")
        self.assertEqual(parts["middle_name"], "J")

    def test_two_word_surname(self):
        from scripts.ingest_routines import split_person_name
        parts = split_person_name("ALDANA MARTINEZ Valeria")
        self.assertEqual(parts["family_name"], "ALDANA MARTINEZ")
        self.assertEqual(parts["given_name"], "Valeria")

    def test_parenthetical_second_name_is_alt_not_part(self):
        from scripts.ingest_routines import split_person_name
        parts = split_person_name("HUANG Rosalyn (xiaoxin)")
        self.assertEqual(parts["family_name"], "HUANG")
        self.assertEqual(parts["given_name"], "Rosalyn")
        self.assertEqual(parts["alt_name"], "xiaoxin")

    # --- rows that must never be read as swimmers ---

    def test_scoring_row_is_not_a_swimmer(self):
        self.assertEqual(self.names("HYBRID (0.5)   7.000 6.50 6.50 6.50 6.25 5.50 22.4583"), [])

    def test_element_types_outside_the_hardcoded_list_are_still_rejected(self):
        # ELEMENT_TYPES is only ("ACRO", "HYBRID"), but the corpus also prints
        # TRE1a / ChoHY / ReqHY. Keying on the difficulty factor catches them all.
        for row in (
            "TRE4b (1.0)           2.600 5.25 4.75 6.00 5.00 13.4333",
            "ChoHY (0.2)           1.000 6.50 6.25 6.75 6.50  1.3000",
            "ReqHY (0.2)           11.15 5.75 6.50 6.50 6.00 13.9375",
        ):
            self.assertEqual(self.names(row), [], row)

    def test_meet_title_is_not_a_swimmer(self):
        self.assertEqual(
            self.names("2026 Charlotte Davis Region A Championship"), [])

    def test_venue_and_date_banner_is_not_a_swimmer(self):
        for row in (
            "Buffalo. NY 9 APR 2026",
            "Snohomish Aquatic Center Snohomish, WA 22 MAR 2026",
            "North Natomas Aquatic Center 2601 New Market Dr., "
            "Sacramento, CA 95835 7 MAR 2026 - 08:00",
        ):
            self.assertEqual(self.names(row), [], row)

    def test_judge_panel_is_not_a_swimmer(self):
        # Three real names and a digit, so the numeric guards do not catch it.
        self.assertEqual(
            self.names("J1  Leslie SIMS      Sharon COPP      Daniela GARMENDIA"), [])

    def test_status_row_is_not_a_swimmer(self):
        self.assertEqual(self.names("DSQ  23.  (10) OCC - OHIO CORALINAS SYNCHRO"), [])
        self.assertEqual(self.names("SCR       (11) SAZ - SCOTTSDALE SYNCHRO"), [])

    def test_team_row_is_not_a_swimmer(self):
        self.assertEqual(self.names("1.   (12) AST - ARMADA ARTISTIC SWIM TEAM"), [])

    def test_column_header_is_not_a_swimmer(self):
        self.assertEqual(
            self.names("Swimmer                            Age Group"), [])

    def test_footer_is_not_a_swimmer(self):
        self.assertEqual(self.names("Signature: ELLA HARRISON"), [])
        self.assertEqual(self.names("Report Created 3/8/2026 9:12 AM"), [])


class ClassificationTests(unittest.TestCase):
    def test_routine_sheet_is_recognised(self):
        from scripts.ingest_routines import classify_pdf
        text = "\n".join([
            "Code Rank Draw Team             Ref DD    J1   J2   J3   J4   J5"
            "     Total Pen.    Total        Routine",
            "     1.   (6)   AST - ARMADA ARTISTIC SWIM TEAM",
            "          HYBRID (0.5)   7.000 6.50 6.50 6.50 6.25 5.50 22.4583"
            "   85.7500   161.0500",
            "    Choreo and Music (1.4)   6.25 6.25 6.25 6.50 5.25 26.2500   75.3000",
        ])
        result = classify_pdf(text)
        self.assertTrue(result["is_routine"], result["reason"])
        self.assertEqual(result["signals"]["scoring header rows"], 1)

    def test_aggregate_sheet_is_not_routine(self):
        from scripts.ingest_routines import classify_pdf
        text = ("1.  (3)  AST - ARMADA ARTISTIC SWIM TEAM   161.0500  85.7500\n"
                "2.  (1)  SFM - SAN FRANCISCO MERIONETTES  157.2375  84.2375\n")
        result = classify_pdf(text)
        self.assertFalse(result["is_routine"])
        self.assertTrue(result["reason"], "a skip must say why")

    def test_empty_text_is_not_routine(self):
        from scripts.ingest_routines import classify_pdf
        self.assertFalse(classify_pdf("")["is_routine"])


class ThreeJudgeSheetTests(unittest.TestCase):
    """The Classic Snohomish sheets: three judges, one header, eight ACRO rows."""

    PDF = (ROOT / "swim-meets/2026/20260321_Classic_Snohomish_WA"
                  "/Age Group 18-19 Acrobatic Routine Free Final.pdf")

    def setUp(self):
        if not self.PDF.exists():
            self.skipTest("fixture PDF not present")

    def test_every_row_reconciles_and_nothing_is_dropped(self):
        from scripts.ingest_routines import extract_text_from_pdf, parse_routine_pdf_text
        parsed = parse_routine_pdf_text(extract_text_from_pdf(str(self.PDF)))
        self.assertEqual(parsed["stats"]["unparsed"], 0, parsed["errors"])
        self.assertEqual(parsed["stats"]["unreconciled"], 0, parsed["errors"])

    def test_panel_and_routine_totals(self):
        from scripts.ingest_routines import extract_text_from_pdf, parse_routine_pdf_text
        parsed = parse_routine_pdf_text(extract_text_from_pdf(str(self.PDF)))
        athlete = parsed["athletes"][0]
        self.assertAlmostEqual(athlete["element_total"], 41.9663, places=3)
        self.assertAlmostEqual(athlete["artisticimpression_total"], 74.0, places=3)
        # 41.9663 + 74.0000 - 15.9667 = 99.9996
        self.assertAlmostEqual(athlete["routine_score"], 99.9996, places=3)
        self.assertIsNone(athlete["synchronization_total"])


class RoutineWritePolicyTests(unittest.TestCase):
    """A disagreement between printed and recomputed totals must stop the write."""

    def _payload(self, errors):
        return {"athletes": [], "judges": [], "errors": errors, "warnings": [],
                "stats": {"scoring_rows": 1, "unparsed": 0, "unreconciled": 0},
                "event": {"event_name": "E", "event_date": "2026-01-01",
                          "host_city": "C"},
                "meet": {"name": "M", "meet_date": "2026-01-01"}}

    def test_mismatch_refuses_by_default(self):
        from scripts.ingest_routines import IngestError, insert_rows_to_supabase
        errors = [{"kind": "score does not reconcile", "line_no": 5,
                   "text": "HYBRID (0.5) 7.000 6.50 6.50 6.50 6.25 5.50 22.4583",
                   "columns": "", "reason": "printed 21.2917 but the judges give 21.2188"}]
        with patch("scripts.ingest_routines.check_results_present"), \
             patch("scripts.ingest_routines.get_supabase_config") as cfg:
            with self.assertRaises(IngestError) as ctx:
                insert_rows_to_supabase(self._payload(errors), "src.pdf", False)
        self.assertIn("do not reconcile", str(ctx.exception))
        cfg.assert_not_called()

    def test_allow_mismatch_gets_past_the_check(self):
        from scripts.ingest_routines import insert_rows_to_supabase
        errors = [{"kind": "score does not reconcile", "line_no": 5, "text": "x",
                   "columns": "", "reason": "because"}]
        with patch("scripts.ingest_routines.check_results_present"), \
             patch("scripts.ingest_routines.get_supabase_config",
                   side_effect=AssertionError("must not be reached")), \
             patch("scripts.ingest_routines.resolve_event"), \
             patch("scripts.ingest_routines.resolve_meet"), \
             patch("scripts.ingest_routines.prepare_meet_for_write",
                   return_value={"replaced": 0, "deleted": 0}), \
             patch("scripts.ingest_routines.SupabaseRest"):
            result = insert_rows_to_supabase(self._payload(errors), "src.pdf",
                                             True, allow_mismatch=True)
        self.assertIn("dry run", result)

    def test_dry_run_does_not_need_supabase_credentials(self):
        from scripts.ingest_routines import insert_rows_to_supabase
        with patch("scripts.ingest_routines.check_results_present"), \
             patch("scripts.ingest_routines.get_supabase_config",
                   side_effect=AssertionError("dry run must not read credentials")), \
             patch("scripts.ingest_routines.SupabaseRest"):
            result = insert_rows_to_supabase(self._payload([]), "src.pdf", True)
        self.assertIn("dry run", result)


if __name__ == "__main__":
    unittest.main()