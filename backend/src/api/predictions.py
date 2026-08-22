"""US1 endpoint: GET /analytics/athletes/{athlete_id}/prediction — predictive insight."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from src.core.auth import get_current_user
from src.services.analytics.analytics_service import AnalyticsService, get_analytics_service
from src.services.predictions.prediction_service import PredictionService, get_prediction_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _resolve_scores(
    athlete_id: str,
    club_id: str,
    analytics: AnalyticsService,
) -> list[float]:
    trends = analytics.get_athlete_trends(athlete_id, club_id=club_id)
    if not trends:
        raise HTTPException(status_code=404, detail="Athlete not found in your club")
    history = trends.get("history") or []
    return [h["figure_score"] for h in history if h.get("figure_score") is not None]


@router.get("/analytics/athletes/{athlete_id}/prediction")
def get_athlete_prediction(
    athlete_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
    analytics: AnalyticsService = Depends(get_analytics_service),
    predictions: PredictionService = Depends(get_prediction_service),
) -> Dict[str, Any]:
    """Next-score forecast, plateau risk, and confidence interval for one athlete."""
    club_id = user.get("club_id")
    if not club_id:
        raise HTTPException(status_code=403, detail="Club access required")

    try:
        scores = _resolve_scores(athlete_id, club_id, analytics)
        insight = predictions.predict(athlete_id, scores)
        return insight.model_dump()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Prediction failed for athlete %s", athlete_id)
        raise HTTPException(status_code=503, detail="Prediction service unavailable") from exc
