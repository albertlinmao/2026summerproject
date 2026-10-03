from fastapi import APIRouter, Depends

from src.core.auth import get_current_person_id, require_club_membership
from src.core.database import supabase
from src.models.media import RoutineTimerInput

router = APIRouter()


@router.get("/routines/timers")
def get_timers(club_id: str = Depends(require_club_membership)):
    # Timers are club-scoped, and the club now comes from the caller's active
    # membership. It cannot be read off the person: as_athlete is a view that
    # carries no club_id.
    resp = supabase.table("as_routine_timers") \
        .select("*") \
        .eq("club_id", club_id) \
        .order("created_at", desc=True) \
        .execute()

    return resp.data or []


@router.post("/routines/timers")
def create_timer(
    timer: RoutineTimerInput,
    created_by: str = Depends(get_current_person_id),
    club_id: str = Depends(require_club_membership),
):
    insert_resp = supabase.table("as_routine_timers").insert({
        "club_id": club_id,
        "title": timer.title,
        "duration_seconds": timer.duration_seconds,
        "created_by": created_by,
    }).execute()

    return insert_resp.data[0] if insert_resp.data else {}
