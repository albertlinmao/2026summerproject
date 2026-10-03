"""GET /athletes/{person_id}/insights — forecast plus AI coaching recommendation.

Identity follows ``specs/001-analytics-dashboard/identity-contract.md``: the path
carries a **person id** rather than an athlete-row id, because a swimmer with no
account still has results. ``require_person_access`` applies the same visibility
rule as the RLS policies (coach-of, self, guardian-of) at the API layer, which
matters because the backend connects with a key that bypasses RLS.
"""

from fastapi import APIRouter, Depends, HTTPException

from src.core.auth import require_person_access
from src.core.database import supabase
from src.services.predictions.ml_service import predict_next_score
from src.services.ai.openai_service import (
    generate_coaching_recommendation,
    AIServiceUnavailableError,
)

router = APIRouter()


@router.get("/athletes/{person_id}/insights")
def get_athlete_insights(
    person_id: str = Depends(require_person_access),
):
    response = (
        supabase.table("as_competition_results")
        .select("*")
        .eq("person_id", person_id)
        .order("competition_date", desc=True)
        .execute()
    )

    results = response.data or []
    if not results:
        raise HTTPException(status_code=404, detail="No competition results found for this athlete")

    insight = predict_next_score(person_id, results)

    try:
        recommendation = generate_coaching_recommendation(person_id, results)
    except AIServiceUnavailableError:
        recommendation = {
            "person_id": person_id,
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
