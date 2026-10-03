"""Authentication and authorization.

The identity model is described in ``specs/001-analytics-dashboard/identity-contract.md``:
a **person** is a human, a **club** is the tenant, and **membership** is the edge
between them. Roles are scoped per club, so one person may be a ``swimmer`` in one
club and a ``coach`` in another, and a login is optional.

Two consequences shape this module:

* The only claim RLS trusts is ``sub``, matched against ``as_person_identity.subject_id``.
  ``person_id`` / ``club_ids`` / ``roles_by_club`` are an advisory cache for the UI only.
* Club scope and role are resolved from ``as_club_membership`` on every request, never
  from a token. Offboarding and role changes therefore take effect immediately instead
  of at token expiry.

AUTHORIZATION IS ENFORCED IN TWO PLACES, deliberately:

1. The helpers here (``can_view_person``, ``has_club_role``, ``require_club_role``) gate
   the REST API. This layer is load-bearing because the backend connects with the
   Supabase service-role key, which **bypasses RLS**.
2. The RLS policies in the SQL migrations gate direct PostgREST / anon-key access.

If a membership lookup cannot be completed, this module raises 503 rather than falling
back to the token. Serving an unverifiable request is the exact failure the
membership-authoritative design exists to prevent.
"""

from typing import Any, Dict, List, Optional, Sequence

import jwt
import logging
from jwt import PyJWKClient

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.config import get_settings
from src.core.database import get_supabase
from src.core.exceptions import ExternalServiceError

settings = get_settings()
logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

#: Statuses that grant access. ``dormant`` and ``left`` revoke it immediately.
ACTIVE_MEMBERSHIP_STATUSES = ("invited", "active")

#: The coarse role vocabulary that RLS matches on. UI distinctions such as
#: "Lead Coach", "Team Captain" and "Club Owner" live in ``as_club_membership.title``
#: and never authorize anything.
CLUB_ROLES = frozenset({"admin", "coach", "swimmer", "parent", "official"})

#: Roles that grant club-wide staff authority.
STAFF_ROLES = frozenset({"coach", "admin"})


