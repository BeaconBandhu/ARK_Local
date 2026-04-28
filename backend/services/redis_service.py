"""Redis service — caching, pub/sub, offline sync queue.

Falls back to an in-memory store automatically when Redis is not reachable.
This lets the backend run on a laptop without Redis installed.
"""

import json
import logging
import os
from collections import defaultdict, deque

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SESSION_KEY = "echo:session:students"
SYNC_QUEUE = "echo:sync_queue"
PUBSUB_CHANNEL = "echo:updates"
OBSIDIAN_CACHE_PREFIX = "echo:obsidian:"


class _MemoryFallback:
    """In-process dict store used when Redis is unavailable."""

    def __init__(self):
        self._hashes: dict[str, dict[str, str]] = defaultdict(dict)
        self._lists: dict[str, deque] = defaultdict(deque)
        self._kv: dict[str, str] = {}

    async def ping(self): return True

    async def hset(self, name, key, value): self._hashes[name][key] = value
    async def hgetall(self, name): return dict(self._hashes[name])
    async def delete(self, name): self._hashes.pop(name, None); self._lists.pop(name, None); self._kv.pop(name, None)

    async def rpush(self, name, value): self._lists[name].append(value)
    async def lpop(self, name):
        q = self._lists[name]
        return q.popleft() if q else None
    async def llen(self, name): return len(self._lists[name])

    async def setex(self, name, ttl, value): self._kv[name] = value
    async def get(self, name): return self._kv.get(name)

    async def publish(self, channel, message): pass  # no-op in memory mode

    def pubsub(self): return _NullPubSub()

    async def aclose(self): pass


class _NullPubSub:
    async def subscribe(self, *args): pass
    async def get_message(self, *args, **kwargs): return None


class RedisService:
    def __init__(self):
        self._redis = None
        self._using_fallback = False

    @property
    def redis(self):
        return self._redis

    async def connect(self):
        try:
            client = await aioredis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
            await client.ping()
            self._redis = client
            self._using_fallback = False
            logger.info("Redis connected: %s", REDIS_URL)
        except Exception as e:
            logger.warning("Redis unavailable (%s) — using in-memory fallback. Data will not persist across restarts.", e)
            self._redis = _MemoryFallback()
            self._using_fallback = True

    async def close(self):
        if self._redis:
            await self._redis.aclose()

    async def is_available(self) -> bool:
        if self._using_fallback:
            return False
        try:
            return bool(await self._redis.ping())
        except Exception:
            return False

    # --- Student session data ---

    async def save_student_result(self, result: dict) -> None:
        sid = result.get("student_id", "unknown")
        await self._redis.hset(SESSION_KEY, sid, json.dumps(result))
        await self._redis.publish(PUBSUB_CHANNEL, json.dumps({"type": "new_result", "data": result}))

    async def get_all_students(self) -> list[dict]:
        raw = await self._redis.hgetall(SESSION_KEY)
        return [json.loads(v) for v in raw.values()]

    async def clear_session(self) -> None:
        await self._redis.delete(SESSION_KEY)

    # --- Offline sync queue (mobile → mongo) ---

    async def enqueue_for_sync(self, result: dict) -> None:
        await self._redis.rpush(SYNC_QUEUE, json.dumps(result))

    async def dequeue_all_for_sync(self) -> list[dict]:
        items = []
        while True:
            raw = await self._redis.lpop(SYNC_QUEUE)
            if raw is None:
                break
            try:
                items.append(json.loads(raw))
            except Exception:
                pass
        return items

    async def queue_length(self) -> int:
        return await self._redis.llen(SYNC_QUEUE)

    # --- Fingerprint cache ---

    async def get_cached_fingerprint(self, key: str) -> dict | None:
        raw = await self._redis.get(f"echo:fp:{key}")
        return json.loads(raw) if raw else None

    async def cache_fingerprint(self, key: str, data: dict, ttl: int = 86400) -> None:
        await self._redis.setex(f"echo:fp:{key}", ttl, json.dumps(data))

    # --- Obsidian vault cache ---

    async def cache_vault_chunk(self, chunk_id: str, text: str, ttl: int = 3600) -> None:
        await self._redis.setex(f"{OBSIDIAN_CACHE_PREFIX}{chunk_id}", ttl, text)

    async def get_vault_chunk(self, chunk_id: str) -> str | None:
        return await self._redis.get(f"{OBSIDIAN_CACHE_PREFIX}{chunk_id}")

    # --- Pub/Sub ---

    async def subscribe_updates(self):
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(PUBSUB_CHANNEL)
        return pubsub
