"""Landing page and the walkthrough-video route.

``/demo`` sends people to ``DEMO_VIDEO_URL``. With no URL configured the
button must not be rendered at all, so nothing on the page links to a video
that does not exist.
"""
from __future__ import annotations

import pytest

VIDEO_URL = "https://example.invalid/file/abc/view"


@pytest.fixture
def demo_url(monkeypatch):
    """Set ``settings.demo_video_url`` for one test."""

    def _set(value: str):
        from app.config import settings

        monkeypatch.setattr(settings, "demo_video_url", value)

    return _set


def test_landing_renders_anonymously(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Get Started" in response.text


def test_demo_redirects_to_configured_video(client, demo_url):
    demo_url(VIDEO_URL)
    response = client.get("/demo")
    assert response.status_code == 303
    assert response.headers["location"] == VIDEO_URL


def test_landing_shows_watch_demo_when_video_configured(client, demo_url):
    demo_url(VIDEO_URL)
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="/demo"' in response.text
    assert "Watch Demo" in response.text


def test_landing_hides_watch_demo_without_a_video(client, demo_url):
    demo_url("")
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="/demo"' not in response.text


def test_demo_without_a_video_does_not_redirect(client, demo_url):
    demo_url("")
    response = client.get("/demo")
    assert response.status_code == 200
    assert "not available yet" in response.text


def test_landing_redirects_signed_in_user_to_dashboard(auth_client):
    signed_in = auth_client(email="landing@test.local")
    response = signed_in.get("/")
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"
