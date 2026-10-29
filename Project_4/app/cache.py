import asyncio
import json
import os
from typing import Any, Callable, Optional

import redis.asyncio as redis

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=6379,
    db=0,
    decode_responses=True,
    socket_timeout=2,
)


async def get_json(key: str) -> Optional[Any]:
    try:
        raw = await redis_client.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


async def set_json(key: str, value: Any, ttl: int = 60) -> None:
    try:
        await redis_client.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass


async def invalidate(key: str) -> None:
    try:
        await redis_client.delete(key)
    except Exception:
        pass


async def invalidate_pattern(pattern: str) -> None:
    # SCAN вместо KEYS: не блокирует Redis
    try:
        async for key in redis_client.scan_iter(match=pattern, count=100):
            await redis_client.delete(key)
    except Exception:
        pass


async def cached(key: str, ttl: int, fetch_fn: Callable, lock_timeout: int = 10):
    """Cache-Aside с mutex-защитой от cache stampede."""
    cached_value = await get_json(key)
    if cached_value is not None:
        return cached_value

    lock_key = f"lock:{key}"
    try:
        acquired = await redis_client.set(lock_key, "1", nx=True, ex=lock_timeout)
    except Exception:
        acquired = True

    if not acquired:
        for _ in range(20):
            await asyncio.sleep(0.05)
            cached_value = await get_json(key)
            if cached_value is not None:
                return cached_value

    try:
        value = await fetch_fn()
        if value is not None:
            await set_json(key, value, ttl)
        return value
    finally:
        try:
            await redis_client.delete(lock_key)
        except Exception:
            pass
