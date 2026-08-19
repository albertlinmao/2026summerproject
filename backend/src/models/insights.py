from pydantic import BaseModel
from datetime import datetime


class PredictiveInsight(BaseModel):
    athlete_id: str
    next_score_prediction: float
    plateau_risk: bool
    confidence_interval: float


class CoachingRecommendation(BaseModel):
    athlete_id: str
    recommendation_text: str
    generated_at: datetime
    weakest_figure: str
