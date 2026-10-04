"""Privacy Center: the user's real privacy switches, record counts and family sharing."""
from __future__ import annotations

from app.page_context import _account_data as data
from app.services import account


def build(db, user) -> dict:
    links = data.family_links(db, user)
    # Guardians are assistants on relationships this user owns.
    guardians = [l for l in links if l["role"] == "assistant" and l["status"] == "active"]
    return {
        "record_counts": data.record_counts(db, user),
        "history_counts": account.history_counts(db, user),
        "memories": [
            {"id": str(m.id), "content": m.content, "created": data.fmt_date(m.created_at)}
            for m in account.list_memories(db, user)
        ],
        "guardian_count": len(guardians),
        "guardian_permission_count": sum(len(g["scopes"]) for g in guardians),
    }
