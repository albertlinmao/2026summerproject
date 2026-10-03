"""Authentication endpoints.

Two things changed with the person/membership identity model
(``specs/001-analytics-dashboard/identity-contract.md``):

* The insecure ``verify_jwt`` shim that decoded tokens with
  ``verify_signature: False`` against a hard-coded ``"SECRET"`` is **gone**. Every
  request now goes through ``src.core.auth.get_current_user``, which verifies the
  signature. The previous split — this module bypassing verification while
  ``core/auth.py`` verified it — meant a forged token reached the database.
* The minted claims follow the contract in identity-contract.md §4: ``sub`` is the
  auth subject and the only authoritative claim; ``person_id``, ``club_ids`` and
  ``roles_by_club`` are cache. The forbidden ``athlete_ids`` and scalar ``club_id``
  claims are not emitted.
"""

import logging
import time
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import jwt

from src.core.auth import get_current_user
from src.core.config import get_settings
from src.core.database import get_supabase

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Demo login: stands in for the external Multi-Tenant User Service while it is
# stubbed for local development. Disabled in production (APP_ENV=production).
#
# This mints only what the local HS256 path can verify. It is a stub, not a
# second identity system: the real user service owns provisioning and issuance.
# ---------------------------------------------------------------------------

TOKEN_TTL_SECONDS = 3600

_DEMO_USERS: Dict[str, Dict[str, Any]] = {
    "sophie.lin@sst.example.com": {
        "password": "demo123",
        "name": "Sophie Lin",
        "club_code": "SST",
        "club_name": "Seattle Synchro",
        # Coarse role vocabulary; UI titles live in as_club_membership.title.
        "roles": ["coach"],
        "permissions": ["read:dashboard", "read:analytics"],
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
    subject_id = _demo_subject_id(email)
    person_id = _resolve_demo_person_id(subject_id)

    # Roles are club-scoped. The cache mirrors what as_club_membership holds so the
    # UI route guard has something to read on first paint; core.auth re-reads
    # membership from the database before granting anything.
    club_ids: List[str] = [club_id] if person_id else []
    roles_by_club = {club_id: list(account["roles"])} if person_id else {}

    now = int(time.time())
    token = jwt.encode(
        {
            "sub": subject_id,
            "person_id": person_id,
            "club_ids": club_ids,
            "roles_by_club": roles_by_club,
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
            "person_id": person_id,
            "club_ids": club_ids,
            "roles_by_club": roles_by_club,
            "permissions": account["permissions"],
            "name": account["name"],
            "email": email,
        },
    }


@router.get("/auth/me")
def me(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Echo the resolved caller. Useful when debugging claim/membership drift."""
    return {
        "subject_id": user.get("subject_id"),
        "person_id": user.get("person_id"),
        "club_ids": user.get("club_ids"),
        "roles_by_club": user.get("roles_by_club"),
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
            res = get_supabase().table("as_club").select("id").eq("name", club_name).limit(1).execute()
            rows = res.data or []
        except Exception as exc:
            logger.exception("Club lookup failed during demo login")
            raise HTTPException(status_code=503, detail="User database unavailable") from exc

    if not rows:
        raise HTTPException(
            status_code=409,
            detail=(
                "Demo club not found. Run "
                "`python scripts/tmp/AdhocDataMigration/generate_demo_data.py` first."
            ),
        )
    return rows[0]["id"]


def _resolve_demo_person_id(subject_id: str):
    """Find the person provisioned for this demo subject, if any.

    A miss is not an error: it is the normal state before
    ``scripts/user_mgmt_sync.py`` has provisioned the account, and the UI is
    expected to show an unprovisioned state rather than a club.
    """
    try:
        res = (
            get_supabase()
            .table("as_person_identity")
            .select("person_id")
            .eq("subject_id", subject_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.warning("Demo person lookup failed: %s", exc)
        return None

    rows = res.data or []
    return rows[0]["person_id"] if rows else None


def _demo_subject_id(email: str) -> str:
    """Stable pseudo-UUID per demo email so tokens stay consistent across logins.

    This is the *auth subject*, matched against ``as_person_identity.subject_id``.
    It is not a person id: the two are different identifiers.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"sst-demo-subject:{email}"))
