"""Collect every English UI string the running app renders.

Signs in as each demo role plus a fresh account, fetches every page in
English, and writes the unique text nodes and user-facing attributes to
``app/i18n/ui/source_en.json``. Translators fill ``hi.json`` / ``ta.json``
with ``{english: translation}``; see app/services/ui_translate.py.

    python -m uvicorn app.main:app          # in another terminal
    python scripts/extract_ui_strings.py [--base http://127.0.0.1:8000]

Prints which strings are still missing from each language catalog.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.ui_translate import UI_DIR, normalise  # noqa: E402

PUBLIC = ["/", "/login", "/register", "/forgot-password"]
PAGES = [
    "/dashboard", "/talk", "/check", "/reflect", "/learn", "/market", "/journey",
    "/family", "/privacy", "/settings", "/offline", "/batch", "/decision-readiness",
    "/explain", "/help", "/reports/journey",
]
ACCOUNTS = [
    ("priya@nirvaan.local", "NirvaanDemo2026", []),
    ("arun@nirvaan.local", "NirvaanDemo2026", []),
    ("admin@nirvaan.local", "QuietLotus7Harbour", ["/admin"]),
]
ATTRS = {"placeholder", "title", "aria-label", "alt"}
SKIP_TAGS = {"script", "style", "textarea"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "source", "track", "wbr"}


class Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool]] = []  # (tag, is_icon)
        self.found: set[str] = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for name in ATTRS & attrs.keys():
            self._add(attrs[name] or "")
        if tag in VOID:
            return
        icon = "material-symbols" in (attrs.get("class") or "")
        self.stack.append((tag, icon))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if any(t in SKIP_TAGS or icon for t, icon in self.stack):
            return
        self._add(data)

    def _add(self, text: str) -> None:
        key = normalise(text)
        if not key or not re.search(r"[A-Za-z]", key):
            return
        if "@" in key or key.startswith(("http", "/")):
            return
        if re.fullmatch(r"[a-z_]+", key) and "_" in key:  # stray icon ligature
            return
        self.found.add(key)


def _csrf(text: str) -> str:
    m = re.search(r'name="_csrf"[^>]*value="([^"]+)"|value="([^"]+)"[^>]*name="_csrf"', text)
    return (m.group(1) or m.group(2)) if m else ""


def _client(base: str) -> httpx.Client:
    c = httpx.Client(base_url=base, timeout=60, follow_redirects=True)
    c.cookies.set("nirvaan_lang", "en")
    return c


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    collector = Collector()
    names: set[str] = set()

    anon = _client(args.base)
    for path in PUBLIC:
        collector.feed(anon.get(path).text)

    sessions = []
    for email, password, extra in ACCOUNTS:
        c = _client(args.base)
        c.post("/login", data={"_csrf": _csrf(c.get("/login").text), "email": email, "password": password})
        sessions.append((c, extra))

    fresh = _client(args.base)
    fresh.post("/register", data={
        "_csrf": _csrf(fresh.get("/register").text), "full_name": "Ui Extract",
        "email": f"ui-extract-{int(time.time())}@example.com", "password": "UiExtract2026!x",
        "language": "en", "terms": "on",
    })
    sessions.append((fresh, []))

    for c, extra in sessions:
        for path in PAGES + extra:
            r = c.get(path)
            if r.status_code == 200 and "text/html" in r.headers.get("content-type", ""):
                collector.feed(r.text)
        # Lesson pages and past check results are only reachable from links.
        for slug in sorted(set(re.findall(r'href="/learn/([a-z0-9-]+)"', c.get("/learn").text)))[:40]:
            collector.feed(c.get(f"/learn/{slug}").text)
        for aid in sorted(set(re.findall(r'data-open-check="([0-9a-f-]{36})"', c.get("/check").text)))[:20]:
            r = c.get(f"/api/check/{aid}")
            if r.status_code == 200:
                collector.feed(r.json().get("html", ""))
                me = re.search(r"<p[^>]*truncate[^>]*>([^<]+)</p>", c.get("/dashboard").text)
        if me:
            names.add(normalise(me.group(1)))

    strings = sorted(s for s in collector.found if s not in names)
    UI_DIR.mkdir(parents=True, exist_ok=True)
    (UI_DIR / "source_en.json").write_text(
        json.dumps(strings, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"{len(strings)} strings -> {UI_DIR / 'source_en.json'}")

    for lang in ("hi", "ta"):
        path = UI_DIR / f"{lang}.json"
        have = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        missing = [s for s in strings if s not in have]
        print(f"{lang}: {len(missing)} missing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
