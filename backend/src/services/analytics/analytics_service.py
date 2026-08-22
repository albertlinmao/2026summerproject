"""AnalyticsService: centralized analytics engine for dashboard widgets.

Implements the layered analytics architecture (Constitution Principle 14):
queries run against aggregated data (materialized view / result tables),
never raw per-request computation on unaggregated sources where avoidable.
"""

import logging
from typing import Any, Optional

from src.core.database import get_supabase
from src.models.athlete_ref import AthleteReference

logger = logging.getLogger(__name__)

# Baseline used when an athlete has too few records for statistics
BASELINE_SCORE = 70.0
MIN_RECORDS_FOR_STATS = 5


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
    # Athlete resolution (club isolation enforced here)
    # ------------------------------------------------------------------

    def get_club_athletes(self, club_id: str) -> list[AthleteReference]:
        """Fetch athlete references for a club from the external-managed table."""
        response = (
            self.client.table("as_athlete").select("id, club_id, name").eq("club_id", club_id).execute()
        )
        rows = response.data or []
        return [
            AthleteReference(id=r["id"], club_id=r["club_id"], name=r.get("name", ""))
            for r in rows
            if r.get("id")
        ]

    def get_athlete(self, athlete_id: str, club_id: Optional[str] = None) -> Optional[AthleteReference]:
        """Fetch one athlete reference, optionally enforcing club scope."""
        query = self.client.table("as_athlete").select("id, club_id, name").eq("id", athlete_id)
        if club_id:
            query = query.eq("club_id", club_id)
        response = query.execute()
        rows = response.data or []
        if not rows:
            return None
        row = rows[0]
        return AthleteReference(id=row["id"], club_id=row["club_id"], name=row.get("name", ""))

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
        """Team athletes with average figure/routine scores, most improved, at-risk."""
        athletes = self.get_club_athletes(club_id)
        team_codes = self._club_team_codes(club_id)
        figure_rows = self._fetch_figure_results(team_codes)
        routine_rows = self._fetch_routine_results(team_codes)

        by_name = {a.name.strip().lower(): a for a in athletes}

        figure_history: dict[str, list[float]] = {}
        for row in figure_rows:
            key = (row.get("athlete_name") or "").strip().lower()
            score = row.get("figure_score")
            if key in by_name and score is not None:
                figure_history.setdefault(key, []).append(float(score))

        routine_history: dict[str, list[float]] = {}
        for row in routine_rows:
            athletes_in_routine = row.get("team_athletes") or []
            names = []
            for entry in athletes_in_routine:
                if isinstance(entry, str):
                    names.append(entry)
                elif isinstance(entry, dict):
                    names.append(str(entry.get("name", "")))
            score = row.get("routine_score")
            if score is None:
                continue
            for name in names:
                key = name.strip().lower()
                if key in by_name:
                    routine_history.setdefault(key, []).append(float(score))

        athlete_stats = []
        for athlete in athletes:
            key = athlete.name.strip().lower()
            fig_scores = figure_history.get(key, [])
            rut_scores = routine_history.get(key, [])
            avg_figure = round(sum(fig_scores) / len(fig_scores), 2) if fig_scores else None
            avg_routine = round(sum(rut_scores) / len(rut_scores), 2) if rut_scores else None
            trend = self._trend(fig_scores + rut_scores)
            athlete_stats.append(
                {
                    "athlete_id": athlete.id,
                    "name": athlete.name,
                    "avg_figure_score": avg_figure,
                    "avg_routine_score": avg_routine,
                    "improvement_trend": trend,
                    "at_risk": trend is not None and trend < 0,
                    "records_count": len(fig_scores) + len(rut_scores),
                }
            )

        scored = [s for s in athlete_stats if s["improvement_trend"] is not None]
        most_improved = max(scored, key=lambda s: s["improvement_trend"], default=None)
        at_risk = [s for s in athlete_stats if s["at_risk"]]

        return {
            "club_id": club_id,
            "athletes": athlete_stats,
            "most_improved": most_improved,
            "at_risk": at_risk,
        }

    def get_figure_weakness_heatmap(self, club_id: str) -> dict[str, Any]:
        """Per-athlete x per-figure average scores for the coach's club."""
        athletes = self.get_club_athletes(club_id)
        by_name = {a.name.strip().lower(): a for a in athletes}
        team_codes = self._club_team_codes(club_id)
        figure_rows = self._fetch_figure_results(team_codes)

        matrix: dict[str, dict[str, list[float]]] = {}
        for row in figure_rows:
            key = (row.get("athlete_name") or "").strip().lower()
            athlete = by_name.get(key)
            if not athlete:
                continue
            for figure_code, value in (row.get("figure_scores") or {}).items():
                try:
                    matrix.setdefault(athlete.id, {}).setdefault(str(figure_code), []).append(
                        float(value)
                    )
                except (TypeError, ValueError):
                    continue

        all_figures = sorted({f for per_athlete in matrix.values() for f in per_athlete})
        cells = []
        for athlete in athletes:
            per_figure = matrix.get(athlete.id, {})
            weaknesses = {
                code: round(sum(vals) / len(vals), 2)
                for code, vals in sorted(per_figure.items())
                if vals
            }
            weakest = min(weaknesses, key=weaknesses.get) if weaknesses else None
            cells.append(
                {
                    "athlete_id": athlete.id,
                    "name": athlete.name,
                    "weaknesses": weaknesses,
                    "weakest_figure": weakest,
                }
            )

        return {"club_id": club_id, "figures": all_figures, "athletes": cells}

    def get_athlete_trends(self, athlete_id: str, club_id: Optional[str] = None) -> dict[str, Any]:
        """Figure/routine trends over time plus radar chart data for one athlete."""
        athlete = self.get_athlete(athlete_id, club_id)
        if not athlete:
            return {}

        team_codes = self._club_team_codes(athlete.club_id)
        figure_rows = self._fetch_figure_results(team_codes)

        key = athlete.name.strip().lower()
        history: list[dict[str, Any]] = []
        figure_totals: dict[str, list[float]] = {}
        for row in figure_rows:
            row_key = (row.get("athlete_name") or "").strip().lower()
            if row_key != key:
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
            "athlete_id": athlete.id,
            "name": athlete.name,
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
