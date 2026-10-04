"""My Journey: the user's own counts, streak, heatmap, patterns and reflection log."""
from __future__ import annotations

from datetime import date, timedelta

from app.page_context import _activity as act

HEAT_STYLE = {
    "none": {
        "cell": "bg-surface-container-low hover:bg-surface-container",
        "num": "text-outline",
        "dot": "bg-outline-variant",
        "label_cls": "text-outline",
        "label": "No activity",
    },
    "learn": {
        "cell": "bg-surface-container hover:bg-surface-container-high",
        "num": "text-on-surface",
        "dot": "bg-secondary-fixed",
        "label_cls": "text-on-surface-variant",
        "label": "Explored",
    },
    "reflect": {
        "cell": "bg-primary/10 hover:bg-primary/20",
        "num": "text-primary font-bold",
        "dot": "bg-primary",
        "label_cls": "text-primary",
        "label": "Paused",
    },
    "check": {
        "cell": "bg-tertiary-fixed/30 hover:bg-tertiary-fixed/50",
        "num": "text-tertiary font-semibold",
        "dot": "bg-tertiary",
        "label_cls": "text-tertiary",
        "label": "Checked",
    },
    "future": {
        "cell": "bg-surface-container-low opacity-40",
        "num": "text-outline",
        "dot": "bg-transparent",
        "label_cls": "text-outline",
        "label": "",
    },
}


def _log(sessions) -> list[dict]:
    rows = []
    for s in sessions[:5]:
        labels = [
            {"name": name, "label": getattr(s, key), "chip": act.LABEL_CHIP.get(getattr(s, key), act.NOT_SET_CHIP)}
            for key, name in act.DIMENSIONS
            if getattr(s, key)
        ]
        needs_review = any(
            l["label"] in ("Needs Review", "Present") for l in labels
        )
        rows.append(
            {
                "summary": act.snippet(s.summary, 260),
                "when": act.time_ago(s.completed_at),
                "date": act.aware(s.completed_at).astimezone().strftime("%d %b %Y"),
                "labels": labels,
                "dot": "bg-secondary" if needs_review else "bg-tertiary",
                "pause_minutes": round((s.pause_seconds or 0) / 60, 1) if s.pause_completed else None,
                "linked_check": s.analysis_id is not None,
            }
        )
    return rows


def build(db, user) -> dict:
    c = act.counts(db, user)
    sessions = act.completed_reflections(db, user)
    today = date.today()
    days = act.activity_by_day(db, user, today - timedelta(days=400))
    cells = act.heatmap(days, today)
    for cell in cells:
        cell.update(HEAT_STYLE[cell["kind"]])
    all_badges = act.badges(c)
    created = act.aware(user.created_at)
    return {
        "journey": {
            "counts": c,
            "member_since": created.astimezone().strftime("%d %b %Y") if created else "",
            "resilience_score": act.resilience_score(sessions),
            "streak": act.streak(days, today),
            "active_days_28": sum(1 for cell in cells if cell["kind"] not in ("none", "future")),
            "heatmap": cells,
            "patterns": act.dimension_patterns(sessions),
            "log": _log(sessions),
            "badges": all_badges,
            "badges_earned": sum(1 for b in all_badges if b["earned"]),
        }
    }
