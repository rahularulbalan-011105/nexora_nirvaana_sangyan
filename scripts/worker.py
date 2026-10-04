"""Run an RQ worker for NIRVAAN background jobs (batch analysis etc.).

    .venv/Scripts/python.exe scripts/worker.py          # Windows
    .venv/bin/python scripts/worker.py                  # Linux / macOS
    python scripts/worker.py --burst                    # drain the queue, then exit

Requires REDIS_URL in .env and ``pip install -r requirements-redis.txt``.

Uses ``SimpleWorker`` (runs each job in this process, no ``fork``) with a
timer-based timeout, so it works on Windows as well as Linux. Run several
of these for more throughput.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--burst", action="store_true", help="exit when the queue is empty")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    from app.config import settings
    from app.services import jobs, redis_client

    if not settings.redis_url:
        print("REDIS_URL is not set - jobs run in-process in the web server; no worker needed.")
        return 1
    client = redis_client.get_redis()
    if client is None:
        print("Redis is not reachable at REDIS_URL - start Redis and try again.")
        return 1
    try:
        from rq import Queue, SimpleWorker
        from rq.timeouts import TimerDeathPenalty
    except ImportError:
        print("rq is not installed: python -m pip install -r requirements-redis.txt")
        return 1

    class NirvaanWorker(SimpleWorker):
        death_penalty_class = TimerDeathPenalty  # SIGALRM does not exist on Windows

    worker = NirvaanWorker([Queue(jobs.QUEUE_NAME, connection=client)], connection=client)
    worker.work(burst=args.burst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
