"""Turn the Stitch HTML exports into Jinja templates.

This is a one-way, re-runnable build step. It treats the Stitch exports as the
visual source of truth and never edits them:

  <stitch_dir>/code.html  ->  app/templates/pages/<slug>.html

The shared shell (head, sidebar, top bar) is lifted from the dashboard export
into app/templates/base.html plus partials, with the hard-coded nav, user name
and language swapped for Jinja expressions. Everything else - classes, colours,
spacing, illustrations - is copied byte for byte.

Run:  python scripts/extract_templates.py
Add --force to overwrite page templates that have since been hand-edited.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "app" / "templates"
PAGES = TEMPLATES / "pages"
PARTIALS = TEMPLATES / "partials"

# Stitch export directory -> template slug + nav key used for active state.
PAGE_MAP: dict[str, tuple[str, str]] = {
    "nirvaan_dashboard": ("dashboard", "dashboard"),
    "voice_assistant_regional_explainer": ("talk", "talk-to-nirvaan"),
    "check_a_message_safety_analysis": ("check_message", "check-a-message"),
    "pause_reflect_suite": ("reflect", "pause-and-reflect"),
    "nirvaan_learn_explore": ("learn", "learn-and-explore"),
    "nirvaan_market_education": ("market", "market-education"),
    "nirvaan_my_journey": ("journey", "my-journey"),
    "nirvaan_family_mode": ("family", "family-mode"),
    "nirvaan_privacy_center": ("privacy", "privacy-center"),
    "nirvaan_profile_settings": ("settings", "settings"),
    "nirvaan_offline_mode": ("offline", "offline"),
    "nirvaan_batch_analysis_results": ("batch", "batch"),
    "nirvaan_decision_readiness": ("decision_readiness", "decision-readiness"),
    "nirvaan_explain_simply": ("explain_simply", "explain-simply"),
    "nirvaan_admin_dashboard": ("admin", "admin"),
}

# The dashboard export is the canonical shell donor.
SHELL_SOURCE = "nirvaan_dashboard"
# The register export is the canonical auth-shell donor.
AUTH_SOURCE = "nirvaan_register"

PAGE_TITLES: dict[str, str] = {
    "dashboard": "Dashboard",
    "talk": "Talk to NIRVAAN",
    "check_message": "Check a Message",
    "reflect": "Pause & Reflect",
    "learn": "Learn & Explore",
    "market": "Market Education",
    "journey": "My Journey",
    "family": "Family Mode",
    "privacy": "Privacy Center",
    "settings": "Profile & Settings",
    "offline": "Offline Mode",
    "batch": "Batch Analysis",
    "decision_readiness": "Decision Readiness",
    "explain_simply": "Explain Simply",
    "admin": "Admin Console",
}

def banner(source: str) -> str:
    """Jinja comment marking a file as generated.

    Built by concatenation rather than str.format: the Jinja comment delimiters
    are themselves braces.
    """
    return (
        "{# ---------------------------------------------------------------\n"
        "   GENERATED from " + source + "/code.html by scripts/extract_templates.py\n"
        "   The Stitch export is the visual source of truth. Markup below is\n"
        "   copied verbatim; add behaviour with Jinja expressions in place.\n"
        "   --------------------------------------------------------------- #}\n"
    )


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def find_block(html: str, tag: str) -> tuple[int, int, int, int]:
    """Locate the first ``<tag ...>`` element, honouring nesting.

    Returns ``(outer_start, inner_start, inner_end, outer_end)``.
    """
    open_re = re.compile(rf"<{tag}\b[^>]*>", re.IGNORECASE)
    match = open_re.search(html)
    if not match:
        raise ValueError(f"<{tag}> not found")

    outer_start, inner_start = match.span()
    depth = 1
    pos = inner_start
    token = re.compile(rf"</?{tag}\b[^>]*>", re.IGNORECASE)

    while depth and (m := token.search(html, pos)):
        depth += -1 if m.group(0).startswith("</") else 1
        pos = m.end()
        if depth == 0:
            return outer_start, inner_start, m.start(), m.end()

    raise ValueError(f"unbalanced <{tag}>")


def inner_of(html: str, tag: str) -> str:
    _, start, end, _ = find_block(html, tag)
    return html[start:end]


def outer_of(html: str, tag: str) -> str:
    start, _, _, end = find_block(html, tag)
    return html[start:end]


# ---------------------------------------------------------------------------
# Shell construction
# ---------------------------------------------------------------------------


def build_head(shell: str) -> str:
    """Head partial: fonts and the Tailwind token config, kept verbatim."""
    head = inner_of(shell, "head")
    # Drop the Stitch-specific shell marker; it has no meaning at runtime.
    head = re.sub(r'<meta content="web_dashboard" name="shell-type">\s*', "", head)
    return (
        banner(SHELL_SOURCE)
        + "{# Design tokens below are the Stitch config - do not retune by hand. #}\n"
        + head.strip()
        + "\n"
    )


def build_sidebar(shell: str) -> str:
    """Sidebar partial with a dynamic nav loop and the real signed-in user."""
    aside = outer_of(shell, "aside")

    # Replace the hard-coded nav list with a loop over app.navigation.NAV_ITEMS.
    nav_start, nav_inner_start, nav_inner_end, nav_end = find_block(aside, "nav")
    nav_open = aside[nav_start:nav_inner_start]
    # Keep Stitch's data-active-classes hook, but drive classes from Python.
    nav_open = re.sub(r'\s*data-active-classes="[^"]*"', "", nav_open)

    nav_loop = """
{%- for item in nav_items %}
{%- if item.divider_before %}
<div class="py-2 px-space-md"><div class="h-px w-full bg-surface-container-high"></div></div>
{%- endif %}
<a class="{{ nav_active_class if item.key == active_nav else nav_inactive_class }}"
   data-path="{{ item.key }}"
   href="{{ item.url }}"
   {% if item.key == active_nav %}aria-current="page"{% endif %}>
