# CLAUDE.md — working in the NIRVAAN codebase

NIRVAAN is a FastAPI + Jinja2 + vanilla-JS web app: a trilingual (en / hi / ta)
financial-resilience companion. Read `README.md` for the product and
`docs/ARCHITECTURE.md` for design detail. This file is how to change the code
safely.

## Commands

Always use the project venv and `python -m` (several Pythons are installed;
bare `python` on this machine is 3.9 and wrong).

```bash
.venv/Scripts/python.exe -m uvicorn app.main:app --reload     # run (http://127.0.0.1:8000)
.venv/Scripts/python.exe -m pytest                            # 168 tests, ~25 s; must stay green
.venv/Scripts/python.exe -m alembic upgrade head              # migrate
.venv/Scripts/python.exe -m alembic revision --autogenerate -m "msg"
.venv/Scripts/python.exe scripts/seed.py --demo-users         # idempotent seed + demo activity
.venv/Scripts/python.exe scripts/extract_ui_strings.py        # list untranslated UI strings (server must be running)
.venv/Scripts/python.exe scripts/merge_ui_translations.py     # merge app/i18n/ui/parts/* into hi.json / ta.json
.venv/Scripts/python.exe scripts/worker.py                    # RQ worker (only with REDIS_URL)
```

Demo logins: `priya@nirvaan.local` / `NirvaanDemo2026` (seeded data),
`arun@nirvaan.local` / `NirvaanDemo2026`, `admin@nirvaan.local` / `QuietLotus7Harbour`.

## Gotchas

- **Restart the server after Python changes.** `--reload` on Windows often
  misses them. Templates and translation JSON reload without a restart.
- **Login is rate-limited to 5/min per IP per process.** For browser tests,
  start a separate server on another port, or test APIs with
  `fastapi.testclient.TestClient` (it has its own limiter).
- The CSP blocks `eval`; Playwright `wait_for_function` needs
  `new_context(bypass_csp=True)` (tests only).
- Several templates use CRLF line endings — preserve them when editing
  programmatically.
- Seed and tests write to `data/nirvaan.db`; clean up rows you create on demo
  accounts.

## Architecture in one screen

- `app/routers/pages.py` — page routes. Most pages use `_simple_page(path,
  template, nav_key, title)`. Per-page data comes from
  **`app/page_context/<nav_key with _>.py` → `build(db, user) -> dict`**,
  merged into the template context automatically. Add data there, not in the
  route.
- Feature APIs live in their own routers: `feature_check.py` (`/api/check`),
  `feature_batch.py` (`/api/batch`), `feature_reflect.py`, `feature_learn.py`
  (also the `/learn/{slug}` page), `feature_account.py` (`/api/account`).
  Cross-cutting endpoints are in `api.py`; reports and data export in
  `reports.py`. Register new routers in `app/main.py`.
- `app/templating.py` — `render()` and `base_context()` (user, prefs, privacy,
  `lang_code`, `t`, `csrf_token`, notifications, nav). Use `render()` for every
  HTML response so CSRF, language and translation apply.
- `app/navigation.py` — sidebar items and breadcrumbs.
- Templates: `base.html` + `partials/` (sidebar, topbar with notifications and
  profile menu) + `pages/`. Auth pages use `auth_base.html`; the landing page
  is standalone.
- JS: one file per feature in `app/static/js/` (`talk.js`, `check.js`,
  `batch.js`, `reflect.js`, `learn.js`, `account.js`); `nirvaan.js` is shared.
- Background work: `app.services.jobs.enqueue("module:function", *args)` only
  (thread pool, or RQ when Redis + a worker are available). Job functions open
  their own `SessionLocal()` and must be safe to retry.
- Optional Redis via `app/services/redis_client.py` / `cache.py`; everything
  must keep working with `REDIS_URL` empty.

## Rules that must not be broken

1. **No financial advice.** Never recommend buying/selling/holding, ranking
   products or predicting prices. Route all model input/output through
   `app/services/responsible_ai.py` (`check_input`, `check_output`,
   `redact_sensitive`).
2. **Never store or request credentials** (OTP, PIN, CVV, card numbers,
   passwords). Redact before analysing or saving.
3. **Analysis status vocabulary is fixed:** the `AnalysisStatus` enum only
   (Multiple Safety Signals Detected / Needs Verification / No Obvious Warning
   Signals Detected). Never say "safe" or "definitely a scam".
4. **No fakes.** No fake data, progress, results, transcripts or "Saved!"
   messages. If a control can't work, show it disabled with "Not available
   yet". Empty states instead of sample data.
5. **User-scoped data.** Every query on personal data filters by
   `user_id == user.id`; other users' records return 404. Admin views are
   aggregate only.
6. **Respect privacy switches** (`user.privacy`): `memory_enabled`,
   `store_analysis_history`, `store_voice_transcripts`,
   `store_uploaded_files`, `allow_family_access`. Memory writes go through
   `app.services.account.remember()`.
7. **CSRF on every state change.** Forms include
   `{% include "partials/csrf.html" %}`; `fetch` sends
   `X-CSRF-Token: window.NIRVAAN.csrf`; routes use
   `dependencies=[Depends(verify_csrf), ThrottleApi]`.
8. **Keep the Stitch visual design.** Reuse the existing Tailwind tokens
   (`bg-surface-container-*`, `text-on-surface`, `font-label-md`, …), rounded
   cards and colours. The `nirvaan_*/code.html` folders are the original
   design reference — never edit them.
9. **Responsive:** no horizontal overflow at 390, 768, 1024, 1440 px. Below
   `lg` the sidebar is a slide-in menu.

## Languages (important)

The page language is the single source of truth (`lang_code`).

- Write template text **in English, as whole text nodes**; don't split a
  sentence across tags. Put dynamic values in their own element
  (`<span>{{ n }}</span> reflections`).
- `ui_translate.translate_html` translates text nodes and
  `placeholder/title/aria-label/alt` by exact match against
  `app/i18n/ui/{hi,ta}.json`. Text inside `<script>`, `<style>`,
  `<textarea>` is never translated.
- Strings shown by JavaScript go in a hidden block in the template and are
  read by the script:
  `<div hidden id="feature-strings"><span data-k="key">English</span></div>`
  (see `talk.html` / `talk.js`).
- Lesson content (`app/services/learning_content.py`) and offline Talk
  answers (`app/services/talk_answers.py`) are written natively per language.
- After adding UI text: run `extract_ui_strings.py`, translate the missing
  strings into `app/i18n/ui/parts/{hi,ta}_<n>.json`, run
  `merge_ui_translations.py`. Never translate users' own content (messages,
  journal text, names).
- Speech uses `en-IN` / `hi-IN` / `ta-IN`; handle missing voices gracefully.

## Before you finish a change

- `python -m pytest` passes; add tests for new backend behaviour
  (`tests/test_<feature>.py`).
- Restart the server and load the changed pages in en, hi and ta.
- Check the browser console and horizontal overflow at the four widths.
- No dead buttons, no fake success states, no new English-only text without
  queuing it for translation.
