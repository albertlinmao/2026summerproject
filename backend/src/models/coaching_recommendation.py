from datetime import datetime

from pydantic import BaseModel, Field


class CoachingRecommendation(BaseModel):
    """AI-generated natural language coaching feedback (read-only, Principle 11).

    Keyed on ``person_id``, not a login. See
    :class:`src.models.predictive_insight.PredictiveInsight` for the rationale.
    """

    person_id: str = Field(..., description="Person UUID (as_person.id)")
    recommendation_text: str = Field(..., description="Natural language practice focus")
    generated_at: datetime = Field(..., description="When the AI generated this insight")
    weakest_figure: str = Field("", description="Figure category needing improvement")