<span class="material-symbols-outlined text-[20px]">{{ item.icon }}</span>
<span class="font-label-lg text-label-lg">{{ item.label }}</span>
</a>
{%- endfor %}
"""
    aside = aside[:nav_inner_start] + nav_loop + aside[nav_inner_end:]
    aside = aside.replace(aside[nav_start:nav_inner_start], nav_open, 1)

    # Swap the mock profile card for the signed-in user.
    aside = aside.replace("Priya Sharma", "{{ user.full_name if user else 'Guest' }}")
    aside = aside.replace("Learning • Growing", "{{ user_status }}")

    return banner(SHELL_SOURCE) + aside + "\n"


def build_topbar(shell: str) -> str:
    """Top bar partial: live breadcrumb, language selector, search."""
    header = outer_of(shell, "header")

    header = header.replace(
        '<span class="text-on-surface-variant truncate max-w-[140px]">Resilience Portal</span>',
        '<span class="text-on-surface-variant truncate max-w-[140px]">{{ breadcrumb }}</span>',
    )
    # Language selector becomes a real form control.
    header = header.replace(
        "<span>English</span>", "<span>{{ language_label }}</span>"
    )
    header = header.replace(
        'aria-label="Select Language" class=',
        'aria-label="Select Language" data-action="open-language" class=',
    )
    # Notification dot only when something is actually unread.
    header = header.replace(
        '<span class="absolute top-2 right-2 w-2 h-2 rounded-full bg-error '
        'ring-2 ring-surface-container-lowest"></span>',
        "{% if unread_count %}<span class=\"absolute top-2 right-2 w-2 h-2 rounded-full "
        'bg-error ring-2 ring-surface-container-lowest"></span>{% endif %}',
    )
    header = header.replace(
        'placeholder="Ask anything about financial information'
        ' (e.g. SIP, mutual funds, scam check)"',
        'placeholder="{{ search_placeholder }}"',
    )
    header = re.sub(
        r'placeholder="Ask anything[^"]*"', 'placeholder="{{ search_placeholder }}"', header
    )
    return banner(SHELL_SOURCE) + header + "\n"


def build_base(shell: str) -> str:
    """base.html: head + sidebar + top bar + a content block inside <main>."""
    body_open = re.search(r"<body\b[^>]*>", shell, re.IGNORECASE)
    if not body_open:
        raise ValueError("<body> not found in shell donor")
    body_tag = body_open.group(0)

    main_open = re.search(r"<main\b[^>]*>", shell, re.IGNORECASE).group(0)
    # Everything between </header> and <main> plus the wrapper div around them.
    wrapper = re.search(r'<div class="pl-72[^"]*">', shell)
    wrapper_tag = wrapper.group(0) if wrapper else '<div class="pl-72 flex flex-col min-h-screen">'

    return f"""{banner(SHELL_SOURCE)}<!DOCTYPE html>
<html class="{{{{ 'text-[18px]' if prefs and prefs.large_text else '' }}}}"
      lang="{{{{ lang_code or 'en' }}}}"
      data-lang="{{{{ lang_code or 'en' }}}}"
      data-data-saver="{{{{ '1' if prefs and prefs.data_saver else '0' }}}}">
