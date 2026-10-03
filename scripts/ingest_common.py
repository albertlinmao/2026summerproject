#!/usr/bin/env python3
"""Shared write path for the PDF ingest scripts.

`ingest_figures.py` and `ingest_routines.py` differ only in how they parse a PDF.
Everything that touches the database lives here, because the bugs that mattered were
all in this layer and both scripts had their own copy of it:

  * a lookup that returned any non-200 fell through to "create a new row", so a
    transient PostgREST error silently duplicated an event or a meet;
  * the event was matched on name alone, ignoring the date the parser had already
    read, so two years of a recurring meet collapsed into one row;
  * nothing checked whether results for a PDF were already present, so re-running
    a PDF duplicated every result row - and `forbid_result_updates()` means a
    duplicate cannot be corrected with an UPDATE, only deleted;
  * a parse that produced zero results still reported success.

The parsers stay in their own files. This module never guesses a number: if the
parser could not read a score it writes NULL, not 0.
"""
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests

ROOT_DIR = Path(__file__).resolve().parents[1]

MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

DATE_RE = re.compile(r"(\d{1,2})\s+([A-Z]{3})\s+(\d{4})")


class IngestError(RuntimeError):
    """A condition that must stop this file, reported without a traceback."""


class AlreadyIngested(IngestError):
    pass


class AmbiguousEntity(IngestError):
    pass


def parse_event_date(raw: Any) -> Optional[date]:
    """Normalise '7 DEC 2025', '2025-12-07' or a date to a date, else None.

    The parser hands back the PDF's own '7 DEC 2025'. Comparing that against a
    stored date needs one representation, and guessing wrong here would merge two
    years of a recurring meet into a single row.
    """
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    text = str(raw).strip()
    match = DATE_RE.search(text.upper())
    if match:
        day, mon, year = match.groups()
        month = MONTHS.get(mon)
        if month:
            try:
                return date(int(year), month, int(day))
            except ValueError:
                return None
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def get_supabase_config() -> Dict[str, str]:
    from dotenv import load_dotenv

    load_dotenv(ROOT_DIR / ".env")
    load_dotenv(ROOT_DIR / "supabase" / ".env", override=False)

    raw_url = (os.getenv("SUPABASE_URL") or os.getenv("SUPABASE_PUBLIC_URL") or "").strip()
    if raw_url.startswith("postgres://") or raw_url.startswith("postgresql://"):
        raw_url = "http://localhost:8000"
    if raw_url.startswith("http://host.docker.internal"):
        raw_url = raw_url.replace("http://host.docker.internal", "http://localhost")
    if not raw_url:
        raw_url = "http://localhost:8000"

    key = (
        os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SERVICE_ROLE_KEY")
        or os.getenv("ANON_KEY")
        or ""
    )

    return {"url": raw_url, "key": key}


