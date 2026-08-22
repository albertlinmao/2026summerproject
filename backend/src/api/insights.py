from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import verify_jwt
from src.core.database import supabase
from src.services.predictions.ml_service import predict_next_score
from src.services.ai.openai_service import (
    generate_coaching_recommendation,
    AIServiceUnavailableError,
)

router = APIRouter()


@router.get("/athletes/{athlete_id}/insights")
def get_athlete_insights(
    athlete_id: str,
    user_payload: dict = Depends(verify_jwt),
):
    response = (
        supabase.table("as_competition_results")
        .select("*")
        .eq("athlete_id", athlete_id)
        .order("competition_date", desc=True)
        .execute()
    )

    results = response.data or []
    if not results:
        raise HTTPException(status_code=404, detail="No competition results found for this athlete")

    insight = predict_next_score(athlete_id, results)

    try:
        recommendation = generate_coaching_recommendation(athlete_id, results)
    except AIServiceUnavailableError:
        recommendation = {
            "athlete_id": athlete_id,
            "recommendation_text": "AI temporarily unavailable",
            "generated_at": None,
            "weakest_figure": "",
        }

    return {
        "insight": insight.model_dump(),
        "recommendation": (
            recommendation.model_dump()
            if hasattr(recommendation, "model_dump")
            else recommendation
        ),
    }
