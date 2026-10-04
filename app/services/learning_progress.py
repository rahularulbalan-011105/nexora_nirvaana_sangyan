"""Learn & Explore data access: lessons joined with the user's own progress.

Progress is always scoped to ``user.id``. Percent is earned, never invented:
opening a lesson counts as reading its first mode (25%), each further mode
read adds 25% up to 75%, and only an explicit "Mark as complete" sets 100%.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.models.learning import LearningContent, LearningProgress
from app.services import learning_content as lc

PERCENT_PER_MODE = 25
MAX_PERCENT_BEFORE_COMPLETE = 75


def _now() -> datetime:
    return datetime.now(timezone.utc)


def published_lessons(db) -> list[LearningContent]:
    return list(
        db.execute(
            select(LearningContent)
            .where(LearningContent.published.is_(True))
            .order_by(LearningContent.order_index, LearningContent.title)
        ).scalars()
    )


def get_lesson(db, slug: str) -> LearningContent | None:
    return db.execute(
        select(LearningContent).where(
            LearningContent.slug == slug, LearningContent.published.is_(True)
        )
    ).scalar_one_or_none()


def progress_map(db, user) -> dict:
    if user is None:
        return {}
    rows = db.execute(
        select(LearningProgress).where(LearningProgress.user_id == user.id)
    ).scalars()
    return {row.content_id: row for row in rows}


def progress_dict(row: LearningProgress | None) -> dict:
    if row is None:
        return {"percent": 0, "complete": False, "bookmarked": False, "started": False,
                "view_count": 0}
    return {
        "percent": 100 if row.completed_at else int(row.percent or 0),
        "complete": row.completed_at is not None,
        "bookmarked": bool(row.bookmarked),
        "started": bool(row.percent or row.view_count or row.completed_at),
        "view_count": int(row.view_count or 0),
    }


def resume_lesson(db, user) -> LearningContent | None:
    """Most recently viewed lesson the user has not completed."""
    if user is None:
        return None
    return db.execute(
        select(LearningContent)
        .join(LearningProgress, LearningProgress.content_id == LearningContent.id)
        .where(
            LearningProgress.user_id == user.id,
            LearningProgress.completed_at.is_(None),
            LearningProgress.last_viewed_at.is_not(None),
            LearningContent.published.is_(True),
        )
        .order_by(LearningProgress.last_viewed_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _row(db, user, content: LearningContent) -> LearningProgress:
    row = db.execute(
        select(LearningProgress).where(
            LearningProgress.user_id == user.id,
            LearningProgress.content_id == content.id,
        )
    ).scalar_one_or_none()
    if row is None:
        row = LearningProgress(
            user_id=user.id, content_id=content.id, percent=0, view_count=0,
            bookmarked=False,
        )
        db.add(row)
    return row


def record_view(db, user, content: LearningContent) -> LearningProgress:
    row = _row(db, user, content)
    row.view_count = int(row.view_count or 0) + 1
    row.last_viewed_at = _now()
    if row.completed_at is None:
        row.percent = max(int(row.percent or 0), PERCENT_PER_MODE)
    db.commit()
    return row


def record_modes(db, user, content: LearningContent, modes_seen: int) -> LearningProgress:
    row = _row(db, user, content)
    row.last_viewed_at = _now()
    if row.completed_at is None:
        earned = min(max(int(modes_seen), 1) * PERCENT_PER_MODE, MAX_PERCENT_BEFORE_COMPLETE)
        row.percent = max(int(row.percent or 0), earned)
    db.commit()
    return row


def mark_complete(db, user, content: LearningContent) -> LearningProgress:
    row = _row(db, user, content)
    row.last_viewed_at = _now()
    row.percent = 100
    if row.completed_at is None:
        row.completed_at = _now()
    db.commit()
    return row


def set_bookmark(db, user, content: LearningContent, value: bool) -> LearningProgress:
    row = _row(db, user, content)
    row.bookmarked = bool(value)
    db.commit()
    return row


def lesson_card(content: LearningContent, language: str, progress: dict) -> dict:
    text = lc.lesson_text(content.slug, language) or {}
    return {
        "slug": content.slug,
        "url": f"/learn/{content.slug}",
        "category": content.category,
        "group": lc.filter_group(content.category),
        "icon": content.icon or "school",
        "reading_minutes": content.reading_minutes or 3,
        "difficulty": content.difficulty or "beginner",
        "title": text.get("title") or content.title,
        "summary": text.get("summary") or content.summary,
        "progress": progress,
    }


def module_context(db, user, slug: str, language: str) -> dict | None:
    """Everything the lesson page needs, in one language."""
    content = get_lesson(db, slug)
    if content is None or slug not in lc.LESSONS:
        return None
    lessons = [c for c in published_lessons(db) if c.slug in lc.LESSONS]
    index = next(i for i, c in enumerate(lessons) if c.slug == slug)
    prev_c = lessons[index - 1] if index > 0 else None
    next_c = lessons[index + 1] if index + 1 < len(lessons) else None
    prog = progress_map(db, user)
    text = lc.lesson_text(slug, language)
    return {
        "module": {
            "slug": slug,
            "category": content.category,
            "group": lc.filter_group(content.category),
            "icon": content.icon or "school",
            "reading_minutes": content.reading_minutes or 3,
            "difficulty": content.difficulty or "beginner",
            "title": text["title"],
            "summary": text["summary"],
            "modes": {m: [p for p in text[m].split("\n\n") if p.strip()] for m in lc.MODES},
            "resources": lc.resources_for(slug, language),
            "speech_lang": lc.SPEECH_LANG.get(language, "en-IN"),
            "language": language,
            "position": index + 1,
            "count": len(lessons),
        },
        "module_progress": progress_dict(prog.get(content.id)),
        "prev_module": lesson_card(prev_c, language, {}) if prev_c else None,
        "next_module": lesson_card(next_c, language, {}) if next_c else None,
    }
