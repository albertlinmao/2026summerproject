"""Tests for the no-Auth identity/link pass that turns printed names into people.

Asserted against a fake REST client rather than a database, because the point of
these is the decisions: what gets created, what gets reused, and what is refused.
Every one of those is a judgement that silently corrupts a swimmer's history if it
goes the wrong way, and none of them needs a live Supabase to pin down.
"""

import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from routine_identity import (  # noqa: E402
    IdentityReport, ensure_people_and_links, entries_of, find_person,
)
from ingest_common import IngestError  # noqa: E402


class FakeRest:
    """Enough of SupabaseRest to exercise the identity decisions."""

    def __init__(self, people=(), clubs=(), memberships=()):
        self.people = [dict(p) for p in people]
        self.clubs = [dict(c) for c in clubs]
        self.memberships = [dict(m) for m in memberships]
        self.inserted = []       # (table, rows)
        self.upserted = []       # (table, rows, on_conflict)
        self._next = 0

    def _new_id(self):
        self._next += 1
        return str(uuid.UUID(int=self._next))

    def select(self, table, params=None):
        if table == "as_person":
            return [{"id": p["id"], "given_name": p.get("given_name"),
                     "family_name": p.get("family_name"),
                     "middle_name": p.get("middle_name")} for p in self.people]
        if table == "as_club":
            return [{"id": c["id"], "code": c["code"]} for c in self.clubs]
        if table == "as_club_membership":
            return list(self.memberships)
        raise AssertionError(f"unexpected select on {table}")

    def insert(self, table, rows):
        rows = [dict(r) for r in rows]
        self.inserted.append((table, rows))
        if table == "as_person":
            # Mirror PostgREST returning the stored representation.
            for r in rows:
                self.people.append({"id": r["id"], "given_name": r.get("given_name"),
                                    "family_name": r.get("family_name"),
                                    "middle_name": r.get("middle_name")})
        elif table == "as_club_membership":
            self.memberships.extend(rows)
        return rows

    def upsert(self, table, rows, on_conflict=None):
        rows = [dict(r) for r in rows]
        self.upserted.append((table, rows, on_conflict))
        return rows

    def tables(self):
        return [t for t, _ in self.inserted] + [t for t, _, _ in self.upserted]

    def rows_for(self, table):
        out = [r for t, rows in self.inserted if t == table for r in rows]
        out += [r for t, rows, _ in self.upserted if t == table for r in rows]
        return out


def payload(*athletes):
    return {"athletes": list(athletes)}


def athlete(team_code, entries, name="Solo"):
    return {"team_code": team_code, "team_name": name,
            "team_athletes": [{"name": n} for n in entries]}


def inserted(count, prefix="r"):
    return [{"id": f"{prefix}{i}"} for i in range(count)]


class EntriesOfTests(unittest.TestCase):
    def test_accepts_a_list(self):
        self.assertEqual(entries_of({"team_athletes": [{"name": "A"}]}), [{"name": "A"}])

    def test_accepts_json_text(self):
        got = entries_of({"team_athletes": '[{"name": "A"}]'})
        self.assertEqual(got, [{"name": "A"}])

    def test_missing_or_broken_is_empty(self):
        self.assertEqual(entries_of({}), [])
        self.assertEqual(entries_of({"team_athletes": None}), [])
        self.assertEqual(entries_of({"team_athletes": "{not json"}), [])


class FindPersonTests(unittest.TestCase):
    def test_absent_is_not_an_error(self):
        """'Nobody matched' must be distinguishable from 'ambiguous'.

        Only the first justifies creating a person; the second does not.
        """
        self.assertEqual(find_person("SMITH Amy", {}, {}), (None, None))

    def test_single_match_resolves(self):
        pid = find_person("SMITH Amy", {"smith amy": "p1"}, {"smith amy": {"p1"}})[0]
        self.assertEqual(pid, "p1")

    def test_two_people_on_one_key_is_refused(self):
        pid, reason = find_person("SMITH Amy", {}, {"smith amy": {"p1", "p2"}})
        self.assertIsNone(pid)
        self.assertIn("2 existing people", reason)

    def test_suffix_does_not_reach_the_parent(self):
        """'LIN Isabella Jr' must never resolve to plain 'LIN Isabella'."""
        shared = {"lin isabella": {"parent"}}
        pid, reason = find_person("LIN Isabella Jr", {}, shared)
        self.assertIsNone(pid)
        self.assertIsNone(reason, "a Jr must read as a new person, not an error")
        self.assertEqual(shared, {"lin isabella": {"parent"}})


