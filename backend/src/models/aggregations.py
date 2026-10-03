from pydantic import BaseModel
from typing import List


class HeatmapData(BaseModel):
    """Per-person analytical row for the coach heatmap.

    ``person_id`` is a person, not a login: a swimmer who has no account still
    appears here, and one person keeps a single identity across a club transfer.
    """

    person_id: str
    figure_weaknesses: dict
    prediction_score: float
    figure_score: float = 0.0
    routine_score: float = 0.0


class TeamOverview(BaseModel):
    """The coach's view of the club they are coaching in.

    ``club_id`` scopes the roster. ``coach_id`` is a person id, matching the
    caller; it is not a login subject.
    """

    coach_id: str
    club_id: str
    team_heatmap: List[HeatmapData]
