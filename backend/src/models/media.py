from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class VideoUpload(BaseModel):
    id: UUID
    club_id: UUID
    uploaded_by: UUID
    storage_path: str
    mime_type: str
    size_bytes: int
    duration_seconds: Optional[float] = None
    status: str
    created_at: datetime


class VideoMarker(BaseModel):
    id: UUID
    video_id: UUID
    time_offset: float
    marker_type: str
    figure_id: Optional[str] = None
    label: Optional[str] = None
    created_by: UUID
    created_at: datetime


class VideoMarkerInput(BaseModel):
    time_offset: float
    marker_type: str
    figure_id: Optional[str] = None
    label: Optional[str] = None


class RoutineTimer(BaseModel):
    id: UUID
    club_id: UUID
    title: Optional[str] = None
    duration_seconds: float
    created_by: UUID
    created_at: datetime


class RoutineTimerInput(BaseModel):
    title: Optional[str] = None
    duration_seconds: float
