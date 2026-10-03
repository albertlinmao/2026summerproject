from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID

from src.core.auth import get_current_person_id, get_current_user
from src.core.database import supabase
from src.models.media import VideoMarkerInput

router = APIRouter()


@router.get("/videos/{video_id}/markers")
def get_markers(video_id: UUID, user: dict = Depends(get_current_user)):
    resp = supabase.table("as_video_markers") \
        .select("*") \
        .eq("video_id", str(video_id)) \
        .order("time_offset") \
        .execute()
    return resp.data or []


@router.post("/videos/{video_id}/markers")
def create_marker(
    video_id: UUID,
    marker: VideoMarkerInput,
    created_by: str = Depends(get_current_person_id),
):
    # created_by is a person, not a login subject: a coach who never signs in
    # is still the author of the marker.
    video_resp = supabase.table("as_video_uploads") \
        .select("id") \
        .eq("id", str(video_id)) \
        .single() \
        .execute()

    if not video_resp.data:
        raise HTTPException(status_code=404, detail="Video not found.")

    insert_resp = supabase.table("as_video_markers").insert({
        "video_id": str(video_id),
        "time_offset": marker.time_offset,
        "marker_type": marker.marker_type,
        "figure_id": marker.figure_id,
        "label": marker.label,
        "created_by": created_by,
    }).execute()

    return insert_resp.data[0] if insert_resp.data else {}
