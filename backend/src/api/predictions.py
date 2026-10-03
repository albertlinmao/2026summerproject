"""US1 endpoint: GET /analytics/athletes/{person_id}/prediction — predictive insight."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from src.core.auth import require_club_membership, require_person_access
from src.services.analytics.analytics_service import AnalyticsService, get_analytics_service
from src.services.predictions.prediction_service import PredictionService, get_prediction_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _resolve_scores(
    person_id: str,
    club_id: str,
    analytics: AnalyticsService,
) -> list[float]:
    trends = analytics.get_person_trends(person_id, club_id=club_id)
    if not trends:
        raise HTTPException(status_code=404, detail="Athlete not found in your club")
    history = trends.get("history") or []
    return [h["figure_score"] for h in history if h.get("figure_score") is not None]


@router.get("/analytics/athletes/{person_id}/prediction")
def get_athlete_prediction(
    person_id: str = Depends(require_person_access),
    club_id: str = Depends(require_club_membership),
    analytics: AnalyticsService = Depends(get_analytics_service),
    predictions: PredictionService = Depends(get_prediction_service),
) -> Dict[str, Any]:
    """Next-score forecast, plateau risk, and confidence interval for one athlete.

    The path carries a person id and access is checked against the caller's
    membership, so a caller cannot forecast another person's future scores. Club
    scope comes from active membership rather than a scalar claim.
    """
    try:
        scores = _resolve_scores(person_id, club_id, analytics)
        insight = predictions.predict(person_id, scores)
        return insight.model_dump()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Prediction failed for person %s", person_id)
        raise HTTPException(status_code=503, detail="Prediction service unavailable") from exc
