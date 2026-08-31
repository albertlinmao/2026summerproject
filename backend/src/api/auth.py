import logging
import time
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt

from src.core.config import get_settings
from src.core.database import get_supabase

logger = logging.getLogger(__name__)

security = HTTPBearer()

router = APIRouter()


def verify_jwt(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        # Connects to 001-multi-tenant-user-api validation
        payload = jwt.decode(token, "SECRET", algorithms=["HS256"], options={"verify_signature": False})
        return payload
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ---------------------------------------------------------------------------
# Demo login: stands in for the external Multi-Tenant User Service while it is
# stubbed for local development. Disabled in production (APP_ENV=production).
# ---------------------------------------------------------------------------

TOKEN_TTL_SECONDS = 3600

_DEMO_USERS: Dict[str, Dict[str, Any]] = {
    "sophie.lin@sst.example.com": {
        "password": "demo123",
        "name": "Sophie Lin",
        "roles": ["Coach"],
        "permissions": ["read:dashboard", "read:analytics"],
        "club_code": "SST",
        "club_name": "Seattle Synchro",
    },
}


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/auth/login")
def login(req: LoginRequest) -> Dict[str, Any]:
    settings = get_settings()
    if settings.APP_ENV == "production":
        raise HTTPException(status_code=404, detail="Not found")

    email = req.email.strip().lower()
    account = _DEMO_USERS.get(email)
    if account is None or req.password != account["password"]:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not settings.USER_SERVICE_JWT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Server JWT signing not configured. Set USER_SERVICE_JWT_SECRET.",
        )

    club_id = _resolve_club_id(account["club_code"], account["club_name"])
    user_id = _demo_user_id(email)

    now = int(time.time())
    token = jwt.encode(
        {
            "sub": user_id,
            "club_id": club_id,
            "roles": account["roles"],
            "athlete_ids": [],
            "permissions": account["permissions"],
            "name": account["name"],
            "email": email,
            "aud": settings.APP_NAME,
            "iss": "sst-demo-auth",
            "iat": now,
            "exp": now + TOKEN_TTL_SECONDS,
        },
        settings.USER_SERVICE_JWT_SECRET,
        algorithm="HS256",
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": TOKEN_TTL_SECONDS,
        "user": {
            "id": user_id,
            "clubId": club_id,
            "roles": account["roles"],
            "athleteIds": [],
            "permissions": account["permissions"],
            "name": account["name"],
            "email": email,
        },
    }


def _resolve_club_id(club_code: str, club_name: str) -> str:
    """Resolve the demo club to the real as_club row created by generate_demo_data."""
    try:
        supabase = get_supabase()
        res = (
            supabase.table("as_club")
            .select("id")
            .eq("code", club_code)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            # Schema without a code column / different seeding: fall back by name.
            res = supabase.table("as_club").select("id").eq("name", club_name).limit(1).execute()
            rows = res.data or []
    except Exception:
        # Unknown column or DB unavailable: try name only before giving up.
        try:
            res = supabase.table("as_club").select("id").eq("name", club_name).limit(1).execute()
            rows = res.data or []
        except Exception as exc:
            logger.exception("Club lookup failed during demo login")
            raise HTTPException(status_code=503, detail="User database unavailable") from exc

    if not rows:
        raise HTTPException(
            status_code=409,
            detail="Demo club not found. Run `python generate_demo_data.py` first.",
        )
    return rows[0]["id"]


def _demo_user_id(email: str) -> str:
    """Stable pseudo-UUID per demo email so tokens stay consistent across logins."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"sst-demo-user:{email}"))
