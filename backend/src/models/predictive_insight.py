from pydantic import BaseModel, Field


class PredictiveInsight(BaseModel):
    """ML-generated forecast for an athlete (read-only per AI Governance, Principle 11)."""

    athlete_id: str = Field(..., description="External athlete UUID")
    next_score_prediction: float = Field(..., description="Expected score at next competition")
    plateau_risk: bool = Field(False, description="True if the athlete is stagnating")
    confidence_interval: float = Field(..., description="95% CI half-width for the prediction")
