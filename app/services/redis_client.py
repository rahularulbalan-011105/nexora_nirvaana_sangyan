"""Optional Redis connection shared by the rate limiter, cache and job queue.

``get_redis()`` returns a live client or ``None``. ``None`` means "use the
in-process fallback" and is the normal answer in development, where
``REDIS_URL`` is empty.

Rules:
* never block a request for long - connect/socket timeouts are short;
* a failed connection is remembered for ``RETRY_SECONDS`` so a dead Redis is
  not re-dialled on every request;
* failures are logged once per outage, not once per request;
* callers that hit an error mid-operation call ``mark_down()`` and fall back.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

from app.config import settings

log = logging.getLogger("nirvaan.redis")

RETRY_SECONDS = 30
CONNECT_TIMEOUT = 0.5
SOCKET_TIMEOUT = 1.0

_lock = threading.Lock()
_client: Any = None
_down_until = 0.0
_warned = False
_override: Any = None  # tests inject a fakeredis client here


def _url() -> str:
    return (settings.redis_url or "").strip()


def configured() -> bool:
    return _override is not None or bool(_url())


def get_redis() -> Any | None:
    """A connected client, or ``None`` when Redis is off or unreachable."""
    global _client, _down_until, _warned
    if _override is not None:
        return _override
    url = _url()
    if not url:
        return None
    if _client is not None:
        return _client
    if time.monotonic() < _down_until:
        return None

    with _lock:
        if _client is not None:
            return _client
        if time.monotonic() < _down_until:
            return None
        try:
            import redis  # optional dependency (requirements-redis.txt)

            client = redis.Redis.from_url(
                url,
                socket_connect_timeout=CONNECT_TIMEOUT,
                socket_timeout=SOCKET_TIMEOUT,
                health_check_interval=30,
            )
            client.ping()
        except Exception as exc:  # noqa: BLE001 - any failure means "fall back"
            _down_until = time.monotonic() + RETRY_SECONDS
            if not _warned:
                log.warning(
                    "Redis unavailable (%s); using in-process fallbacks, retry in %ss",
                    exc, RETRY_SECONDS,
                )
                _warned = True
            return None
        if _warned:
            log.info("Redis reachable again at %s", _safe_url(url))
        _warned = False
        _client = client
        return _client


def mark_down(exc: BaseException | None = None) -> None:
    """Forget the client after a runtime error and back off before retrying."""
    global _client, _down_until, _warned
    if _override is not None:
        return
    with _lock:
        _client = None
        _down_until = time.monotonic() + RETRY_SECONDS
        if not _warned:
            log.warning("Redis error (%s); falling back to in-process state", exc)
            _warned = True


def status() -> dict[str, object]:
    """Small dict for /api/health and the admin console."""
    client = get_redis()
    reachable = False
    if client is not None:
        try:
            reachable = bool(client.ping())
        except Exception as exc:  # noqa: BLE001
            mark_down(exc)
    return {
        "backend": "redis" if reachable else "memory",
        "configured": configured(),
        "reachable": reachable,
    }


def use_client(client: Any | None) -> None:
    """Test hook: force a specific client (e.g. fakeredis), or clear it."""
    global _override, _client, _down_until, _warned
    with _lock:
        _override = client
        _client = None
        _down_until = 0.0
        _warned = False


def _safe_url(url: str) -> str:
    """Strip credentials before logging."""
    if "@" in url:
        scheme, _, rest = url.partition("://")
        return f"{scheme}://***@{rest.split('@', 1)[1]}"
    return url