class NoAuthTests(unittest.TestCase):
    def test_creates_a_person_for_an_unknown_name(self):
        client = FakeRest(clubs=[{"id": "club-1", "code": "SAC"}])
        report = ensure_people_and_links(
            client, inserted(1), payload(athlete("SAC", ["NEWPERSON A"])))

        made = client.rows_for("as_person")
        self.assertEqual(len(made), 1)
        self.assertEqual(made[0]["family_name"], "NEWPERSON")
        self.assertEqual(report.people_created, ["NEWPERSON A"])

    def test_reuses_an_existing_person_instead_of_duplicating(self):
        client = FakeRest(
            people=[{"id": "p1", "given_name": "Isabella", "family_name": "LIN"}],
            clubs=[{"id": "club-1", "code": "SAC"}])
        report = ensure_people_and_links(
            client, inserted(1), payload(athlete("SAC", ["LIN Isabella"])))

        self.assertEqual(client.rows_for("as_person"), [], "created a duplicate person")
        self.assertEqual(report.people_reused, {"p1"})
        links = client.rows_for("as_result_person_link")
        self.assertEqual(links[0]["person_id"], "p1")

    def test_same_name_twice_in_one_pdf_creates_one_person(self):
        client = FakeRest(clubs=[{"id": "club-1", "code": "SAC"}])
        ensure_people_and_links(
            client, inserted(2),
            payload(athlete("SAC", ["NEWPERSON A"]), athlete("SAC", ["NEWPERSON A"])))

        self.assertEqual(len(client.rows_for("as_person")), 1)
        links = client.rows_for("as_result_person_link")
        self.assertEqual(len(links), 2, "both rows still need their own link")
        self.assertEqual(len({l["person_id"] for l in links}), 1,
                         "the two rows must point at the same person")


class SafeRefusalTests(unittest.TestCase):
    def test_ambiguous_name_is_reported_and_left_unlinked(self):
        client = FakeRest(
            people=[{"id": "p1", "given_name": "Isabella", "family_name": "LIN"},
                    {"id": "p2", "given_name": "Isabella", "family_name": "LIN"}],
            clubs=[{"id": "club-1", "code": "SAC"}])
        report = ensure_people_and_links(
            client, inserted(1), payload(athlete("SAC", ["LIN Isabella"])))

        self.assertEqual(client.rows_for("as_person"), [],
                         "an ambiguous name must not be used to create a third person")
        self.assertEqual(client.rows_for("as_result_person_link"), [])
        self.assertEqual(len(report.unresolved), 1)
        self.assertIn("left unlinked", report.unresolved[0])

    def test_missing_club_is_reported_and_no_club_is_invented(self):
        """as_club.id is the tenant id, so a missing club cannot be conjured up."""
        client = FakeRest()
        report = ensure_people_and_links(
            client, inserted(1), payload(athlete("NOPE", ["NEWPERSON A"])))

        self.assertEqual(report.clubs_missing, {"NOPE"})
        self.assertNotIn("as_club", client.tables(), "created a club")
        for row in client.rows_for("as_club_membership"):
            self.assertIsNotNone(row["club_id"])

    def test_row_count_mismatch_writes_no_links(self):
        client = FakeRest(clubs=[{"id": "club-1", "code": "SAC"}])
        report = ensure_people_and_links(
            client, inserted(1), payload(athlete("SAC", ["A One"]), athlete("SAC", ["B Two"])))

        self.assertEqual(client.upserted, [], "linked against the wrong rows")
        self.assertEqual(len(report.unresolved), 1)
        self.assertIn("no links written", report.unresolved[0])

    def test_id_count_mismatch_is_refused_outright(self):
        class ShortInsert(FakeRest):
            def insert(self, table, rows):
                rows = [dict(r) for r in rows]
                self.inserted.append((table, rows))
                return rows[:1]  # server acknowledged fewer rows than we sent

        short = ShortInsert(clubs=[{"id": "club-1", "code": "SAC"}])
        with self.assertRaises(IngestError):
            ensure_people_and_links(short, inserted(2), payload(
                athlete("SAC", ["NEWPERSON A"]), athlete("SAC", ["NEWPERSON B"])))
        self.assertEqual(short.upserted, [],
                         "linked people whose database ids were never confirmed")


