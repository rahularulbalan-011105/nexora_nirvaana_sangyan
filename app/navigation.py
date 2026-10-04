"""Sidebar navigation definition.

The labels, icons and ordering are taken verbatim from the Stitch sidebar so
the rendered markup matches the design. ``roles`` gates visibility in the
template; it is cosmetic only - the route still enforces authorization.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import Role

# Class strings lifted exactly from the Stitch export so the active and
# inactive states render identically to the design.
NAV_ACTIVE_CLASS = (
    "flex items-center gap-space-sm px-space-md py-2.5 rounded-xl transition-all "
    "bg-primary-container text-on-primary-container font-semibold "
    "shadow-[0_4px_12px_-2px_rgba(37,99,235,0.18)]"
)
NAV_INACTIVE_CLASS = (
    "flex items-center gap-space-sm px-space-md py-2.5 rounded-xl "
    "text-on-surface-variant hover:bg-surface-container hover:text-on-surface "
    "transition-all"
)


@dataclass(frozen=True)
class NavItem:
    key: str
    label: str
    icon: str
    url: str
    roles: tuple[str, ...] = ()
    divider_before: bool = False

    def visible_to(self, user) -> bool:
        if not self.roles:
            return True
        if user is None:
            return False
        return bool(user.role_names & set(self.roles))


NAV_ITEMS: tuple[NavItem, ...] = (
    NavItem("dashboard", "Home / Dashboard", "grid_view", "/dashboard"),
    NavItem("talk-to-nirvaan", "Talk to NIRVAAN", "mic", "/talk"),
    NavItem("check-a-message", "Check a Message", "document_scanner", "/check"),
    NavItem("batch", "Batch Analysis", "library_books", "/batch"),
    NavItem("pause-and-reflect", "Pause & Reflect", "self_improvement", "/reflect"),
    NavItem("learn-and-explore", "Learn & Explore", "explore", "/learn"),
    NavItem("my-journey", "My Journey", "trending_up", "/journey"),
    NavItem("family-mode", "Family Mode", "supervised_user_circle", "/family"),
    NavItem("privacy-center", "Privacy Center", "lock_reset", "/privacy", divider_before=True),
    NavItem("settings", "Settings", "tune", "/settings"),
    NavItem("help-and-support", "Help & Support", "support_agent", "/help"),
    NavItem(
        "admin",
        "Admin Console",
        "admin_panel_settings",
        "/admin",
        roles=(Role.ADMIN.value,),
        divider_before=True,
    ),
)

# Breadcrumb text shown in the top bar, keyed by nav key.
BREADCRUMBS: dict[str, str] = {
    "dashboard": "Resilience Portal",
    "talk-to-nirvaan": "Voice Companion",
    "check-a-message": "Message Safety Check",
    "pause-and-reflect": "Pause & Reflect",
    "learn-and-explore": "Learn & Explore",
    "my-journey": "My Journey",
    "family-mode": "Family Mode",
    "privacy-center": "Privacy Center",
    "settings": "Profile & Settings",
    "help-and-support": "Help & Support",
    "admin": "Admin Console",
    "batch": "Batch Analysis",
    "decision-readiness": "Decision Readiness",
    "explain-simply": "Explain Simply",
    "offline": "Offline Mode",
}


def items_for(user) -> list[NavItem]:
    return [item for item in NAV_ITEMS if item.visible_to(user)]


def breadcrumb_for(key: str) -> str:
    return BREADCRUMBS.get(key, "Resilience Portal")
