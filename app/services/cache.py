"""Small shared JSON cache: Redis when available, else an in-process TTL dict.

    from app.services import cache
    cache.set("ai:health:ollama", {"ok": True}, ttl=30)
    cache.get("ai:health:ollama")            # -> {"ok": True} or None
    cache.delete("ai:health:ollama")

Values must be JSON-serialisable. Every call degrades silently to the memory
backend if Redis errors, so a cache problem can never fail a request. Do not
put anything personal in here - it is shared by every worker.

``get(..., stat="talk")`` also counts hits/misses under that label for the
admin console (aggregate numbers only).
"""
from __future__ import annotations

import json
import threading
import time
from collections import Counter
from typing import Any

from app.services import redis_client

PREFIX = "nirvaan:cache:"
STATS_KEY = "nirvaan:stats:cache"
MAX_MEMORY_ITEMS = 2048

_lock = threading.Lock()
_mem: dict[str, tuple[float, str]] = {}
_mem_stats: Counter[str] = Counter()


# -- memory backend ---------------------------------------------------------

def _mem_get(key: str) -> str | None:
    with _lock:
        item = _mem.get(key)
        if item is None:
            return None
        expires, raw = item
        if expires and expires < time.monotonic():
            _mem.pop(key, None)
            return None
        return raw


def _mem_set(key: str, raw: str, ttl: int | None) -> None:
    expires = time.monotonic() + ttl if ttl else 0.0
    with _lock:
        if len(_mem) >= MAX_MEMORY_ITEMS and key not in _mem:
            now = time.monotonic()
            for k in [k for k, (e, _) in _mem.items() if e and e < now]:
                _mem.pop(k, None)
            while len(_mem) >= MAX_MEMORY_ITEMS:
                _mem.pop(next(iter(_mem)))  # oldest insertion
        _mem[key] = (expires, raw)


# -- public API -------------------------------------------------------------

def backend() -> str:
    return "redis" if redis_client.get_redis() is not None else "memory"


def get(key: str, *, stat: str | None = None) -> Any | None:
    raw: str | bytes | None = None
    client = redis_client.get_redis()
    if client is not None:
        try:
            raw = client.get(PREFIX + key)
        except Exception as exc:  # noqa: BLE001
            redis_client.mark_down(exc)
            client = None
    if client is None:
        raw = _mem_get(key)

    value = None
    if raw is not None:
        try:
            value = json.loads(raw)
        except (TypeError, ValueError):
            value = None
    if stat:
        _count(f"{stat}:{'hit' if value is not None else 'miss'}")
    return value


def set(key: str, value: Any, ttl: int | None = 300) -> None:  # noqa: A001
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    client = redis_client.get_redis()
    if client is not None:
        try:
            client.set(PREFIX + key, raw, ex=ttl if ttl else None)
            return
        except Exception as exc:  # noqa: BLE001
            redis_client.mark_down(exc)
    _mem_set(key, raw, ttl)


def delete(key: str) -> None:
    with _lock:
        _mem.pop(key, None)
    client = redis_client.get_redis()
    if client is not None:
        try:
            client.delete(PREFIX + key)
        except Exception as exc:  # noqa: BLE001
            redis_client.mark_down(exc)


def clear_memory() -> None:
    """Test helper: empty the in-process backend and counters."""
    with _lock:
        _mem.clear()
        _mem_stats.clear()


# -- hit/miss counters ------------------------------------------------------

def _count(field: str) -> None:
    client = redis_client.get_redis()
    if client is not None:
        try:
            client.hincrby(STATS_KEY, field, 1)
            return
        except Exception as exc:  # noqa: BLE001
            redis_client.mark_down(exc)
    with _lock:
        _mem_stats[field] += 1


def stats() -> dict[str, int]:
    """Hit/miss counters since start (memory) or since Redis was emptied."""
    client = redis_client.get_redis()
    if client is not None:
        try:
            raw = client.hgetall(STATS_KEY) or {}
            return {
                (k.decode() if isinstance(k, bytes) else k): int(v) for k, v in raw.items()
            }
        except Exception as exc:  # noqa: BLE001
            redis_client.mark_down(exc)
    with _lock:
        return dict(_mem_stats)
