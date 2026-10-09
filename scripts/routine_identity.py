"""Attach the printed names on routine result rows to real people in the database.

`ingest_routines.py` already writes `as_meet_routine_result`, including a
`team_athletes` jsonb array of the names exactly as the PDF printed them. That array is
lineage, not identity: nothing in it says who the swimmer is. The dashboard reads
identity through `as_result_person_link`, so without this step a routine result is
stored but unattributable and no swimmer ever accumulates a history.

This module does the identity half of the ingest and deliberately does not do the
account half. `synchronized_meet()` provisions tenants, Supabase Auth users and API
keys; this runs whether or not that is enabled (`--no-provision`), and creates no
login, no API key and no tenant. That separation is the point: results and their
attribution must not depend on account provisioning succeeding.

Two rules shape the design:

* `as_club.id` IS the tenant id, so a club cannot be conjured up here. A missing club is
  reported and its swimmers are left unlinked rather than attached to an invented club.
* A person is never merged on a guess. An ambiguous name is reported, not resolved,
  because averaging two swimmers' scores into one person is not recoverable later.
"""

import json
import uuid
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

try:
    from person_names import person_column_values, person_keys_from_columns, person_match_keys
except ImportError:  # imported as a module rather than run as a script
    from scripts.person_names import (
        person_column_values, person_keys_from_columns, person_match_keys,
    )

try:
    from ingest_common import IngestError
except ImportError:
    from scripts.ingest_common import IngestError

RESULT_TABLE = "as_meet_routine_result"
LINK_TABLE = "as_result_person_link"

# The one conflict target that makes a re-import converge instead of accumulating.
LINK_CONFLICT = "result_table,result_id,athlete_name"


class IdentityReport:
    """What the identity pass did, and what it refused to guess."""

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.people_created: List[str] = []
        self.people_reused: Set[str] = set()
        self.memberships_created = 0
        self.links_written = 0
        self.clubs_missing: Set[str] = set()
        self.unresolved: List[str] = []

    def summary(self) -> str:
        parts = [
            f"{len(self.people_created)} person(s) created",
            f"{len(self.people_reused)} reused",
            f"{self.memberships_created} swimmer membership(s) added",
            f"{self.links_written} result link(s) written",
        ]
        if self.clubs_missing:
            parts.append(f"{len(self.clubs_missing)} club(s) not in as_club")
        if self.unresolved:
            parts.append(f"{len(self.unresolved)} name(s) left unlinked")
        return (", ".join(parts) + ", nothing written"
                if self.dry_run else ", ".join(parts))

    def lines(self) -> List[str]:
        """Human-readable detail, one line per thing that needs a human."""
        out = [
            f"club '{code}' is not in as_club, so its swimmers were not linked "
            f"(as_club.id is the tenant id and is not created here)"
            for code in sorted(self.clubs_missing)
        ]
        out.extend(sorted(self.unresolved))
        return out


