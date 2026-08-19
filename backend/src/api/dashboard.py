from fastapi import APIRouter, Depends
from src.api.auth import verify_jwt
from src.services.analytics.coach_service import get_coach_team_overview

router = APIRouter()

@router.get('/analytics/dashboard')
def get_dashboard(user_payload: dict = Depends(verify_jwt)):
    # Simple role check for Phase 3 MVP
    coach_id = user_payload.get('uid')
    return get_coach_team_overview(coach_id)
