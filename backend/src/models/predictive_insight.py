from pydantic import BaseModel, Field


class PredictiveInsight(BaseModel):
    """ML-generated forecast for a person (read-only per AI Governance, Principle 11).

    Keyed on ``person_id``, not a login: a swimmer with no account still receives
    forecasts, and one person keeps a single identity across a club transfer.
    """

    person_id: str = Field(..., description="Person UUID (as_person.id)")
    next_score_prediction: float = Field(..., description="Expected score at next competition")
    plateau_risk: bool = Field(False, description="True if the athlete is stagnating")
    confidence_interval: float = Field(..., description="95% CI half-width for the prediction")
