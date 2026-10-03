"""AnalyticsService: centralized analytics engine for dashboard widgets.

Implements the layered analytics architecture (Constitution Principle 14):
queries run against aggregated data (materialized view / result tables),
never raw per-request computation on unaggregated sources where avoidable.

Identity follows ``specs/001-analytics-dashboard/identity-contract.md``: analytics
are keyed on ``person_id``, not on a login. A swimmer with no account still
appears, and one person keeps a single identity across a club transfer. Club
scope comes from ``as_club_membership`` rather than from a denormalized
``club_id`` on the person.

Name matching against the immutable result tables is a deliberate fallback, not
the primary path: the authoritative mapping is ``as_result_person_link``.
"""

import json
import logging
from typing import Any, Optional

from src.core.database import get_supabase
from src.models.athlete_ref import AthleteRef

logger = logging.getLogger(__name__)

# Baseline used when an athlete has too few records for statistics
BASELINE_SCORE = 70.0
MIN_RECORDS_FOR_STATS = 5

#: Statuses that grant access. Mirrors ``ACTIVE_MEMBERSHIP_STATUSES`` in core.auth.
ACTIVE_MEMBERSHIP_STATUSES = ("invited", "active")


class AnalyticsService:
    """Score distributions, ranking histories, and figure radar chart data."""

    def __init__(self, client=None):
        self._client = client

    @property
    def client(self):
        if self._client is None:
            self._client = get_supabase()
        return self._client

    # ------------------------------------------------------------------
    # Person resolution
    #
    # as_athlete / as_coach are views over as_person joined to an active
    # membership, so they carry person_id and name but no club_id. Scoping to a
    # club is a separate question, answered by as_club_membership.
    # ------------------------------------------------------------------

    def get_club_swimmers(self, club_id: str) -> list[AthleteRef]:
        """People holding an active ``swimmer`` membership in this club."""
        response = (
            self.client.table("as_club_membership")
            .select("person_id")
            .eq("club_id", club_id)
            .eq("role", "swimmer")
            .in_("status", list(ACTIVE_MEMBERSHIP_STATUSES))
            .execute()
        )
        person_ids = [r["person_id"] for r in (response.data or []) if r.get("person_id")]
        if not person_ids:
            return []

        people = (
            self.client.table("as_athlete")
            .select("person_id, name, given_name, family_name, birth_date")
            .in_("person_id", person_ids)
            .execute()
        )
        return [
            AthleteRef(
                person_id=r["person_id"],
                name=r.get("name") or "",
                given_name=r.get("given_name"),
                family_name=r.get("family_name"),
                birth_date=r.get("birth_date"),
            )
            for r in (people.data or [])
            if r.get("person_id")
        ]

    def get_person(self, person_id: str, club_id: Optional[str] = None) -> Optional[AthleteRef]:
        """Fetch one swimmer.

        ``club_id`` is optional and, when given, additionally requires the person to
        hold an active ``swimmer`` membership there. It cannot be applied as a
        column filter because the view spans clubs by design.
        """
        if club_id and not self.is_club_swimmer(person_id, club_id):
            return None

        response = (
            self.client.table("as_athlete")
            .select("person_id, name, given_name, family_name, birth_date")
            .eq("person_id", person_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return None
        r = rows[0]
        return AthleteRef(
            person_id=r["person_id"],
            name=r.get("name") or "",
            given_name=r.get("given_name"),
            family_name=r.get("family_name"),
            birth_date=r.get("birth_date"),
        )

    def is_club_swimmer(self, person_id: str, club_id: str) -> bool:
        response = (
            self.client.table("as_club_membership")
            .select("id")
            .eq("person_id", person_id)
            .eq("club_id", club_id)
            .eq("role", "swimmer")
            .in_("status", list(ACTIVE_MEMBERSHIP_STATUSES))
            .limit(1)
            .execute()
        )
        return bool(response.data)

    def resolve_result_person_ids(self, result_table: str, result_ids: list[str]) -> dict[str, str]:
        """Map result rows to people via ``as_result_person_link``.

        Returns ``{"<athlete_name lowercased>": person_id}``. This is the
        authoritative resolution; :meth:`get_team_overview` falls back to matching
        printed names only when a row has no link.
        """
        if not result_ids:
            return {}
        response = (
            self.client.table("as_result_person_link")
            .select("result_id, person_id, athlete_name")
            .eq("result_table", result_table)
            .in_("result_id", result_ids)
            .execute()
        )
        return {
            (r.get("athlete_name") or "").strip().lower(): r["person_id"]
            for r in (response.data or [])
            if r.get("person_id")
        }

    # ------------------------------------------------------------------
    # Raw result access (immutable competition records)
    # ------------------------------------------------------------------

    def _fetch_figure_results(self, team_codes: list[str]) -> list[dict[str, Any]]:
        if not team_codes:
            return []
        response = (
            self.client.table("as_meet_figure_result")
            .select("*")
            .in_("team_code", team_codes)
            .order("created_at", desc=False)
            .execute()
        )
        return response.data or []

    def _fetch_routine_results(self, team_codes: list[str]) -> list[dict[str, Any]]:
        if not team_codes:
            return []
        response = (
            self.client.table("as_meet_routine_result")
            .select("*")
            .in_("team_code", team_codes)
            .order("created_at", desc=False)
            .execute()
        )
        return response.data or []

    def _club_team_codes(self, club_id: str) -> list[str]:
        """Resolve distinct team codes recorded for the club's results."""
        response = (
            self.client.table("as_meet_figure_result")
            .select("team_code")
            .not_.is_("team_code", "null")
            .limit(1000)
            .execute()
        )
        codes = sorted({(r.get("team_code") or "").strip() for r in response.data or []} - {""})
        return codes

    # ------------------------------------------------------------------
    # Team overview (US1)
    # ------------------------------------------------------------------

    def get_team_overview(self, club_id: str) -> dict[str, Any]:
        """Team swimmers with average figure/routine scores, most improved, at-risk."""
        swimmers = self.get_club_swimmers(club_id)
        team_codes = self._club_team_codes(club_id)
        figure_rows = self._fetch_figure_results(team_codes)
        routine_rows = self._fetch_routine_results(team_codes)

        by_name = {s.name.strip().lower(): s for s in swimmers}
        person_id_of_name = {key: swimmer.person_id for key, swimmer in by_name.items()}

        figure_links = self.resolve_result_person_ids(
            "as_meet_figure_result", [r["id"] for r in figure_rows if r.get("id")]
        )
        routine_links = self.resolve_result_person_ids(
            "as_meet_routine_result", [r["id"] for r in routine_rows if r.get("id")]
        )

        def _bucket(row_key: str, resolved: dict[str, str]) -> Optional[str]:
            """Person id for a printed name: explicit link first, name match second.

            Falling back to the name keeps pre-migration data visible; once a row has
            a link the link wins, so a corrected identity takes effect immediately.
            """
            return resolved.get(row_key) or person_id_of_name.get(row_key)

        # Two buckets per person so the averages stay type-specific.
        figure_scores: dict[str, list[float]] = {}
        routine_scores: dict[str, list[float]] = {}

        for row in figure_rows:
            score = row.get("figure_score")
            if score is None:
                score = row.get("total_score")
            if score is None:
                continue
            key = (row.get("athlete_name") or "").strip().lower()
            bucket = _bucket(key, figure_links)
            if bucket:
                figure_scores.setdefault(bucket, []).append(float(score))

        for row in routine_rows:
            athletes_in_routine = row.get("team_athletes") or []
            if isinstance(athletes_in_routine, str):
                try:
                    athletes_in_routine = json.loads(athletes_in_routine)
                except json.JSONDecodeError:
                    athletes_in_routine = []

            score = row.get("routine_score")
            if score is None:
                continue
            for entry in athletes_in_routine:
                name = entry if isinstance(entry, str) else str((entry or {}).get("name", ""))
                key = name.strip().lower()
                bucket = _bucket(key, routine_links)
                if bucket:
                    routine_scores.setdefault(bucket, []).append(float(score))

        swimmer_stats = []
        for swimmer in swimmers:
            figs = figure_scores.get(swimmer.person_id, [])
            ruts = routine_scores.get(swimmer.person_id, [])
            trend = self._trend(figs + ruts)
            swimmer_stats.append(
                {
                    "person_id": swimmer.person_id,
                    "name": swimmer.name,
                    "avg_figure_score": self._avg(figs),
                    "avg_routine_score": self._avg(ruts),
                    "improvement_trend": trend,
                    "at_risk": trend is not None and trend < 0,
                    "records_count": len(figs) + len(ruts),
                }
            )

        scored = [s for s in swimmer_stats if s["improvement_trend"] is not None]
        most_improved = max(scored, key=lambda s: s["improvement_trend"], default=None)
        at_risk = [s for s in swimmer_stats if s["at_risk"]]

        return {
            "club_id": club_id,
            "athletes": swimmer_stats,
            "most_improved": most_improved,
            "at_risk": at_risk,
        }

    def get_figure_weakness_heatmap(self, club_id: str) -> dict[str, Any]:
        """Per-swimmer x per-figure average scores for the coach's club."""
        swimmers = self.get_club_swimmers(club_id)
        by_name = {s.name.strip().lower(): s for s in swimmers}
        team_codes = self._club_team_codes(club_id)
        figure_rows = self._fetch_figure_results(team_codes)
        links = self.resolve_result_person_ids(
            "as_meet_figure_result", [r["id"] for r in figure_rows if r.get("id")]
        )

        matrix: dict[str, dict[str, list[float]]] = {}
        for row in figure_rows:
            key = (row.get("athlete_name") or "").strip().lower()
            person_id = links.get(key) or (by_name[key].person_id if key in by_name else None)
            if not person_id:
                continue
            for figure_code, value in (row.get("figure_scores") or {}).items():
                try:
                    matrix.setdefault(person_id, {}).setdefault(str(figure_code), []).append(
                        float(value)
                    )
                except (TypeError, ValueError):
                    continue

        all_figures = sorted({f for per_person in matrix.values() for f in per_person})
        cells = []
        for swimmer in swimmers:
            per_figure = matrix.get(swimmer.person_id, {})
            weaknesses = {
                code: round(sum(vals) / len(vals), 2)
                for code, vals in sorted(per_figure.items())
                if vals
            }
            weakest = min(weaknesses, key=weaknesses.get) if weaknesses else None
            cells.append(
                {
                    "person_id": swimmer.person_id,
                    "name": swimmer.name,
                    "weaknesses": weaknesses,
                    "weakest_figure": weakest,
                }
            )

        return {"club_id": club_id, "figures": all_figures, "athletes": cells}

    def get_person_trends(self, person_id: str, club_id: Optional[str] = None) -> dict[str, Any]:
        """Figure/routine trends over time plus radar chart data for one swimmer."""
        swimmer = self.get_person(person_id, club_id)
        if not swimmer:
            return {}

        team_codes = self._club_team_codes(club_id) if club_id else []
        figure_rows = self._fetch_figure_results(team_codes)
        links = self.resolve_result_person_ids(
            "as_meet_figure_result", [r["id"] for r in figure_rows if r.get("id")]
        )

        key = swimmer.name.strip().lower()
        history: list[dict[str, Any]] = []
        figure_totals: dict[str, list[float]] = {}
        for row in figure_rows:
            row_key = (row.get("athlete_name") or "").strip().lower()
            row_person = links.get(row_key) or (person_id if row_key == key else None)
            if row_person != person_id:
                continue
            score = row.get("figure_score")
            if score is not None:
                history.append(
                    {
                        "meet_id": row.get("meet_id"),
                        "date": row.get("created_at"),
                        "figure_score": float(score),
                    }
                )
            for figure_code, value in (row.get("figure_scores") or {}).items():
                try:
                    figure_totals.setdefault(str(figure_code), []).append(float(value))
                except (TypeError, ValueError):
                    continue

        radar = [
            {
                "figure": code,
                "average": round(sum(values) / len(values), 2),
                "samples": len(values),
            }
            for code, values in sorted(figure_totals.items())
        ]

        all_scores = [h["figure_score"] for h in history]
        return {
            "person_id": swimmer.person_id,
            "name": swimmer.name,
            "history": history,
            "radar": radar,
            "distribution": {
                "mean": round(sum(all_scores) / len(all_scores), 2) if all_scores else None,
                "min": min(all_scores) if all_scores else None,
                "max": max(all_scores) if all_scores else None,
                "count": len(all_scores),
            },
        }

    @staticmethod
    def _avg(values: list[float]) -> Optional[float]:
        return round(sum(values) / len(values), 2) if values else None

    @staticmethod
    def _trend(scores: list[float]) -> Optional[float]:
        """Simple improvement indicator: last-half mean minus first-half mean."""
        if len(scores) < 2:
            return None
        half = len(scores) // 2
        first = scores[:half]
        second = scores[half:]
        if not first or not second:
            return None
        return round((sum(second) / len(second)) - (sum(first) / len(first)), 2)


def get_analytics_service() -> AnalyticsService:
    return AnalyticsService()
