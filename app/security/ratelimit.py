"""Rate limiters.

``RateLimiter`` is the in-process sliding window: a per-key deque of hit
timestamps. Correct for one process, and the dev default.

``RedisRateLimiter`` keeps the same interface (``check``/``reset``/``prune``)
but counts hits in Redis, so every uvicorn worker shares one budget. It uses
an atomic fixed window (``INCR`` + ``EXPIRE`` in one transaction) keyed by
limiter name, client key and window number. Whenever Redis is not configured
or errors, it transparently uses an embedded ``RateLimiter`` instead - a
limit is always enforced, at worst per process.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque

from fastapi import Request

log = logging.getLogger("nirvaan.ratelimit")


class RateLimiter:
    def __init__(self, *, limit: int, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """Record a hit. Returns ``(allowed, retry_after_seconds)``."""
        now = time.monotonic()
        cutoff = now - self.window

        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()

            if len(bucket) >= self.limit:
                retry_after = max(1, int(self.window - (now - bucket[0])) + 1)
                return False, retry_after

            bucket.append(now)
            return True, 0

    def reset(self, key: str) -> None:
        """Clear a key - called after a successful login."""
        with self._lock:
            self._hits.pop(key, None)

    def prune(self) -> int:
        """Drop empty buckets so the dict does not grow without bound."""
        cutoff = time.monotonic() - self.window
        removed = 0
        with self._lock:
            for key in list(self._hits):
                bucket = self._hits[key]
                while bucket and bucket[0] < cutoff:
                    bucket.popleft()
                if not bucket:
                    del self._hits[key]
                    removed += 1
        return removed


class RedisRateLimiter:
    """Shared fixed-window limiter with an in-memory fallback.

    A fixed window can admit up to ``2 * limit`` hits across a window
    boundary; for login/API throttling that trade is fine and keeps the
    operation a single atomic round trip.
    """

    PREFIX = "nirvaan:rl"

    def __init__(
        self, name: str, *, limit: int, window_seconds: int = 60, redis_factory=None
    ) -> None:
        self.name = name
        self.limit = limit
        self.window = window_seconds
        self.fallback = RateLimiter(limit=limit, window_seconds=window_seconds)
        if redis_factory is None:
            from app.services.redis_client import get_redis

            redis_factory = get_redis
        self._redis = redis_factory

    def _key(self, key: str, slot: int) -> str:
        return f"{self.PREFIX}:{self.name}:{key}:{slot}"

    @property
    def backend(self) -> str:
        return "redis" if self._redis() is not None else "memory"

    def check(self, key: str) -> tuple[bool, int]:
        client = self._redis()
        if client is None:
            return self.fallback.check(key)
        now = time.time()
        slot = int(now // self.window)
        rkey = self._key(key, slot)
        try:
            pipe = client.pipeline(transaction=True)
            pipe.incr(rkey)
            pipe.expire(rkey, self.window + 1)
            count = int(pipe.execute()[0])
        except Exception as exc:  # noqa: BLE001 - Redis trouble must not 500
            _redis_failed(exc)
            return self.fallback.check(key)
        if count > self.limit:
            retry_after = max(1, int((slot + 1) * self.window - now) + 1)
            return False, retry_after
        return True, 0

    def reset(self, key: str) -> None:
        self.fallback.reset(key)
        client = self._redis()
        if client is None:
            return
        slot = int(time.time() // self.window)
        try:
            client.delete(self._key(key, slot), self._key(key, slot - 1))
        except Exception as exc:  # noqa: BLE001
            _redis_failed(exc)

    def prune(self) -> int:
        # Redis keys expire on their own; only the fallback needs pruning.
        return self.fallback.prune()


def _redis_failed(exc: BaseException) -> None:
    try:
        from app.services.redis_client import mark_down

        mark_down(exc)
    except Exception:  # noqa: BLE001
        log.warning("rate limiter: Redis error %s", exc)


def client_key(request: Request, prefix: str = "") -> str:
    """Identify the caller.

    Honours ``X-Forwarded-For`` only for its first hop, which is what a single
    trusted reverse proxy sets. Without a proxy this is the socket address.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"
    return f"{prefix}:{ip}" if prefix else ip
