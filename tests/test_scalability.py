"""Redis-backed scalability layer: limiter, cache, job queue - and their fallbacks."""
from __future__ import annotations

import threading
import time

import pytest

fakeredis = pytest.importorskip("fakeredis")

from app.security.ratelimit import RateLimiter, RedisRateLimiter  # noqa: E402
from app.services import cache, jobs, redis_client  # noqa: E402


class _DeadRedis:
    """A client whose every call fails, as if Redis went away mid-flight."""

    def __getattr__(self, name):
        def boom(*args, **kwargs):
            raise ConnectionError("redis down")

        return boom


@pytest.fixture
def fake():
    client = fakeredis.FakeRedis()
    redis_client.use_client(client)
    cache.clear_memory()
    yield client
    redis_client.use_client(None)
    cache.clear_memory()


@pytest.fixture
def no_redis():
    redis_client.use_client(None)
    cache.clear_memory()
    yield
    cache.clear_memory()


# -- rate limiting -----------------------------------------------------------

def test_redis_limiter_is_shared_between_workers(fake):
    # Two instances = two uvicorn workers; one budget in Redis.
    worker_a = RedisRateLimiter("login", limit=3, window_seconds=60)
    worker_b = RedisRateLimiter("login", limit=3, window_seconds=60)
    assert worker_a.backend == "redis"

    assert worker_a.check("ip1") == (True, 0)
    assert worker_b.check("ip1") == (True, 0)
    assert worker_a.check("ip1") == (True, 0)
    allowed, retry = worker_b.check("ip1")
    assert not allowed and 1 <= retry <= 61
    # Other clients and other limiter names are unaffected.
    assert worker_a.check("ip2")[0]
    assert RedisRateLimiter("api", limit=3).check("ip1")[0]

    worker_a.reset("ip1")
    assert worker_b.check("ip1")[0]


def test_limiter_falls_back_to_memory_without_redis(no_redis):
    limiter = RedisRateLimiter("login", limit=2, window_seconds=60)
    assert limiter.backend == "memory"
    assert limiter.check("k")[0] and limiter.check("k")[0]
    assert not limiter.check("k")[0]


def test_limiter_falls_back_when_redis_errors():
    limiter = RedisRateLimiter(
        "login", limit=2, window_seconds=60, redis_factory=lambda: _DeadRedis()
    )
    assert limiter.check("k")[0] and limiter.check("k")[0]
    assert not limiter.check("k")[0]  # still enforced, per process


def test_in_memory_limiter_unchanged():
    limiter = RateLimiter(limit=1, window_seconds=60)
    assert limiter.check("x") == (True, 0)
    assert not limiter.check("x")[0]


def test_unreachable_redis_url_does_not_hang(monkeypatch):
    redis_client.use_client(None)
    monkeypatch.setattr(redis_client.settings, "redis_url", "redis://127.0.0.1:1/0")
    try:
        started = time.monotonic()
        assert redis_client.get_redis() is None
        assert redis_client.get_redis() is None  # cached failure: no re-dial
        assert time.monotonic() - started < 5
        assert redis_client.status()["backend"] == "memory"
    finally:
        redis_client.use_client(None)


# -- cache -------------------------------------------------------------------

@pytest.mark.parametrize("backend", ["redis", "memory"])
def test_cache_roundtrip_and_ttl(backend, request):
    request.getfixturevalue("fake" if backend == "redis" else "no_redis")
    assert cache.backend() == backend

    cache.set("t:k", {"a": [1, "२"]}, ttl=60)
    assert cache.get("t:k") == {"a": [1, "२"]}
    cache.delete("t:k")
    assert cache.get("t:k") is None

    cache.set("t:short", "v", ttl=1)
    assert cache.get("t:short") == "v"
    time.sleep(1.2)
    assert cache.get("t:short") is None


def test_cache_counts_hits_and_misses(fake):
    cache.get("t:none", stat="talk")
    cache.set("t:yes", 1)
    cache.get("t:yes", stat="talk")
    assert cache.stats() == {"talk:miss": 1, "talk:hit": 1}


def test_cache_survives_redis_errors(no_redis):
    redis_client.use_client(_DeadRedis())
    try:
        cache.set("t:x", 5)
        assert cache.get("t:x") == 5  # served by the memory fallback
    finally:
        redis_client.use_client(None)