class JWTAuth:
    def __init__(self):
        self._jwks_client: Optional[PyJWKClient] = None
        self._jwks_url = settings.USER_SERVICE_JWKS_URL

    @property
    def jwks_client(self) -> PyJWKClient:
        if self._jwks_client is None:
            if not self._jwks_url:
                raise HTTPException(
                    status_code=503,
                    detail="JWKS URL not configured. Cannot validate JWT."
                )
            self._jwks_client = PyJWKClient(self._jwks_url)
        return self._jwks_client

    async def validate_token(self, token: str) -> Dict[str, Any]:
        try:
            if self._jwks_url:
                # Tokens issued by the external Multi-Tenant User Service (RS256 via JWKS).
                signing_key = self.jwks_client.get_signing_key_from_jwt(token)
                payload = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=[settings.USER_SERVICE_JWT_ALGORITHM],
                    audience=settings.APP_NAME,
                    options={"verify_aud": True}
                )
            elif settings.USER_SERVICE_JWT_SECRET:
                # Locally-issued tokens (HS256 shared secret), e.g. from POST /api/auth/login
                payload = jwt.decode(
                    token,
                    settings.USER_SERVICE_JWT_SECRET,
                    algorithms=["HS256"],
                    audience=settings.APP_NAME,
                )
            else:
                raise HTTPException(
                    status_code=503,
                    detail="JWT validation not configured. Set USER_SERVICE_JWKS_URL "
                           "or USER_SERVICE_JWT_SECRET.",
                )
            return payload
        except HTTPException:
            raise
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidAudienceError:
            raise HTTPException(status_code=401, detail="Invalid token audience")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
        except Exception as e:
            logger.error(f"JWT validation error: {e}")
            raise HTTPException(status_code=503, detail="Authentication service unavailable")

    def extract_claims(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Project the verified token onto the contract in identity-contract.md §4.

        Only ``subject_id`` is authoritative. Everything else here is cache: it is
        used to build the UI's club switcher and route guards, and is always
        re-checked against ``as_club_membership`` before granting access.
        """
        return {
            "subject_id": payload.get("sub"),
            "person_id": payload.get("person_id"),
            "club_ids": payload.get("club_ids", []) or [],
            "roles_by_club": payload.get("roles_by_club", {}) or {},
            "permissions": payload.get("permissions", []) or [],
            "name": payload.get("name"),
            "email": payload.get("email"),
        }


jwt_auth = JWTAuth()


# ---------------------------------------------------------------------------
# Membership resolution — the authorization source of truth
# ---------------------------------------------------------------------------

def _resolve_person_id(subject_id: str) -> Optional[str]:
    """Map a verified auth subject to a person.

    Returns ``None`` for a valid token whose subject has no ``as_person_identity``
    row, which is the expected state for anyone the club has not provisioned yet.
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
        logger.exception("Person resolution failed for subject %s", subject_id)
        raise ExternalServiceError("Supabase", f"identity lookup failed: {exc}") from exc

    rows = res.data or []
    return rows[0]["person_id"] if rows else None


def _load_memberships(person_id: str) -> List[Dict[str, Any]]:
    """Active memberships for a person, across every club."""
    try:
        res = (
            get_supabase()
            .table("as_club_membership")
            .select("id, club_id, role, title, status, joined_at, left_at")
            .eq("person_id", person_id)
            .in_("status", list(ACTIVE_MEMBERSHIP_STATUSES))
            .execute()
        )
    except Exception as exc:
        logger.exception("Membership lookup failed for person %s", person_id)
        raise ExternalServiceError("Supabase", f"membership lookup failed: {exc}") from exc

    return res.data or []


def _build_caller(payload: Dict[str, Any]) -> Dict[str, Any]:
    claims = jwt_auth.extract_claims(payload)
    subject_id = claims.get("subject_id")
    if not subject_id:
        raise HTTPException(status_code=401, detail="Invalid token: missing sub")

    person_id = _resolve_person_id(subject_id)
    memberships: List[Dict[str, Any]] = []
    if person_id:
        memberships = _load_memberships(person_id)

    # The claim cache is only trusted once it agrees with the database, so a
    # stale token cannot widen access and a fresh offboarding cannot be ignored.
    roles_by_club: Dict[str, List[str]] = {}
    for m in memberships:
        roles_by_club.setdefault(m["club_id"], []).append(m["role"])

    return {
        **claims,
        "person_id": person_id,
        "memberships": memberships,
        "club_ids": [m["club_id"] for m in memberships],
        "roles_by_club": roles_by_club,
    }


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Dict[str, Any]:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = await jwt_auth.validate_token(credentials.credentials)
        return _build_caller(payload)
    except HTTPException:
        raise
    except ExternalServiceError as exc:
        # Authorization could not be established. Serving anyway would hand out
        # access we cannot verify.
        logger.error("Authorization unavailable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Unable to verify club membership. Please retry.",
        ) from exc


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[Dict[str, Any]]:
    if credentials is None:
        return None
    try:
        payload = await jwt_auth.validate_token(credentials.credentials)
        return _build_caller(payload)
    except HTTPException:
        return None
    except ExternalServiceError:
        logger.error("Authorization unavailable for optional caller")
        return None


def get_current_person_id(user: Dict[str, Any] = Depends(get_current_user)) -> str:
    """The caller's person id. 403 when the token has no provisioned person."""
    person_id = user.get("person_id")
    if not person_id:
        raise HTTPException(
            status_code=403,
            detail="No club membership is associated with this account",
        )
    return person_id


# ---------------------------------------------------------------------------
# Authorization predicates (mirrors the app_*() SQL helpers)
# ---------------------------------------------------------------------------

def has_club_role(user: Dict[str, Any], club_id: str, roles: Sequence[str]) -> bool:
    """True when the caller holds one of ``roles`` in ``club_id``."""
    for m in user.get("memberships") or []:
        if m.get("club_id") == club_id and m.get("role") in roles:
            return True
    return False


def is_club_staff(user: Dict[str, Any], club_id: str) -> bool:
    return has_club_role(user, club_id, STAFF_ROLES)


def get_default_club_id(user: Dict[str, Any]) -> Optional[str]:
    """The caller's first active club, if any.

    Multi-club callers should not rely on this: endpoints that act within a club
    take the club from the request instead of guessing.
    """
    club_ids = user.get("club_ids") or []
    return club_ids[0] if club_ids else None


def require_club_membership(user: Dict[str, Any] = Depends(get_current_user)) -> str:
    club_id = get_default_club_id(user)
    if not club_id:
        raise HTTPException(status_code=403, detail="Club access required")
    return club_id


def require_club_role(*required_roles: str):
    """Require one of ``required_roles`` in **any** active club.

    Replaces the old flat ``require_role``, which read a single ``roles`` claim and
    could not express that a role is scoped to one club only.
    """
    wanted = set(required_roles)

    async def role_checker(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        for roles in (user.get("roles_by_club") or {}).values():
            if wanted & set(roles or []):
                return user
        raise HTTPException(
            status_code=403,
            detail=f"Required role(s): {', '.join(sorted(wanted))}",
        )
    return role_checker


def visible_person_ids(user: Dict[str, Any]) -> set:
    """People whose analytics the caller may read.

    Mirrors ``app_visible_person_ids()``: the swimmers they coach, themselves, and
    their own children via ``as_person_link``.
    """
    person_id = user.get("person_id")
    if not person_id:
        return set()

    staff_clubs = {
        m["club_id"] for m in user.get("memberships") or []
        if m.get("role") in STAFF_ROLES
    }

    visible = {person_id}
    if staff_clubs:
        visible |= _swimmers_in_clubs(staff_clubs)
    visible |= _children_of(person_id)
    return visible


def _swimmers_in_clubs(club_ids: set) -> set:
    try:
        res = (
            get_supabase()
            .table("as_club_membership")
            .select("person_id")
            .in_("club_id", list(club_ids))
            .in_("status", list(ACTIVE_MEMBERSHIP_STATUSES))
            .eq("role", "swimmer")
            .execute()
        )
    except Exception as exc:
        logger.exception("Swimmer scope lookup failed for clubs %s", club_ids)
        raise ExternalServiceError("Supabase", f"scope lookup failed: {exc}") from exc
    return {row["person_id"] for row in (res.data or [])}


def _children_of(person_id: str) -> set:
    try:
        res = (
            get_supabase()
            .table("as_person_link")
            .select("child_person_id")
            .eq("parent_person_id", person_id)
            .in_("kind", ["parent", "guardian"])
            .execute()
        )
    except Exception as exc:
        logger.exception("Guardian lookup failed for person %s", person_id)
        raise ExternalServiceError("Supabase", f"scope lookup failed: {exc}") from exc
    return {row["child_person_id"] for row in (res.data or [])}


def can_view_person(user: Dict[str, Any], person_id: str) -> bool:
    """Whether the caller may read this person's analytics."""
    return person_id in visible_person_ids(user)


def require_person_access(
    person_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> str:
    if not can_view_person(user, person_id):
        raise HTTPException(status_code=403, detail="Not permitted for this athlete")
    return person_id
