"""Whole-page UI translation for Hindi and Tamil.

The page templates come from the Stitch design exports and hold their English
copy inline, so ``t()`` keys alone cannot cover them. Instead, after a page is
rendered, every text node and every user-facing attribute (placeholder, title,
aria-label, alt) whose exact English text appears in
``app/i18n/ui/<lang>.json`` is swapped for its translation.

Matching is exact and case-sensitive on whitespace-normalised text, so user
content (names, journal text, message bodies) passes through untouched unless
it happens to equal a UI string verbatim. ``<script>``, ``<style>`` and
``<textarea>`` bodies are never touched.

Regenerate the source list with ``python scripts/extract_ui_strings.py``.
"""
from __future__ import annotations

import html
import json
import logging
import re
from functools import lru_cache

from app.config import BASE_DIR

log = logging.getLogger("nirvaan.ui_translate")

UI_DIR = BASE_DIR / "app" / "i18n" / "ui"

_RAW_BLOCK = re.compile(r"(<(script|style|textarea)\b[^>]*>.*?</\2\s*>)", re.S | re.I)
_TEXT_NODE = re.compile(r">([^<>]+)<")
_ATTR = re.compile(r'(\s(?:placeholder|title|aria-label|alt)=")([^"]*)(")')
_WS = re.compile(r"\s+")

# Relative times are generated per request ("7 min ago"), so they cannot live in
# the static catalog; translate them by pattern instead.
_AGO = re.compile(r"^(\d+) (min|minute|minutes|hr|hrs|hour|hours|day|days) ago$")
_UNITS = {
    "hi": {"min": "मिनट", "hour": "घंटे", "day": "दिन"},
    "ta": {"min": "நிமிடம்", "hour": "மணிநேரம்", "day": "நாள்"},
}
_AGO_FORMAT = {"hi": "{n} {unit} पहले", "ta": "{n} {unit} முன்பு"}
_JUST_NOW = {"hi": "अभी-अभी", "ta": "இப்போது தான்"}


def _relative_time(key: str, language: str) -> str | None:
    if language not in _AGO_FORMAT:
        return None
    if key.lower() == "just now":
        return _JUST_NOW[language]
    match = _AGO.match(key)
    if not match:
        return None
    unit = match.group(2)
    unit = "min" if unit.startswith("min") else "hour" if unit.startswith("h") else "day"
    return _AGO_FORMAT[language].format(n=match.group(1), unit=_UNITS[language][unit])


def normalise(text: str) -> str:
    """Catalog key for a piece of rendered text."""
    return _WS.sub(" ", html.unescape(text)).strip()


def catalog(language: str) -> dict[str, str]:
    """Catalog for ``language``, re-read whenever its file changes on disk."""
    path = UI_DIR / f"{language}.json"
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {}
    return _load(language, mtime)


@lru_cache(maxsize=8)
def _load(language: str, mtime: float) -> dict[str, str]:
    path = UI_DIR / f"{language}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("could not load UI catalog %s: %s", language, exc)
        return {}
    return {normalise(k): v for k, v in data.items() if isinstance(v, str) and v.strip()}


def _translate_segment(segment: str, table: dict[str, str], language: str) -> str:
    def text_node(match: re.Match[str]) -> str:
        raw = match.group(1)
        key = normalise(raw)
        if not key:
            return match.group(0)
        value = table.get(key) or _relative_time(key, language)
        if value is None:
            return match.group(0)
        lead = raw[: len(raw) - len(raw.lstrip())]
        trail = raw[len(raw.rstrip()):]
        return ">" + lead + html.escape(value, quote=False) + trail + "<"

    def attribute(match: re.Match[str]) -> str:
        key = normalise(match.group(2))
        if key not in table:
            return match.group(0)
        return match.group(1) + html.escape(table[key], quote=True) + match.group(3)

    segment = _TEXT_NODE.sub(text_node, segment)
    return _ATTR.sub(attribute, segment)


def translate_html(page: str, language: str) -> str:
    """Return ``page`` with known UI strings translated into ``language``."""
    table = catalog(language)
    if not table:
        return page
    parts = _RAW_BLOCK.split(page)
    # re.split with two groups yields: text, whole-block, tag-name, text, ...
    out: list[str] = []
    i = 0
    while i < len(parts):
        out.append(_translate_segment(parts[i], table, language))
        if i + 1 < len(parts):
            out.append(parts[i + 1])  # raw block, untouched
        i += 3
    return "".join(out)
