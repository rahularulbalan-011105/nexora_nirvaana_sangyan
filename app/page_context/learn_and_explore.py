"""Learn & Explore: lessons plus the signed-in user's own learning progress.

Lesson content is shared by everyone; progress rows are always filtered to
``user.id``. A brand-new account therefore sees zero progress, not a mockup.
``build`` does not know the page language, so lesson cards are prepared for
every supported language and the template picks ``lang_code``.
"""
from __future__ import annotations

from app.services import learning_content as lc
from app.services import learning_progress as lp

# Each structured path on the page groups real LearningContent categories.
PATHS: dict[str, tuple[str, ...]] = {
    "foundation": ("basics", "mutual-funds", "market-concepts", "risk-volatility"),
    "scams": ("scams", "digital-safety", "investor-rights"),
    "habits": ("budgeting",),
}

RING_CIRCUMFERENCE = 125.6


def _path_summary(total: int, completed: int, started: int) -> dict:
    percent = round(completed * 100 / total) if total else 0
    if total and completed >= total:
        status = "completed"
    elif completed or started:
        status = "in_progress"
    else:
        status = "not_started"
    return {
        "total": total,
        "completed": completed,
        "percent": percent,
        "status": status,
        "dashoffset": round(RING_CIRCUMFERENCE * (1 - percent / 100), 2),
    }


def build(db, user) -> dict:
    lessons = [c for c in lp.published_lessons(db) if c.slug in lc.LESSONS]
    prog = lp.progress_map(db, user)
    progress_of = {c.id: lp.progress_dict(prog.get(c.id)) for c in lessons}

    completed_ids = {cid for cid, p in progress_of.items() if p["complete"]}
    started_ids = {
        cid for cid, p in progress_of.items() if not p["complete"] and p["percent"] > 0
    }

    paths = {}
    for key, categories in PATHS.items():
        members = [c for c in lessons if c.category in categories]
        ids = {c.id for c in members}
        summary = _path_summary(len(ids), len(ids & completed_ids), len(ids & started_ids))
        # Where the path's button goes: the first lesson not yet completed,
        # or the first lesson when reviewing a completed path.
        target = next((c for c in members if c.id not in completed_ids), None)
        target = target or (members[0] if members else None)
        summary["url"] = f"/learn/{target.slug}" if target else None
        summary["groups"] = sorted({lc.filter_group(cat) for cat in categories})
        paths[key] = summary

    cards_by_lang = {
        lang: [lp.lesson_card(c, lang, progress_of[c.id]) for c in lessons]
        for lang in lc.LANGUAGES
    }
    resume = lp.resume_lesson(db, user)
    resume_by_lang = None
    if resume is not None and resume.slug in lc.LESSONS:
        resume_by_lang = {
            lang: lp.lesson_card(resume, lang, lp.progress_dict(prog.get(resume.id)))
            for lang in lc.LANGUAGES
        }
    # Bookmarked lessons, most recently viewed first.
    saved = sorted(
        (c for c in lessons if progress_of[c.id]["bookmarked"]),
        key=lambda c: (prog[c.id].last_viewed_at.isoformat() if prog.get(c.id) and prog[c.id].last_viewed_at else ""),
        reverse=True,
    )
    saved_by_lang = {
        lang: [lp.lesson_card(c, lang, progress_of[c.id]) for c in saved] for lang in lc.LANGUAGES
    }
    spotlight = {
        lang: lc.lesson_text("what-is-a-mutual-fund", lang) for lang in lc.LANGUAGES
    }

    group_counts: dict[str, int] = {}
    for card in cards_by_lang["en"]:
        group_counts[card["group"]] = group_counts.get(card["group"], 0) + 1

    return {
        "learn": {
            "topics_total": len(lessons),
            "concepts_completed": len(completed_ids),
            "paths_in_progress": sum(
                1 for p in paths.values() if p["status"] == "in_progress"
            ),
            "saved_count": sum(1 for p in progress_of.values() if p["bookmarked"]),
            "paths": paths,
            "cards_by_lang": cards_by_lang,
            "resume_by_lang": resume_by_lang,
            "saved_by_lang": saved_by_lang,
            "spotlight_by_lang": spotlight,
            "group_counts": group_counts,
        }
    }