def test_provider_health_is_shared_via_cache(fake):
    from app.services.ai.registry import ProviderRegistry

    ProviderRegistry(order=["local"]).health("local")
    assert fake.get(cache.PREFIX + "ai:health:local") is not None


# -- talk answer cache key ---------------------------------------------------

def test_talk_cache_key_skips_personal_and_credential_input():
    from app.services import responsible_ai as rai
    from app.services.talk import _cache_key

    general = _cache_key(rai.check_input("What is a mutual fund?", language="en"), "en")
    assert general and general.startswith("talk:answer:")
    assert general != _cache_key(rai.check_input("What is a mutual fund?", language="hi"), "hi")
    assert _cache_key(rai.check_input("What should I do with my savings?", language="en"), "en") is None
    assert _cache_key(rai.check_input("my OTP is 482913, is that ok", language="en"), "en") is None


# -- jobs --------------------------------------------------------------------

_done = threading.Event()
_seen: list = []


def record(value):
    _seen.append(value)
    _done.set()


def test_jobs_use_thread_pool_without_redis(no_redis):
    _done.clear()
    _seen.clear()
    assert jobs.enqueue("tests.test_scalability:record", 7) == "thread"
    assert _done.wait(5)
    assert _seen == [7]
    assert jobs.status()["backend"] == "thread"


def test_jobs_run_in_process_when_no_rq_worker(fake, monkeypatch):
    pytest.importorskip("rq")
    monkeypatch.setattr(jobs, "_has_workers", lambda queue: False)
    _seen.clear()
    assert jobs.enqueue("tests.test_scalability:record", 7) == "thread"
    import time
    for _ in range(50):
        if _seen:
            break
        time.sleep(0.02)
    assert _seen == [7]


def test_jobs_use_rq_when_redis_available(fake, monkeypatch):
    pytest.importorskip("rq")
    from rq import Queue, SimpleWorker
    from rq.timeouts import TimerDeathPenalty

    monkeypatch.setattr(jobs, "_has_workers", lambda queue: True)
    _seen.clear()
    assert jobs.enqueue("tests.test_scalability:record", 42) == "rq"
    queue = Queue(jobs.QUEUE_NAME, connection=fake)
    assert queue.count == 1
    assert jobs.status() == {"backend": "rq", "queue": "nirvaan", "queued": 1}

    class Worker(SimpleWorker):
        death_penalty_class = TimerDeathPenalty

    Worker([queue], connection=fake).work(burst=True)
    assert _seen == [42]
    assert queue.count == 0


def test_jobs_fall_back_when_rq_enqueue_fails(no_redis):
    redis_client.use_client(_DeadRedis())
    try:
        _done.clear()
        _seen.clear()
        assert jobs.enqueue("tests.test_scalability:record", 9) == "thread"
        assert _done.wait(5)
        assert _seen == [9]
    finally:
        redis_client.use_client(None)


# -- talk answer cache + admin usage ------------------------------------------

def test_talk_reuses_cached_model_answer_and_admin_counts_it(seeded, db, make_user, fake, monkeypatch):
    from app.page_context.admin import _ai_usage
    from app.services import talk
    from app.services.ai.base import Completion

    calls: list = []

    def fake_complete(messages, **kwargs):
        calls.append(messages)
        return Completion(
            text="A mutual fund pools money from many investors.", provider="ollama", latency_ms=5
        )

    monkeypatch.setattr(talk.registry, "complete", fake_complete)
    user = make_user(email="cache-talk@test.local")

    first = talk.respond(db, user, "What is a mutual fund?", "en")
    second = talk.respond(db, user, "what is a  mutual fund?", "en")
    assert len(calls) == 1
    assert second.reply == first.reply and second.provider == "ollama"

    talk.respond(db, user, "Explain how my SIP works", "en")  # personal: no cache
    assert len(calls) == 2
    db.commit()

    usage = _ai_usage(db)
    names = {p["name"]: p for p in usage["providers"]}
    assert names["ollama"]["week"] >= 2 and names["cache"]["week"] >= 1
    assert usage["cache_hits"] >= 1 and usage["cache_backend"] == "redis"