def entries_of(athlete: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The team_athletes array, whether it is still a list or was serialised for jsonb."""
    raw = athlete.get("team_athletes")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
    if not isinstance(raw, list):
        return []
    return [e for e in raw if isinstance(e, dict)]


def _load_people(client: Any) -> Tuple[Dict[str, str], Dict[str, Set[str]]]:
    """Index the existing people by lookup key.

    Returns (unambiguous key -> person_id, key -> every person_id holding it). A key
    held by more than one person is ambiguous and must not be used to link anything.
    """
    rows = client.select("as_person", {"select": "id,given_name,family_name,middle_name"})
    shared: Dict[str, Set[str]] = {}
    for row in rows or []:
        pid = row.get("id")
        if not pid:
            continue
        for key in person_keys_from_columns(
            row.get("family_name"), row.get("given_name"), row.get("middle_name")
        ):
            shared.setdefault(key, set()).add(pid)
    direct = {k: next(iter(v)) for k, v in shared.items() if len(v) == 1}
    return direct, shared


def _load_clubs(client: Any) -> Dict[str, str]:
    """Club code -> club id. as_club.id is the tenant id, so nothing is created here."""
    rows = client.select("as_club", {"select": "id,code"})
    out: Dict[str, str] = {}
    for row in rows or []:
        code = (row.get("code") or "").strip().upper()
        pid = row.get("id")
        if code and pid:
            out.setdefault(code, pid)
    return out


def _load_memberships(client: Any) -> Set[Tuple[str, str]]:
    """(person_id, club_id) pairs that already hold a live swimmer membership."""
    rows = client.select(
        "as_club_membership",
        {"select": "person_id,club_id,role,status", "role": "eq.swimmer"},
    )
    return {
        (r.get("person_id"), r.get("club_id"))
        for r in rows or []
        if r.get("status") in ("invited", "active")
    }


def find_person(printed: str, direct: Dict[str, str],
                shared: Dict[str, Set[str]]) -> Tuple[Optional[str], Optional[str]]:
    """Resolve a printed name to a person id.

    Returns (person_id, reason). Exactly one is set: a person_id when the name resolved,
    or a reason describing why it could not be decided. 'not found' and 'ambiguous' are
    kept apart because only the first one justifies creating a person.
    """
    keys = person_match_keys(printed)
    if not keys:
        return None, "produced no usable name keys"
    for key in keys:
        hits = shared.get(key) or set()
        if len(hits) > 1:
            listed = ", ".join(sorted(hits)[:3])
            return None, f"matches {len(hits)} existing people on key '{key}' ({listed})"
        if len(hits) == 1:
            return next(iter(hits)), None
    return None, None


def ensure_people_and_links(client: Any, inserted: Sequence[Dict[str, Any]],
                            payload: Dict[str, Any],
                            dry_run: bool = False) -> IdentityReport:
    """Create missing people and attach every printed name to its result row.

    `inserted` is what `client.insert(RESULT_TABLE, ...)` returned: the same rows, in
    the same order, carrying the database ids that `as_result_person_link.result_id`
    needs.
    """
    report = IdentityReport(dry_run=dry_run)
    athletes = payload.get("athletes") or []
    if not athletes:
        return report

    if len(inserted) != len(athletes):
        # Without ids the links cannot be written, and inventing one would attach a
        # result to whatever row happened to occupy that slot.
        report.unresolved.append(
            f"expected {len(athletes)} inserted result row(s) but got {len(inserted)}; "
            f"no links written"
        )
        return report

    direct, shared = _load_people(client)
    clubs = _load_clubs(client)
    memberships = _load_memberships(client)

    # printed name -> the row that will be inserted, so a name repeated across blocks
    # becomes one person rather than two.
    pending_people: Dict[str, Dict[str, Any]] = {}
    pending_keys: Dict[str, List[str]] = {}
    new_memberships: Dict[Tuple[str, str], Dict[str, Any]] = {}
    links: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for athlete, row in zip(athletes, inserted):
        result_id = row.get("id")
        if not result_id:
            report.unresolved.append("an inserted result row came back without an id")
            continue
        club_code = (athlete.get("team_code") or "").strip().upper()
        club_id = clubs.get(club_code) if club_code else None
        if club_code and not club_id:
            report.clubs_missing.add(club_code)

        for entry in entries_of(athlete):
            printed = (entry.get("name") or "").strip()
            if not printed:
                continue

            person_id, reason = find_person(printed, direct, shared)
            if reason:
                report.unresolved.append(f"'{printed}' {reason}; left unlinked")
                continue
            if person_id is None:
                person_id = _stage_person(
                    printed, pending_people, pending_keys, direct, shared, report)
            else:
                report.people_reused.add(person_id)

            if person_id and club_id and (person_id, club_id) not in memberships:
                new_memberships.setdefault((person_id, club_id), {
                    "id": str(uuid.uuid4()),
                    "person_id": person_id,
                    "club_id": club_id,
                    "role": "swimmer",
                    "status": "active",
                })

            if person_id:
                links[(result_id, printed)] = {
                    "result_table": RESULT_TABLE,
                    "result_id": result_id,
                    "person_id": person_id,
                    # The printed form, verbatim: this is the PDF's lineage and the only
                    # audit trail back to it. Never the normalised person columns.
                    "athlete_name": printed,
                    "confidence": 1.0,
                }

    report.people_created = list(pending_people)
    report.memberships_created = len(new_memberships)
    report.links_written = len(links)

    if dry_run:
        return report

    if pending_people:
        made = client.insert("as_person", list(pending_people.values()))
        got = made if isinstance(made, list) else []
        if len(got) != len(pending_people):
            raise IngestError(
                f"as_person insert returned {len(got)} row(s) for "
                f"{len(pending_people)} people; refusing to link against unknown ids"
            )
        # The ids were generated here and sent with the rows, so the staged ids are
        # already the real ones; re-index the keys against them for the write below.
        for printed, keys in pending_keys.items():
            pid = pending_people[printed]["id"]
            for key in keys:
                shared.setdefault(key, set()).add(pid)

    if new_memberships:
        client.insert("as_club_membership", list(new_memberships.values()))

    if links:
        client.upsert(LINK_TABLE, list(links.values()), on_conflict=LINK_CONFLICT)

    return report


def _stage_person(printed: str, pending: Dict[str, Dict[str, Any]],
                  pending_keys: Dict[str, List[str]], direct: Dict[str, str],
                  shared: Dict[str, Set[str]], report: IdentityReport) -> str:
    """Queue one as_person row for a printed name that matched nobody."""
    existing = pending.get(printed)
    if existing:
        return existing["id"]
    columns = person_column_values(printed)
    pid = str(uuid.uuid4())
    pending[printed] = {
        "id": pid,
        "given_name": columns["given_name"],
        "family_name": columns["family_name"],
        "middle_name": columns["middle_name"],
    }
    keys = person_match_keys(printed)
    pending_keys[printed] = keys
    # Make the staged person findable for the rest of this run, so the same name in a
    # second block resolves instead of creating a twin. It counts as neither created
    # twice nor reused: it is the one person this run is about to create.
    for key in keys:
        shared.setdefault(key, set()).add(pid)
        direct.setdefault(key, pid)
    report.people_reused.discard(pid)
    return pid


from ingest_common import IngestError  # noqa: E402  (cycle-free, kept last)