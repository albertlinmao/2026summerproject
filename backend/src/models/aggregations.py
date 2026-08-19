from pydantic import BaseModel
from typing import List

class HeatmapData(BaseModel):
    athlete_id: str
    figure_weaknesses: dict
    prediction_score: float
    figure_score: float = 0.0
    routine_score: float = 0.0

class TeamOverview(BaseModel):
    coach_id: str
    team_heatmap: List[HeatmapData]
