"""Translation lookup and language detection for English, Hindi and Tamil.

Strings live in app/i18n/<code>.json. Lookup falls back to English and then to
the key itself, so a missing translation degrades to readable text rather than
an exception or a blank screen.
"""
from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import BASE_DIR
from app.models.enums import Language

log = logging.getLogger("nirvaan.i18n")

I18N_DIR = BASE_DIR / "app" / "i18n"
DEFAULT_LANGUAGE = Language.EN.value

SUPPORTED: dict[str, dict[str, str]] = {
    "en": {"label": "English", "native": "English", "dir": "ltr"},
    "hi": {"label": "Hindi", "native": "हिन्दी", "dir": "ltr"},
    "ta": {"label": "Tamil", "native": "தமிழ்", "dir": "ltr"},
}

# Unicode block heuristics. These are decisive for Devanagari and Tamil, so
# they run before the statistical detector.
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_TAMIL = re.compile(r"[஀-௿]")


@lru_cache(maxsize=8)
def _catalog(language: str) -> dict[str, Any]:
    path = I18N_DIR / f"{language}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("could not load i18n catalog %s: %s", language, exc)
        return {}


def normalise(language: str | None) -> str:
    code = (language or "").strip().lower()[:2]
    return code if code in SUPPORTED else DEFAULT_LANGUAGE


def translate(key: str, language: str | None = None, **params: Any) -> str:
    """Look up ``key``, falling back to English then to the key itself."""
    lang = normalise(language)
    value = _catalog(lang).get(key)
    if value is None and lang != DEFAULT_LANGUAGE:
        value = _catalog(DEFAULT_LANGUAGE).get(key)
    if value is None:
        value = key

    if params and isinstance(value, str):
        try:
            return value.format(**params)
        except (KeyError, IndexError, ValueError):
            # A malformed placeholder must not break the page.
            return value
    return value


def translator(language: str | None):
    """Bound translator passed into templates as ``t``."""
    lang = normalise(language)

    def _t(key: str, **params: Any) -> str:
        return translate(key, lang, **params)

    return _t


def language_label(language: str | None) -> str:
    return SUPPORTED[normalise(language)]["native"]


def language_options() -> list[dict[str, str]]:
    return [
        {"code": code, "label": meta["label"], "native": meta["native"]}
        for code, meta in SUPPORTED.items()
    ]


def detect_language(text: str, *, default: str = DEFAULT_LANGUAGE) -> tuple[str, float]:
    """Detect the language of user-supplied text.

    Returns ``(code, confidence)``. Script detection is checked first because
    Devanagari and Tamil characters are unambiguous; romanised Hindi or Tamil
    falls through to the statistical detector and often reads as English,
    which is why the UI always lets the user override the language.
    """
    sample = (text or "").strip()
    if not sample:
        return default, 0.0

    tamil = len(_TAMIL.findall(sample))
    devanagari = len(_DEVANAGARI.findall(sample))
    letters = sum(1 for ch in sample if ch.isalpha()) or 1

    if tamil and tamil / letters > 0.15:
        return "ta", min(0.99, 0.6 + tamil / letters)
    if devanagari and devanagari / letters > 0.15:
        return "hi", min(0.99, 0.6 + devanagari / letters)

    try:
        from langdetect import DetectorFactory, detect_langs

        DetectorFactory.seed = 0  # deterministic results
        best = detect_langs(sample)[0]
        code = normalise(best.lang)
        # langdetect only helps us distinguish the three languages we support.
        if best.lang[:2] in SUPPORTED:
            return code, float(best.prob)
        return default, 0.3
    except Exception:  # noqa: BLE001 - detection is best-effort
        return default, 0.2


def reload_catalogs() -> None:
    """Drop the cache so edited JSON is picked up without a restart."""
    _catalog.cache_clear()
