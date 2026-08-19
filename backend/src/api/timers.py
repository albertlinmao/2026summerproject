from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import verify_jwt
from src.core.database import supabase
from src.models.media import RoutineTimerInput

router = APIRouter()


@router.get("/routines/timers")
def get_timers(user_payload: dict = Depends(verify_jwt)):
    user_id = user_payload.get("uid")

    athlete_resp = supabase.table("athlete") \
        .select("club_id") \
        .eq("id", user_id) \
        .single() \
        .execute()

    if not athlete_resp.data:
        return []

    club_id = athlete_resp.data.get("club_id")

    resp = supabase.table("routine_timers") \
        .select("*") \
        .eq("club_id", club_id) \
        .order("created_at", desc=True) \
        .execute()

    return resp.data or []


@router.post("/routines/timers")
def create_timer(timer: RoutineTimerInput, user_payload: dict = Depends(verify_jwt)):
    user_id = user_payload.get("uid")

    athlete_resp = supabase.table("athlete") \
        .select("club_id") \
        .eq("id", user_id) \
        .single() \
        .execute()

    if not athlete_resp.data:
        raise HTTPException(status_code=404, detail="User not associated with a club.")

    club_id = athlete_resp.data.get("club_id")

    insert_resp = supabase.table("routine_timers").insert({
        "club_id": club_id,
        "title": timer.title,
        "duration_seconds": timer.duration_seconds,
        "created_by": user_id,
    }).execute()

    return insert_resp.data[0] if insert_resp.data else {}
