import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any, List
from functools import lru_cache
import httpx
import logging
from src.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


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
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=[settings.USER_SERVICE_JWT_ALGORITHM],
                audience=settings.APP_NAME,
                options={"verify_aud": True}
            )
            return payload
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
        return {
            "user_id": payload.get("sub"),
            "club_id": payload.get("club_id"),
            "roles": payload.get("roles", []),
            "athlete_ids": payload.get("athlete_ids", []),
            "permissions": payload.get("permissions", []),
        }


jwt_auth = JWTAuth()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Dict[str, Any]:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = await jwt_auth.validate_token(credentials.credentials)
    claims = jwt_auth.extract_claims(payload)

    # Validate required claims
    if not claims.get("user_id"):
        raise HTTPException(status_code=401, detail="Invalid token: missing user_id")

    return claims


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[Dict[str, Any]]:
    if credentials is None:
        return None
    try:
        payload = await jwt_auth.validate_token(credentials.credentials)
        return jwt_auth.extract_claims(payload)
    except HTTPException:
        return None


def require_role(*required_roles: str):
    async def role_checker(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_roles = user.get("roles", [])
        if not any(role in user_roles for role in required_roles):
            raise HTTPException(
                status_code=403,
                detail=f"Required role(s): {', '.join(required_roles)}"
            )
        return user
    return role_checker


def require_club_access(user: Dict[str, Any] = Depends(get_current_user)) -> str:
    club_id = user.get("club_id")
    if not club_id:
        raise HTTPException(status_code=403, detail="Club access required")
    return club_id


def get_club_id(user: Dict[str, Any] = Depends(get_current_user)) -> Optional[str]:
    return user.get("club_id")