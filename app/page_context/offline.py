"""Offline Mode: what is actually available offline for this user."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.models.learning import LearningContent
from app.models.market import MarketDataCache
from app.page_context import _account_data as data


def build(db, user) -> dict:
    prefs = user.preferences
    cache_enabled = bool(prefs.offline_cache_enabled) if prefs else True
    where = (LearningContent.published.is_(True), LearningContent.offline_available.is_(True))
    lesson_count = data.count(db, LearningContent, *where) if cache_enabled else 0
    titles = []
    if cache_enabled:
        titles = list(
            db.execute(
                select(LearningContent.title)
                .where(*where, LearningContent.language == (user.language or "en"))
                .order_by(LearningContent.order_index, LearningContent.title)
                .limit(3)
            ).scalars()
        )
        if not titles:
            titles = list(
                db.execute(
                    select(LearningContent.title)
                    .where(*where)
                    .order_by(LearningContent.order_index, LearningContent.title)
                    .limit(3)
                ).scalars()
            )
    market_snapshot = db.execute(select(func.max(MarketDataCache.fetched_at))).scalar()
    return {
        "offline_cache_enabled": cache_enabled,
        "offline_lesson_count": lesson_count,
        "offline_lesson_titles": titles,
        "offline_last_sync": data.fmt_datetime(datetime.now(timezone.utc)),
        "market_snapshot_at": data.fmt_datetime(market_snapshot),
    }
