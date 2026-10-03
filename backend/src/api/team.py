"""US1 endpoint: GET /analytics/team/heatmap — figure weakness heatmap for a club."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from src.core.auth import require_club_membership
from src.services.analytics.analytics_service import AnalyticsService, get_analytics_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/analytics/team/heatmap")
def get_team_heatmap(
    club_id: str = Depends(require_club_membership),
    analytics: AnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    """Figure weakness heatmap (athlete x figure averages) for the caller's club.

    The club is the caller's first active membership, not a scalar ``club_id``
    claim: one person may coach in several clubs.
    """
    try:
        return analytics.get_figure_weakness_heatmap(club_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Team heatmap failed for club %s", club_id)
        raise HTTPException(status_code=503, detail="Analytics data unavailable") from exc
