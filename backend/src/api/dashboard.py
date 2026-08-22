"""US1 endpoint: GET /analytics/dashboard — role-based widget data aggregation."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from src.core.auth import get_current_user
from src.services.analytics.analytics_service import AnalyticsService, get_analytics_service

logger = logging.getLogger(__name__)

router = APIRouter()

COACH_ROLES = {"Coach", "Lead Coach", "Team Captain"}
ADMIN_ROLES = {"Club Admin", "Club Owner"}


@router.get("/analytics/dashboard")
def get_dashboard(
    user: Dict[str, Any] = Depends(get_current_user),
    analytics: AnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Aggregate widget data based on the caller's role and club scope."""
    club_id = user.get("club_id")
    if not club_id:
        raise HTTPException(status_code=403, detail="Club access required")

    roles = set(user.get("roles") or [])
    athlete_ids = user.get("athlete_ids") or []

    try:
        if roles & COACH_ROLES or roles & ADMIN_ROLES:
            overview = analytics.get_team_overview(club_id)
            return {
                "role": "coach" if roles & COACH_ROLES else "admin",
                "club_id": club_id,
                "widgets": {
                    "team_overview": overview,
                },
            }

        # Athlete-facing summary (own data only)
        own_id = athlete_ids[0] if athlete_ids else user.get("user_id")
        trends = analytics.get_athlete_trends(own_id, club_id=club_id) if own_id else {}
        return {
            "role": "athlete",
            "club_id": club_id,
            "widgets": {
                "personal_summary": trends,
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Dashboard aggregation failed for club %s", club_id)
        raise HTTPException(status_code=503, detail="Analytics data unavailable") from exc
