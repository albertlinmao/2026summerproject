from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class FigureResultRecord(BaseModel):
    """A single figure result row from as_meet_figure_result."""

    id: str
    meet_id: str
    rank: Optional[str] = None
    draw: Optional[str] = None
    team_code: Optional[str] = None
    team_name: Optional[str] = None
    athlete_name: str
    athlete_birth_year: Optional[int] = None
    penalty: Optional[str] = None
    total_score: Optional[float] = None
    figure_score: Optional[float] = None
    figure_scores: dict[str, Any] = Field(default_factory=dict)
    source_file: Optional[str] = None
    created_at: Optional[datetime] = None


class RoutineResultRecord(BaseModel):
    """A single routine result row from as_meet_routine_result."""

    id: str
    meet_id: str
    rank: Optional[str] = None
    draw: Optional[str] = None
    team_code: Optional[str] = None
    team_name: Optional[str] = None
    team_athletes: list[Any] = Field(default_factory=list)
    routine_score: Optional[float] = None
    element_total: Optional[float] = None
    artisticimpression_total: Optional[float] = None
    synchronization_total: Optional[float] = None
    source_file: Optional[str] = None
    created_at: Optional[datetime] = None


class CompetitionResult(BaseModel):
    """Aggregated competition result for an athlete.

    Aggregates scores from as_meet_figure_result and as_meet_routine_result,
    matched to the athlete via fuzzy name + birth year + club/team_code.
    """

    athlete_id: str
    athlete_name: str
    meet_id: str
    meet_date: Optional[date] = None
    figure_score: Optional[float] = None
    routine_score: Optional[float] = None
    combined_score: Optional[float] = None
    rank: Optional[str] = None
    team_code: Optional[str] = None
    team_name: Optional[str] = None
    source_file: Optional[str] = None

    def model_post_init(self, __context: Any) -> None:
        if self.combined_score is None:
            parts = [s for s in (self.figure_score, self.routine_score) if s is not None]
            self.combined_score = round(sum(parts), 2) if parts else None
