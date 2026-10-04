"""Family Mode: the user's real family links and invitations (either side of the link)."""
from __future__ import annotations

from app.page_context import _account_data as data


def build(db, user) -> dict:
    links = [l for l in data.family_links(db, user) if l["status"] != "revoked"]
    active = [l for l in links if l["status"] == "active"]
    return {
        "family_links": links,
        "family_active": active,
        "family_invites": data.pending_invitations(db, user),
        "family_names": ", ".join(l["first_name"] for l in active),
    }
