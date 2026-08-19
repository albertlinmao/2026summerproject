from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID

from src.api.auth import verify_jwt
from src.core.database import supabase
from src.models.media import VideoMarkerInput

router = APIRouter()


@router.get("/videos/{video_id}/markers")
def get_markers(video_id: UUID, user_payload: dict = Depends(verify_jwt)):
    resp = supabase.table("video_markers") \
        .select("*") \
        .eq("video_id", str(video_id)) \
        .order("time_offset") \
        .execute()
    return resp.data or []


@router.post("/videos/{video_id}/markers")
def create_marker(video_id: UUID, marker: VideoMarkerInput, user_payload: dict = Depends(verify_jwt)):
    user_id = user_payload.get("uid")

    video_resp = supabase.table("video_uploads") \
        .select("id") \
        .eq("id", str(video_id)) \
        .single() \
        .execute()

    if not video_resp.data:
        raise HTTPException(status_code=404, detail="Video not found.")

    insert_resp = supabase.table("video_markers").insert({
        "video_id": str(video_id),
        "time_offset": marker.time_offset,
        "marker_type": marker.marker_type,
        "figure_id": marker.figure_id,
        "label": marker.label,
        "created_by": user_id,
    }).execute()

    return insert_resp.data[0] if insert_resp.data else {}
