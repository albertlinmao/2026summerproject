"""MaterializedViewService: on-demand refresh + caching for daily aggregations.

Research decision: on-demand refresh with caching when first accessed —
balances freshness against database load (no scheduled/event-driven refresh).

Rows are keyed on ``person_id`` (``specs/001-analytics-dashboard/identity-contract.md``),
so the cache key is membership-independent: a person keeps one identity across a
club transfer, and a swimmer with no account still has aggregations.
"""

import logging
from typing import Any, Optional

from src.core.cache import CacheService
from src.core.database import get_supabase

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 300  # 5 minutes


class MaterializedViewService:
    """Manages the as_daily_aggregations materialized view."""

    def __init__(self, client=None, cache: Optional[CacheService] = None):
        self._client = client
        self._cache = cache

    @property
    def client(self):
        if self._client is None:
            self._client = get_supabase()
        return self._client

    @property
    def cache(self) -> CacheService:
        if self._cache is None:
            self._cache = CacheService()
        return self._cache

    async def refresh(self) -> bool:
        """Trigger an on-demand CONCURRENT refresh via the DB function."""
        try:
            self.client.rpc("refresh_as_daily_aggregations").execute()
            await self.cache.delete_pattern("as_daily_aggregations*")
            logger.info("Refreshed materialized view as_daily_aggregations")
            return True
        except Exception as exc:
            logger.error("Failed to refresh as_daily_aggregations: %s", exc)
            return False

    async def get_athlete_aggregations(
        self, person_id: str, force_refresh: bool = False
    ) -> list[dict[str, Any]]:
        """Read cached aggregations for one person; refresh on cache miss."""
        cache_key = f"as_daily_aggregations:{person_id}"
        if not force_refresh:
            cached = await self.cache.get_json(cache_key)
            if cached is not None:
                return cached.get("rows", [])

        rows = self._query_person(person_id)
        if not rows:
            # On-demand refresh per research decision, then retry once.
            await self.refresh()
            rows = self._query_person(person_id)

        await self.cache.set_json(cache_key, {"rows": rows}, ttl=CACHE_TTL_SECONDS)
        return rows

    def _query_person(self, person_id: str) -> list[dict[str, Any]]:
        try:
            response = (
                self.client.table("as_daily_aggregations")
                .select("*")
                .eq("person_id", person_id)
                .order("date", desc=False)
                .execute()
            )
            return response.data or []
        except Exception as exc:
            logger.warning("as_daily_aggregations query failed for %s: %s", person_id, exc)
            return []


def get_materialized_view_service() -> MaterializedViewService:
    return MaterializedViewService()
