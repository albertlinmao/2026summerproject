from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class FigureResultRecord(BaseModel):
    """A single figure result row from as_meet_figure_result.

    ``athlete_name`` / ``athlete_birth_year`` are verbatim fields from the source
    PDF and are immutable lineage, not identity references. ``person_id`` is the
    canonical person resolved through ``as_result_person_link`` and is null until
    that resolution has been made.
    """

    id: str
    meet_id: str
    rank: Optional[str] = None
    draw: Optional[str] = None
    team_code: Optional[str] = None
    team_name: Optional[str] = None
    athlete_name: str
    athlete_birth_year: Optional[int] = None
    person_id: Optional[str] = None
    penalty: Optional[str] = None
    total_score: Optional[float] = None
    figure_score: Optional[float] = None
    figure_scores: dict[str, Any] = Field(default_factory=dict)
    source_file: Optional[str] = None
    created_at: Optional[datetime] = None


class RoutineResultRecord(BaseModel):
    """A single routine result row from as_meet_routine_result.

    ``team_athletes`` is the printed-names array from the source PDF, i.e. lineage.
    Per-athlete person resolution lives in ``as_result_person_link``, which keys on
    ``(result_table, result_id, athlete_name)`` because every athlete in a routine
    shares one ``result_id``.
    """

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
    """One person's result at one meet.

    Aggregation is keyed on ``person_id`` so it survives a club transfer, and
    ``athlete_name`` is retained as the printed name for display and for
    traceability back to the immutable source row.
    """

    person_id: str
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