<head>
<title>{{% block title %}}NIRVAAN{{% endblock %}} · NIRVAAN</title>
{{% include "partials/head.html" %}}
<link href="/static/css/nirvaan.css" rel="stylesheet">
<link href="/static/manifest.webmanifest" rel="manifest">
<meta content="#2563eb" name="theme-color">
{{% block head_extra %}}{{% endblock %}}
</head>
{body_tag}
{{% include "partials/offline_banner.html" %}}
{{% include "partials/sidebar.html" %}}
{wrapper_tag}
{{% include "partials/topbar.html" %}}
{main_open}
{{% block content %}}{{% endblock %}}
</main>
</div>
{{% include "partials/toast.html" %}}
<script>window.NIRVAAN = {{
  lang: "{{{{ lang_code or 'en' }}}}",
  csrf: "{{{{ csrf_token }}}}",
  dataSaver: {{{{ 'true' if prefs and prefs.data_saver else 'false' }}}},
  authenticated: {{{{ 'true' if user else 'false' }}}}
}};</script>
<script src="/static/js/nirvaan.js" defer></script>
{{% block scripts %}}{{% endblock %}}
</body>
</html>
"""


def build_auth_base(auth_html: str) -> str:
    """Shell for the unauthenticated pages, donated by the register export."""
    head = inner_of(auth_html, "head")
    # base.html supplies the title block, so drop the exported static one.
    head = re.sub(r"<title>.*?</title>\s*", "", head, flags=re.IGNORECASE | re.DOTALL)

    body_tag = re.search(r"<body\b[^>]*>", auth_html, re.IGNORECASE).group(0)
    body_inner = inner_of(auth_html, "body")

    # The Stitch mock carries a "SEBI Registered Framework Safe" badge. That is
    # an unverified regulatory authority claim - precisely the pattern NIRVAAN
    # teaches users to distrust - so it is replaced with an accurate statement.
    body_inner = body_inner.replace(
        "SEBI Registered Framework Safe", "Non-commercial · Educational only"
    )

    # Keep everything except <main>, which becomes the content block.
    m_outer_start, _, _, m_outer_end = find_block(body_inner, "main")
    before = body_inner[:m_outer_start]
    after = body_inner[m_outer_end:]
    main_open = re.search(r"<main\b[^>]*>", body_inner, re.IGNORECASE).group(0)

    return f"""{banner(AUTH_SOURCE)}<!DOCTYPE html>
<html lang="{{{{ lang_code or 'en' }}}}" data-lang="{{{{ lang_code or 'en' }}}}">
<head>
<title>{{% block title %}}Welcome{{% endblock %}} · NIRVAAN</title>
{head.strip()}
<link href="/static/css/nirvaan.css" rel="stylesheet">
<link href="/static/manifest.webmanifest" rel="manifest">
<meta content="#2563eb" name="theme-color">
{{% block head_extra %}}{{% endblock %}}
</head>
{body_tag}
{before}
{main_open}
{{% block content %}}{{% endblock %}}
</main>
{after}
<script>window.NIRVAAN = {{ lang: "{{{{ lang_code or 'en' }}}}", csrf: "{{{{ csrf_token }}}}", authenticated: false }};</script>
<script src="/static/js/nirvaan.js" defer></script>
{{% block scripts %}}{{% endblock %}}
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Page extraction
# ---------------------------------------------------------------------------


def build_page(source_dir: str, slug: str, nav_key: str, html: str) -> str:
    content = inner_of(html, "main").strip()
    title = PAGE_TITLES.get(slug, slug.replace("_", " ").title())

    return (
        banner(source_dir)
        + '{% extends "base.html" %}\n'
        + f"{{% block title %}}{title}{{% endblock %}}\n\n"
        + "{% block content %}\n"
        + content
        + "\n{% endblock %}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite page templates even if they were hand-edited since generation",
    )
    args = parser.parse_args()

    for directory in (TEMPLATES, PAGES, PARTIALS):
        directory.mkdir(parents=True, exist_ok=True)

    shell_file = ROOT / SHELL_SOURCE / "code.html"
    if not shell_file.exists():
        print(f"error: shell donor missing: {shell_file}", file=sys.stderr)
        return 1
    shell = read(shell_file)

    written: list[str] = []
    skipped: list[str] = []

    # --- shared shell ---
    for name, content in (
        ("partials/head.html", build_head(shell)),
        ("partials/sidebar.html", build_sidebar(shell)),
        ("partials/topbar.html", build_topbar(shell)),
        ("base.html", build_base(shell)),
    ):
        (TEMPLATES / name).write_text(content, encoding="utf-8")
        written.append(name)

    auth_file = ROOT / AUTH_SOURCE / "code.html"
    if auth_file.exists():
        (TEMPLATES / "auth_base.html").write_text(
            build_auth_base(read(auth_file)), encoding="utf-8"
        )
        written.append("auth_base.html")

    # --- pages ---
    for source_dir, (slug, nav_key) in sorted(PAGE_MAP.items()):
        src = ROOT / source_dir / "code.html"
        if not src.exists():
            print(f"  skip (no export): {source_dir}")
            continue

        target = PAGES / f"{slug}.html"
        if target.exists() and not args.force:
            existing = read(target)
            if "GENERATED from" not in existing.split("\n", 4)[1]:
                skipped.append(f"{slug} (hand-edited; use --force)")
                continue

        try:
            target.write_text(
                build_page(source_dir, slug, nav_key, read(src)), encoding="utf-8"
            )
        except ValueError as exc:
            print(f"  error in {source_dir}: {exc}", file=sys.stderr)
            continue
        written.append(f"pages/{slug}.html")

    print(f"wrote {len(written)} template(s):")
    for name in written:
        print("  +", name)
    if skipped:
        print("skipped:")
        for name in skipped:
            print("  -", name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
