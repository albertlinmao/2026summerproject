from datetime import datetime

from pydantic import BaseModel, Field


class CoachingRecommendation(BaseModel):
    """AI-generated natural language coaching feedback (read-only, Principle 11)."""

    athlete_id: str = Field(..., description="External athlete UUID")
    recommendation_text: str = Field(..., description="Natural language practice focus")
    generated_at: datetime = Field(..., description="When the AI generated this insight")
    weakest_figure: str = Field("", description="Figure category needing improvement")