class SupabaseRest:
    """Thin PostgREST client that refuses to guess when a request fails.

    Every method raises on a non-2xx. The previous code did not, which is how a
    failed SELECT became an INSERT.
    """

    def __init__(self, url: str, key: str, timeout: int = 20) -> None:
        if not url or not key:
            raise IngestError("Supabase credentials not provided in environment")
        self.base = url.rstrip("/")
        self.timeout = timeout
        self._headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, table: str, params: Optional[Dict[str, Any]] = None,
                 json: Any = None, prefer: Optional[str] = None) -> Any:
        headers = dict(self._headers)
        if prefer:
            headers["Prefer"] = prefer
        try:
            response = requests.request(
                method, f"{self.base}/rest/v1/{table}", headers=headers,
                params=params, json=json, timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise IngestError(f"{method} {table} failed: {exc}") from exc

        if not (200 <= response.status_code < 300):
            raise IngestError(
                f"{method} {table} returned {response.status_code}: {response.text[:400]}"
            )
        if not response.text.strip():
            return []
        try:
            return response.json()
        except ValueError as exc:
            raise IngestError(f"{method} {table} returned invalid JSON: {response.text[:200]}") from exc

    def select(self, table: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows = self._request("GET", table, params=params)
        return rows if isinstance(rows, list) else [rows]

    def insert(self, table: str, rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not rows:
            return []
        return self._request("POST", table, json=list(rows), prefer="return=representation")

    def delete_by_ids(self, table: str, ids: Sequence[str]) -> int:
        if not ids:
            return 0
        joined = ",".join(ids)
        rows = self._request(
            "DELETE", table,
            params={"id": f"in.({joined})"}, prefer="return=representation",
        )
        return len(rows) if isinstance(rows, list) else 1


def resolve_event(client: SupabaseRest, event: Dict[str, Any]) -> Tuple[str, bool]:
    """Find the event by name AND date, or create it.

    Matching on the name alone was a real merge bug: the same meet recurs every
    year and every PDF already carries its date.
    """
    event_name = (event.get("event_name") or "").strip()
    if not event_name:
        raise IngestError("no event_name parsed from the PDF header")

    wanted = parse_event_date(event.get("event_date"))
    candidates = client.select(
        "as_event",
        {"event_name": f"eq.{event_name}", "select": "id,event_name,event_date"},
    )
    if candidates:
        if wanted is None:
            if len(candidates) == 1:
                return candidates[0]["id"], False
            raise AmbiguousEntity(
                f"event {event_name!r} has {len(candidates)} rows and the PDF had no readable "
                "date, so the right one cannot be chosen. Fix the date or clear the event first."
            )
        exact = [c for c in candidates if parse_event_date(c.get("event_date")) == wanted]
        if len(exact) > 1:
            raise AmbiguousEntity(
                f"event {event_name!r} on {wanted} has {len(exact)} rows; refusing to guess."
            )
        if exact:
            return exact[0]["id"], False

    created = client.insert("as_event", [event])
    if not created:
        raise IngestError("event insert returned no row")
    return created[0]["id"], True


def resolve_meet(client: SupabaseRest, meet: Dict[str, Any], event_id: str) -> Tuple[str, bool]:
    """Find the meet by name within the event, or create it.

    `ingest_figures.py` had no lookup here at all, so every run minted another
    as_meet row. The live database still carries the pair it produced: two meets
    named 'Age Group 12 and Under Figures', same event, same date, 11 results each.
    """
    meet_name = (meet.get("name") or "").strip()
    if not meet_name:
        raise IngestError("no meet name parsed from the PDF header")

    existing = client.select(
        "as_meet",
        {"name": f"eq.{meet_name}", "event_id": f"eq.{event_id}", "select": "id,name,meet_date"},
    )
    if existing:
        if len(existing) > 1:
            raise AmbiguousEntity(
                f"meet {meet_name!r} already has {len(existing)} rows in this event; "
                "refusing to add another. Clear the event first."
            )
        return existing[0]["id"], False

    payload = dict(meet)
    payload["event_id"] = event_id
    created = client.insert("as_meet", [payload])
    if not created:
        raise IngestError("meet insert returned no row")
    return created[0]["id"], True


def inspect_meet_results(client: SupabaseRest, table: str, meet_id: str,
                         source_file: str) -> Dict[str, List[Dict[str, Any]]]:
    """Split this meet's existing results into 'from this PDF' and 'from another'.

    Filtering by source_file in PostgREST means escaping a Windows path into a
    filter value, so the meet is fetched by id and split here instead.
    """
    rows = client.select(table, {"meet_id": f"eq.{meet_id}", "select": "id,source_file"})
    mine, other = [], []
    for row in rows:
        bucket = mine if (row.get("source_file") or "") == source_file else other
        bucket.append(row)
    return {"mine": mine, "other": other}


def prepare_meet_for_write(client: SupabaseRest, table: str, meet_id: str,
                           source_file: str, replace: bool) -> Optional[str]:
    """Refuse a re-ingest unless replacement was asked for. Returns a note, or None.

    A second insert of the same PDF doubles every result row. Because
    forbid_result_updates() blocks UPDATE on the result tables, the duplicate
    cannot be edited into place afterwards - it has to be deleted, so this is
    worth stopping before it happens rather than after.
    """
    split = inspect_meet_results(client, table, meet_id, source_file)
    mine, other = split["mine"], split["other"]

    if other:
        raise IngestError(
            f"this meet already holds {len(other)} result row(s) from a different PDF "
            f"({other[0].get('source_file')!r}), so meet {meet_id} is not this PDF's alone. "
            "Refusing to delete anything; clear the event and re-ingest instead."
        )
    if not mine:
        return None
    if not replace:
        raise AlreadyIngested(
            f"{len(mine)} result row(s) from this PDF are already in {table} for meet "
            f"{meet_id}. Nothing written. Pass --replace-source to delete those rows and "
            "re-import, or clear the event with sql/03_clear_event_data_by_eventid.sql."
        )

    ids = [r["id"] for r in mine]
    removed = client.delete_by_ids(table, ids)
    panels = client.delete_by_ids(
        "as_meet_judge_panel",
        [r["id"] for r in client.select(
            "as_meet_judge_panel", {"meet_id": f"eq.{meet_id}", "select": "id"})],
    )
    figures = client.delete_by_ids(
        "as_figure",
        [r["id"] for r in client.select(
            "as_figure", {"meet_id": f"eq.{meet_id}", "select": "id"})],
    )
    return (
        f"replaced {removed} result row(s) from this PDF, plus {panels} judge panel row(s) "
        f"and {figures} figure row(s) for the meet"
    )


def describe(payload: Dict[str, Any]) -> str:
    """The parse, as text. This is what --dry-run is for."""
    event = payload.get("event", {})
    meet = payload.get("meet", {})
    lines = [
        f"  event : {event.get('event_name') or '(none)'}",
        f"  date  : {event.get('event_date') or '(none)'}   city: {event.get('host_city') or '(none)'}",
        f"  meet  : {meet.get('name') or '(none)'}",
    ]
    if "figures" in payload:
        lines.append(f"  figures: {len(payload.get('figures') or [])}")
    lines.append(f"  judges : {len(payload.get('judges') or [])}")
    lines.append(f"  results: {len(payload.get('athletes') or [])}")
    for warning in payload.get("warnings") or []:
        lines.append(f"  WARNING: {warning}")
    return "\n".join(lines)


def check_results_present(payload: Dict[str, Any], allow_empty: bool) -> None:
    """An import that reads a meet and finds no results is a parse failure.

    The old code wrote the event, the meet and the figures, inserted an empty list
    of results, and printed a success line.
    """
    count = len(payload.get("athletes") or [])
    if count == 0 and not allow_empty:
        raise IngestError(
            "the parser found 0 results in this PDF, so only the event and meet would be "
            "written. That usually means the PDF layout drifted, not that the meet is "
            "empty. Re-run with --dry-run to see the parse, or pass --allow-empty if the "
            "meet really has no results."
        )


class RunReport:
    """Per-file outcomes and an exit code. A run that failed says so."""

    def __init__(self) -> None:
        self.rows: List[Tuple[str, str, str]] = []

    def add(self, path: str, status: str, detail: str = "") -> None:
        self.rows.append((path, status, detail))

    @property
    def failures(self) -> int:
        return sum(1 for _, status, _ in self.rows if status in ("FAILED", "REFUSED"))

    def render(self) -> str:
        if not self.rows:
            return "no files processed"
        lines = [""]
        for path, status, detail in self.rows:
            suffix = f" - {detail}" if detail else ""
            lines.append(f"[{status}] {path}{suffix}")
        ok = sum(1 for _, status, _ in self.rows if status == "OK")
        skipped = sum(1 for _, status, _ in self.rows if status == "SKIPPED")
        lines.append("")
        lines.append(
            f"{ok} ok, {skipped} skipped, {self.failures} failed or refused "
            f"({len(self.rows)} file(s))"
        )
        return "\n".join(lines)


def add_script_dir_to_path() -> None:
    """Make `from user_mgmt_sync import ...` work when imported as scripts.ingest_*.

    Running the file directly puts scripts/ on sys.path, so the bare import worked
    there and nowhere else - which is why tests/test_ingest_figures.py could not
    even import the module.
    """
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)