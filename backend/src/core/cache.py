import redis.asyncio as redis
from typing import Optional, Any, List
import json
import logging
from src.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None


async def get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis_client


async def close_redis_client():
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None


class CacheService:
    def __init__(self, client: redis.Redis = None):
        self._client = client

    async def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = await get_redis_client()
        return self._client

    async def get(self, key: str) -> Optional[str]:
        try:
            client = await self._get_client()
            return await client.get(key)
        except Exception as e:
            logger.warning(f"Cache get error for key {key}: {e}")
            return None

    async def set(self, key: str, value: str, ttl: int = 300) -> bool:
        try:
            client = await self._get_client()
            return await client.setex(key, ttl, value)
        except Exception as e:
            logger.warning(f"Cache set error for key {key}: {e}")
            return False

    async def get_json(self, key: str) -> Optional[dict]:
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return None

    async def set_json(self, key: str, value: dict, ttl: int = 300) -> bool:
        try:
            return await self.set(key, json.dumps(value), ttl)
        except Exception as e:
            logger.warning(f"Cache set_json error for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        try:
            client = await self._get_client()
            return await client.delete(key) > 0
        except Exception as e:
            logger.warning(f"Cache delete error for key {key}: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        try:
            client = await self._get_client()
            keys = await client.keys(pattern)
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Cache delete_pattern error for pattern {pattern}: {e}")
            return 0

    async def exists(self, key: str) -> bool:
        try:
            client = await self._get_client()
            return await client.exists(key) > 0
        except Exception as e:
            logger.warning(f"Cache exists error for key {key}: {e}")
            return False

    async def increment(self, key: str, amount: int = 1, ttl: int = 300) -> int:
        try:
            client = await self._get_client()
            pipe = client.pipeline()
            pipe.incrby(key, amount)
            pipe.expire(key, ttl)
            results = await pipe.execute()
            return results[0]
        except Exception as e:
            logger.warning(f"Cache increment error for key {key}: {e}")
            return 0


async def get_cache_service() -> CacheService:
    return CacheService()