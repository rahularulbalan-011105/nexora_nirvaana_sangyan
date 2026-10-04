"""Explain Simply (/explain): the mutual fund lesson in the explainer layout.

The page shares ``pages/learn_module.html`` with /learn/{slug}. ``build`` does
not know the page language, so the lesson is prepared for each supported
language and the template picks ``lang_code``.
"""
from __future__ import annotations

from app.services import learning_content as lc
from app.services import learning_progress as lp

FEATURED_SLUG = "what-is-a-mutual-fund"


def build(db, user) -> dict:
    by_lang = {}
    for lang in lc.LANGUAGES:
        ctx = lp.module_context(db, user, FEATURED_SLUG, lang)
        if ctx is not None:
            by_lang[lang] = ctx
    return {"module_by_lang": by_lang}