class MembershipTests(unittest.TestCase):
    def test_membership_added_for_a_new_person(self):
        client = FakeRest(clubs=[{"id": "club-1", "code": "SAC"}])
        ensure_people_and_links(
            client, inserted(1), payload(athlete("SAC", ["NEWPERSON A"])))

        rows = client.rows_for("as_club_membership")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["role"], "swimmer")
        self.assertEqual(rows[0]["club_id"], "club-1")

    def test_existing_membership_is_not_duplicated(self):
        person = {"id": "p1", "given_name": "Isabella", "family_name": "LIN"}
        client = FakeRest(
            people=[person], clubs=[{"id": "club-1", "code": "SAC"}],
            memberships=[{"person_id": "p1", "club_id": "club-1", "role": "swimmer",
                          "status": "active"}])
        ensure_people_and_links(
            client, inserted(1), payload(athlete("SAC", ["LIN Isabella"])))

        self.assertEqual(client.rows_for("as_club_membership"), [])

    def test_inactive_membership_is_not_treated_as_existing(self):
        person = {"id": "p1", "given_name": "Isabella", "family_name": "LIN"}
        client = FakeRest(
            people=[person], clubs=[{"id": "club-1", "code": "SAC"}],
            memberships=[{"person_id": "p1", "club_id": "club-1", "role": "swimmer",
                          "status": "inactive"}])
        ensure_people_and_links(
            client, inserted(1), payload(athlete("SAC", ["LIN Isabella"])))

        self.assertEqual(len(client.rows_for("as_club_membership")), 1)


class LinkTests(unittest.TestCase):
    def test_link_carries_the_printed_name_and_the_result_id(self):
        client = FakeRest(
            people=[{"id": "p1", "given_name": "Isabella", "family_name": "LIN"}],
            clubs=[{"id": "club-1", "code": "SAC"}])
        ensure_people_and_links(
            client, inserted(1, prefix="res-"), payload(athlete("SAC", ["LIN Isabella"])))

        link = client.rows_for("as_result_person_link")[0]
        self.assertEqual(link["result_table"], "as_meet_routine_result")
        self.assertEqual(link["result_id"], "res-0")
        self.assertEqual(link["person_id"], "p1")
        self.assertEqual(link["athlete_name"], "LIN Isabella")

    def test_printed_name_is_not_normalised_away(self):
        """The PDF form is the only audit trail back to the PDF."""
        client = FakeRest(clubs=[{"id": "club-1", "code": "SAC"}])
        ensure_people_and_links(
            client, inserted(1), payload(athlete("SAC", ["YANOVSKIS Milana 12u"])))

        link = client.rows_for("as_result_person_link")[0]
        self.assertEqual(link["athlete_name"], "YANOVSKIS Milana 12u")

    def test_upsert_uses_the_one_conflict_that_makes_reimports_converge(self):
        client = FakeRest(clubs=[{"id": "club-1", "code": "SAC"}])
        ensure_people_and_links(
            client, inserted(1), payload(athlete("SAC", ["NEWPERSON A"])))

        table, rows, conflict = client.upserted[0]
        self.assertEqual(table, "as_result_person_link")
        self.assertEqual(conflict, "result_table,result_id,athlete_name")
        self.assertEqual(len(rows), 1)


class DryRunTests(unittest.TestCase):
    def test_dry_run_writes_nothing_but_still_counts(self):
        client = FakeRest(clubs=[{"id": "club-1", "code": "SAC"}])
        report = ensure_people_and_links(
            client, inserted(1), payload(athlete("SAC", ["NEWPERSON A"])), dry_run=True)

        self.assertEqual(client.inserted, [])
        self.assertEqual(client.upserted, [])
        self.assertEqual(report.people_created, ["NEWPERSON A"])
        self.assertEqual(report.links_written, 1)
        self.assertIn("nothing written", report.summary())

    def test_empty_athletes_touches_nothing(self):
        client = FakeRest()
        report = ensure_people_and_links(client, [], {"athletes": []})
        self.assertEqual(client.tables(), [])
        self.assertEqual(report.links_written, 0)


if __name__ == "__main__":
    unittest.main()