"""Learn & Explore: lesson content, lesson pages and per-user progress."""
from __future__ import annotations

import re
import uuid

import pytest
from markupsafe import escape

from app.services import learning_content as lc
from tests.conftest import csrf_of

TAMIL = re.compile(r"[஀-௿]")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
# Language names in the language picker are deliberately shown in their own script.
LANGUAGE_LABELS = ("தமிழ்", "हिन्दी")


def _strip_labels(html: str) -> str:
    for label in LANGUAGE_LABELS:
        html = html.replace(label, "")
    return html


def _seeded_slugs() -> list[str]:
    from scripts.seed import LEARNING

    return [spec["slug"] for spec in LEARNING]


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------


def test_every_seeded_lesson_has_all_languages_and_modes():
    for slug in _seeded_slugs():
        assert slug in lc.LESSONS, slug
        lesson = lc.LESSONS[slug]
        for lang in lc.LANGUAGES:
            text = lesson[lang]
            for field in ("title", "summary", *lc.MODES):
                assert text[field].strip(), (slug, lang, field)
            # The four modes are genuinely different explanations.
            assert len({text[m] for m in lc.MODES}) == 4, (slug, lang)
        # Hindi is Devanagari, Tamil is Tamil script, English is neither.
        assert DEVANAGARI.search(lesson["hi"]["simple"]), slug
        assert TAMIL.search(lesson["ta"]["simple"]), slug
        en_all = " ".join(lesson["en"].values())
        assert not TAMIL.search(en_all) and not DEVANAGARI.search(en_all), slug


def test_resources_are_official_https_links():
    for slug, lesson in lc.LESSONS.items():
        assert lesson["resources"], slug
        for key in lesson["resources"]:
            res = lc.RESOURCES[key]
            assert res["url"].startswith("https://"), key
            assert res["url"].split("/")[2].endswith((".gov.in", ".org.in", "amfiindia.com"))
            assert all(res["about"].get(lang) for lang in lc.LANGUAGES), key


def test_content_makes_no_recommendation():
    banned = re.compile(r"\b(you should (buy|sell|invest)|we recommend|buy now|sell now)\b", re.I)
    for slug, lesson in lc.LESSONS.items():
        assert not banned.search(" ".join(lesson["en"].values())), slug


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


@pytest.fixture
def learner(auth_client, request):
    request.node.learner_email = f"learner-{uuid.uuid4().hex[:12]}@test.local"
    return auth_client(email=request.node.learner_email)


def test_learn_page_links_every_card_to_a_lesson(learner):
    html = learner.get("/learn?lang=en").text
    for slug in _seeded_slugs():
        assert f'href="/learn/{slug}"' in html, slug
        assert f'data-learn-card="{slug}"' in html
    # Every filter chip maps to a real group and every card carries one.
    groups = set(re.findall(r'data-group="([a-z-]+)"', html))
    chips = set(re.findall(r'data-category="([a-z-]+)"', html)) - {"all"}
    assert groups <= chips
    # The old fake audio toggle is gone; there is no Tamil on an English page.
    assert "toggle-audio-guide" not in html
    assert not TAMIL.search(_strip_labels(html))
    # A brand-new account has no resume card.
    assert 'id="learn-resume"' not in html


@pytest.mark.parametrize("lang,script", [("hi", DEVANAGARI), ("ta", TAMIL)])
def test_learn_page_shows_lessons_in_the_page_language(learner, lang, script):
    html = learner.get(f"/learn?lang={lang}").text
    title = lc.LESSONS["understanding-sip"][lang]["title"]
    assert title in html
    assert script.search(title)
    learner.get("/learn?lang=en")  # reset the language cookie


