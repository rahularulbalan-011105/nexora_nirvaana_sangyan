"""Background job queue.

One call site for every deferred task::

    from app.services import jobs
    jobs.enqueue("app.services.batch:process_job", job_id)

The target is given as an importable "module:function" string so it can be
handed to an out-of-process worker.

Backends, chosen per call:

* **RQ** - when Redis is reachable (``REDIS_URL``) and ``rq`` is installed,
  the job goes onto the ``nirvaan`` RQ queue and is run by
  ``python scripts/worker.py`` (any number of workers, any host). Jobs then
  survive a web-worker restart and do not compete with requests for CPU.
* **thread** - otherwise, an in-process thread pool (the dev default). If
  RQ enqueueing fails, the job falls back to the pool rather than being lost.

Without a running worker, RQ jobs wait in Redis until one starts - so only
set ``REDIS_URL`` in deployments that also run the worker.
"""
from __future__ import annotations

import importlib
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.services import redis_client

log = logging.getLogger("nirvaan.jobs")

QUEUE_NAME = "nirvaan"
JOB_TIMEOUT_SECONDS = 15 * 60

_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="nirvaan-job")


def resolve(target: str):
    module_name, func_name = target.split(":", 1)
    return getattr(importlib.import_module(module_name), func_name)


def _run(target: str, args: tuple[Any, ...]) -> None:
    try:
        resolve(target)(*args)
    except Exception:  # noqa: BLE001 - a job failure must never kill the worker
        log.exception("job %s failed", target)


def run_target(target: str, *args: Any) -> None:
    """Worker shim: what RQ actually executes (``app.services.jobs.run_target``).

    Resolving the "module:function" string inside the worker keeps the queue
    payload a plain string plus arguments, and lets a failure be logged the
    same way as on the thread pool. Exceptions are re-raised so RQ records
    the job as failed.
    """
    resolve(target)(*args)


def _rq_queue():
    """The RQ queue, or None when Redis/rq are unavailable."""
    client = redis_client.get_redis()
    if client is None:
        return None
    try:
        from rq import Queue
    except ImportError:
        return None
    return Queue(QUEUE_NAME, connection=client)


def backend() -> str:
    return "rq" if _rq_queue() is not None else "thread"


def _has_workers(queue) -> bool:
    try:
        from rq import Worker

        return Worker.count(queue=queue) > 0
    except Exception:  # noqa: BLE001 - if we cannot tell, trust the queue
        return True


def enqueue(target: str, *args: Any) -> str:
    """Schedule ``target(*args)``. Returns a backend label ("rq" or "thread")."""
    queue = _rq_queue()
    if queue is not None and not _has_workers(queue):
        # Redis is up but nobody is consuming the queue: don't strand the job.
        log.warning("no RQ worker is running; running %s in-process", target)
        queue = None
    if queue is not None:
        try:
            queue.enqueue(run_target, target, *args, job_timeout=JOB_TIMEOUT_SECONDS)
            return "rq"
        except Exception as exc:  # noqa: BLE001 - never lose a job to a Redis blip
            redis_client.mark_down(exc)
            log.warning("RQ enqueue of %s failed (%s); running in-process", target, exc)
    _pool.submit(_run, target, args)
    return "thread"


def status() -> dict[str, object]:
    """Queue backend and depth for /api/health."""
    queue = _rq_queue()
    if queue is None:
        return {"backend": "thread", "queued": None}
    try:
        return {"backend": "rq", "queue": QUEUE_NAME, "queued": queue.count}
    except Exception as exc:  # noqa: BLE001
        redis_client.mark_down(exc)
        return {"backend": "thread", "queued": None}
