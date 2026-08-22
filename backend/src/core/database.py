import threading
import logging
from typing import Any

from supabase import create_client, Client

from src.core.config import get_settings
from src.core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


class _LazySupabaseClient:
    """Defers Supabase client creation until first use.

    Keeps the application importable and startable even when Supabase
    credentials are missing; requests that actually need the database then
    fail with a clear 503 instead of crashing at startup.
    """

    def __init__(self) -> None:
        self._client: Client | None = None
        self._lock = threading.Lock()

    def _get(self) -> Client:
        if self._client is None:
            with self._lock:
                if self._client is None:
                    settings = get_settings()
                    key = (
                        settings.SUPABASE_SERVICE_ROLE_KEY
                        or settings.SUPABASE_ANON_KEY
                        or settings.SUPABASE_KEY
                    )
                    if not key:
                        raise ExternalServiceError(
                            "Supabase",
                            "not configured: set SUPABASE_SERVICE_ROLE_KEY "
                            "(or SUPABASE_ANON_KEY / SUPABASE_KEY) in the environment",
                        )
                    self._client = create_client(settings.SUPABASE_URL, key)
                    logger.info("Supabase client initialized for %s", settings.SUPABASE_URL)
        return self._client

    def __getattr__(self, name: str) -> Any:
        # Guard against infinite recursion if internal attrs are not yet set.
        if name.startswith("__") or name in ("_client", "_lock"):
            raise AttributeError(name)
        return getattr(self._get(), name)


# Backward-compatible module-level proxy (supports `database.supabase.table(...)`)
supabase: Client = _LazySupabaseClient()  # type: ignore[assignment]


def get_supabase() -> Client:
    """Dependency injection for Supabase client."""
    return supabase  # type: ignore[return-value]


def get_supabase_admin() -> Client:
    """Get Supabase client with service role for admin operations."""
    settings = get_settings()
    if not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise ExternalServiceError(
            "Supabase", "admin operations require SUPABASE_SERVICE_ROLE_KEY"
        )
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