def test_lesson_page_renders_four_modes_in_each_language(learner):
    slug = "what-is-a-mutual-fund"
    for lang in lc.LANGUAGES:
        html = learner.get(f"/learn/{slug}?lang={lang}").text
        for mode in lc.MODES:
            assert f'data-mode-panel="{mode}"' in html
            first = lc.LESSONS[slug][lang][mode].split("\n\n")[0].split("\n")[0]
            assert str(escape(first)) in html, (lang, mode)
        assert f'data-speech-lang="{lc.SPEECH_LANG[lang]}"' in html
        for res in lc.LESSONS[slug]["resources"]:
            assert lc.RESOURCES[res]["url"] in html
        assert 'target="_blank"' in html
    english = learner.get(f"/learn/{slug}?lang=en").text
    assert not TAMIL.search(_strip_labels(english))
    assert not DEVANAGARI.search(_strip_labels(english))


def test_unknown_lesson_is_404(learner):
    assert learner.get("/learn/not-a-real-lesson").status_code == 404


def test_explain_page_uses_the_working_lesson_layout(learner):
    html = learner.get("/explain?lang=ta").text
    assert lc.LESSONS["what-is-a-mutual-fund"]["ta"]["title"] in html
    assert 'data-mode-panel="analogy"' in html
    learner.get("/learn?lang=en")


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------


def test_progress_requires_csrf_and_login(client):
    assert client.post("/api/learn/understanding-sip/view").status_code in (401, 403)


def test_progress_view_modes_complete_and_resume(learner):
    headers = {"X-CSRF-Token": csrf_of(learner)}
    assert learner.post("/api/learn/understanding-sip/view").status_code == 403

    r = learner.post("/api/learn/understanding-sip/view", headers=headers)
    assert r.status_code == 200 and r.json()["percent"] == 25
    r = learner.post(
        "/api/learn/understanding-sip/progress", headers=headers, json={"modes_seen": 4}
    )
    assert r.json()["percent"] == 75 and r.json()["complete"] is False

    html = learner.get("/learn").text
    assert 'id="learn-resume"' in html
    resume = html.split('id="learn-resume"', 1)[1].split("</section>", 1)[0]
    assert 'href="/learn/understanding-sip"' in resume

    # Viewing a second lesson makes it the most recent incomplete one.
    learner.post("/api/learn/what-is-volatility/view", headers=headers)
    resume = learner.get("/learn").text.split('id="learn-resume"', 1)[1].split("</section>", 1)[0]
    assert 'href="/learn/what-is-volatility"' in resume

    r = learner.post("/api/learn/what-is-volatility/complete", headers=headers)
    assert r.json() == {**r.json(), "percent": 100, "complete": True}
    html = learner.get("/learn").text
    assert '<span id="stat-completed">1</span>' in html
    resume = html.split('id="learn-resume"', 1)[1].split("</section>", 1)[0]
    assert 'href="/learn/understanding-sip"' in resume

    # Lesson page reflects the stored state.
    page = learner.get("/learn/what-is-volatility").text
    assert 'data-complete="1"' in page

    # Bookmarks are real and counted.
    r = learner.post(
        "/api/learn/understanding-sip/bookmark", headers=headers, json={"bookmarked": True}
    )
    assert r.json()["bookmarked"] is True
    assert "<span>1</span> <span>Saved</span>" in learner.get("/learn").text

    assert learner.post("/api/learn/nope/view", headers=headers).status_code == 404


def test_progress_rows_belong_to_the_user(learner, db, request):
    from sqlalchemy import select

    from app.models.learning import LearningContent, LearningProgress
    from app.models.user import User

    headers = {"X-CSRF-Token": csrf_of(learner)}
    learner.post("/api/learn/budgeting-first-steps/view", headers=headers)
    user = db.execute(select(User).where(User.email == request.node.learner_email)).scalar_one()
    content = db.execute(
        select(LearningContent).where(LearningContent.slug == "budgeting-first-steps")
    ).scalar_one()
    row = db.execute(
        select(LearningProgress).where(
            LearningProgress.user_id == user.id, LearningProgress.content_id == content.id
        )
    ).scalar_one()
    assert row.view_count >= 1 and row.last_viewed_at is not None and row.completed_at is None
