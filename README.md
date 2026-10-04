# NIRVAAN — Financial Resilience Companion

**Pause. Understand. Reflect. Decide for yourself.**

NIRVAAN is a multilingual (English, हिन्दी, தமிழ்), voice-first web application
that helps people in India understand financial information, notice the
warning signs of scams and pressure tactics, and pause before acting on money
decisions.

It is a non-commercial public-good project. **It never tells anyone what to
buy, sell or hold, never predicts prices, and never asks for an OTP, PIN or
password.** Those rules are enforced in code, not left to a prompt.

### ▶ Watch the demo

**[NIRVAAN — full walkthrough video](https://drive.google.com/file/d/1ERj4PQzkbVaEBGn3IAsJUiPc7NxreZsB/view?usp=drive_link)**

The same video is behind the **Watch Demo** button on the landing page. The
URL comes from `DEMO_VIDEO_URL` in `.env`, so you can point it somewhere else
without touching any code; leave it blank and the button disappears rather
than linking to nothing.

---

## Contents

1. [Project report](#1-project-report)
2. [Features](#2-features)
3. [Architecture and technology](#3-architecture-and-technology)
4. [Setup — run it on your machine](#4-setup--run-it-on-your-machine)
5. [Configuration reference](#5-configuration-reference)
6. [Using the app](#6-using-the-app)
7. [Testing](#7-testing)
8. [Languages and translation](#8-languages-and-translation)
9. [Optional components](#9-optional-components-ollama-redis-postgresql-ocr)
10. [Project structure](#10-project-structure)
11. [API and routes](#11-api-and-routes)
12. [Security and privacy](#12-security-and-privacy)
13. [Troubleshooting](#13-troubleshooting)
14. [Status and known limitations](#14-status-and-known-limitations)

---

## 1. Project report

### Problem

Financial fraud in India increasingly reaches people through WhatsApp
forwards, SMS, Telegram "tip" groups and fake links: guaranteed-return
schemes, fake KYC updates, OTP requests, electricity-disconnection threats,
"SEBI-approved" trading clubs. The people most exposed are often first-time
smartphone users who are more comfortable in Hindi or Tamil than in English,
and who are pushed to act *immediately*.

Most financial apps either sell products or give advice. Few help a person
slow down and understand what is in front of them.

### Goal

Give people a calm, trustworthy companion that:

- **explains** financial terms and messages in plain language, in their own
  language, by voice or text;
- **surfaces warning signals** in a suspicious message, link, screenshot or
  PDF, with the exact words that triggered each signal and what to verify;
- **creates a pause** before a decision through a short structured reflection;
- **builds understanding** through short trilingual lessons and links to
  official sources (SEBI, RBI, AMFI, the national cybercrime portal);
- **respects privacy** by default: nothing personal is remembered unless the
  person turns it on.

### What NIRVAAN will never do

| | |
|---|---|
| ⛔ | Recommend buying, selling or holding anything |
| ⛔ | Predict prices, returns or personal outcomes |
| ⛔ | Rank or compare investments for a user |
| ⛔ | Recommend a broker, platform or product, or earn commission |
| ⛔ | Ask for or store a password, OTP, PIN, CVV or card number |
| ⛔ | Say a message is "safe" or "definitely a scam" |

Asked *"Should I buy XYZ?"*, NIRVAAN explains why it won't decide for the
person and offers to walk through the information instead. Analysis results
only ever say **Multiple Safety Signals Detected**, **Needs Verification** or
**No Obvious Warning Signals Detected**, always with the evidence and what is
still unverified.

### Approach

- **Design first.** The interface started as 17 Google Stitch design exports
  (the `nirvaan_*` folders). `scripts/extract_templates.py` turned them into
  Jinja templates; the visual design is preserved and every screen is now
  wired to real data.
- **Server-rendered, progressively enhanced.** FastAPI renders pages; small
  vanilla-JS modules add interactivity (voice, uploads, multi-step flows).
  Every core action also works as a plain form post.
- **Guardrails as code.** `app/services/responsible_ai.py` screens every input
  (credential masking, prompt-injection detection, advice/prediction requests)
  and every model output before it reaches the person.
- **Local-first AI.** A local model via Ollama when available; otherwise a
  reviewed, deterministic offline answer bank in all three languages. Nothing
  silently pretends to be a model.
- **Honest UI.** Controls that cannot work yet are shown as unavailable; no
  fake progress, fake results or fake "saved!" messages.

### Outcome

A working web application with 14 product pages, a JSON API, background job
processing, printable reports, a personal data export, full Hindi coverage and
broad Tamil coverage, responsive layouts from 390 px phones to 1440 px
desktops, and **174 passing automated tests**.

---

## 2. Features

| Area | What it does |
|---|---|
| **Landing page** | Illustrated hero, features, "For Bharat", about, help; language switcher. |
| **Accounts** | Register, sign in/out, sign out of all devices, email verification, password reset, lockout after failed attempts, optional gender (chooses the companion avatar). |
| **Dashboard** | Time-of-day greeting, resilience score, streak, counts, four feature shortcuts, recent activity with a summary pop-up per item (message checks open their full result with "Check another"). |
| **Talk to NIRVAAN** | Browser speech recognition (en-IN / hi-IN / ta-IN) or typed questions → `/api/talk` → guardrails → model or offline answer → read aloud (play / pause / replay / slower). Live transcript, mute, voice settings, and an explanation panel that follows each question. |
| **Check a Message** | Four inputs: **text**, **link** (address analysed, page never fetched), **image** (preview; OCR if installed, otherwise the person types the visible text), **PDF** (text extracted with pypdf). Rule-based signal engine with evidence spans, what to verify and what remains uncertain. Past checks list; save to journal. |
| **Batch Analysis** | Up to 20 messages, links, images or PDFs in one job, processed in the background with live progress; per-item results, past batches, printable summary and CSV export. |
| **Pause & Reflect** | Five steps (Reason → Evidence → Horizon → Emotions → Review), answers kept between steps, review and edit, saved as a reflection that feeds the score and journey. Optional link to a past check; optional journal entry. |
| **Learn & Explore** | Ten lessons (mutual funds, SIP, scams, risk, investor rights, budgeting, UPI/OTP safety, …) each with **Simple / Detailed / Example / Analogy** text in English, Hindi and Tamil, **Listen** (speech in the page language), progress, Resume Learning, bookmarks with a Saved lessons list, filter chips, and verified links to official sites. |
| **My Journey** | Resilience score, 4-week activity heatmap, streak, reflection patterns, badges, exportable resilience report. |
| **Decision Readiness** | Readiness scorecard from the latest reflection and any linked message check. |
| **Family Mode** | Linked family members, consent status and granted scopes (e.g. safety alerts only). |
| **Privacy Center** | Memory, analysis history, voice transcripts, uploaded files and family access switches; delete memories, history, transcripts or journal; export all data as a ZIP. |
| **Settings** | Profile, language, voice speed and read-aloud, accessibility (large text, high contrast), offline cache, data saver, notifications, active sessions (end other sessions), delete account. |
| **Help & Support** | FAQ, what to do if money was lost (1930 helpline, cybercrime.gov.in, SEBI SCORES, RBI CMS). |
| **Notifications** | Bell with unread count; opening a notification marks it read and goes to its page; mark all as read. |
| **Reports & export** | Resilience report and batch summary as print-ready pages ("Save as PDF"), batch CSV, personal data ZIP. |
| **Admin console** | Aggregate counts only (no private content): users, sessions, analyses, provider health, AI usage (calls by provider, offline share, latency), recent audit events. |
| **Offline / PWA** | Service worker caches static assets and a few lesson pages; offline notes sync into the journal later. |
| **Responsive** | Desktop sidebar; below 1024 px the sidebar becomes a slide-in menu. No horizontal scrolling at 390 / 768 / 1024 / 1440 px. |

---

## 3. Architecture and technology

| Layer | Technology |
|---|---|
| Web framework | FastAPI, Uvicorn |
| Templates / UI | Jinja2, Tailwind CSS (CDN), Material Symbols, vanilla JavaScript |
| Database | SQLAlchemy 2 + Alembic; SQLite for development, PostgreSQL for deployment |
| Auth & security | Argon2id password hashing, DB-backed sessions (hashed tokens), double-submit CSRF, rate limiting, strict security headers / CSP |
| AI | Provider registry with failover: Ollama (`qwen2.5:7b`) → deterministic offline provider |
| Speech | Browser Web Speech API (recognition + synthesis) |
| Documents | pypdf (PDF text); optional OCR (easyocr / pytesseract) |
| Scaling (optional) | Redis (shared rate limits + cache), RQ (job queue + worker) |
| Tests | pytest, FastAPI TestClient, fakeredis |

Request flow for a typical page:

```
Browser ─► FastAPI route ─► page_context/<page>.py (DB queries, user-scoped)
        ◄─ Jinja template ◄─ ui_translate (Hindi/Tamil post-render) ◄─┘
```

Request flow for a Talk or Check request:

```
input ─► responsible_ai.check_input (mask credentials, refuse advice requests)
      ─► analysis engine / AI provider registry (Ollama or offline bank)
      ─► responsible_ai.check_output ─► stored only if privacy settings allow
```

More detail, including database diagrams and the scaling design, is in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## 4. Setup — run it on your machine

### Prerequisites

- **Python 3.11 or newer** (3.14 is tested). Check with `python --version`.
  On Windows with several Pythons installed, use `py -3.14` (or your version)
  to create the virtual environment.
- **Git**, and a modern browser. **Chrome or Edge** is recommended for voice
  input; Firefox has no speech recognition (typing still works).
- Optional: [Ollama](https://ollama.com) for full AI answers, Redis for
  multi-worker deployments, PostgreSQL for production.

Nothing else is required. The database, content and demo accounts are all
created by the commands below — there is no data file to obtain separately.

### Step by step

Every command below is run from the project folder: the one that contains
`app/`, `requirements.txt` and this README.

**1. Clone the repository**

```bash
git clone https://github.com/rahularulbalan-011105/nexora_nirvaana_sangyan.git
cd nexora_nirvaana_sangyan
```

> If you received the project as a ZIP instead, unzip it and `cd` into the
> folder that contains `app/` — that folder is the project root, and the rest
> of the steps are identical.

**2. Create and activate a virtual environment**

```bash
# Windows (PowerShell)
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Windows (Git Bash)
py -3.14 -m venv .venv
source .venv/Scripts/activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

**3. Install dependencies**

```bash
python -m pip install -r requirements.txt
```

**4. Configure**

```bash
cp .env.example .env          # PowerShell: Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Paste the generated value into `.env` as `SECRET_KEY=...`. **Do not leave the
placeholder** — it signs session and password-reset tokens.

Everything else has a working default: the app uses SQLite at
`data/nirvaan.db`, prints emails to the terminal instead of sending them, and
falls back to the offline AI provider if Ollama isn't running. Two optional
lines you may want:

```ini
DEMO_VIDEO_URL=https://drive.google.com/file/d/1ERj4PQzkbVaEBGn3IAsJUiPc7NxreZsB/view?usp=drive_link
OLLAMA_MODEL=qwen2.5:7b
```

`DEMO_VIDEO_URL` is where the landing page's **Watch Demo** button goes.
Leave it blank and the button is not rendered at all.

`.env` is git-ignored and must never be committed; `.env.example` is the
committed template.

**5. Create the database and load content**

```bash
python -m alembic upgrade head
python scripts/seed.py --demo-users
```

This creates the schema, safety rules, lessons and three demo accounts with
realistic activity (checked messages, reflections, a batch job, journal
entries, notifications, a family link). Running the seed again is safe; it
never duplicates data.

**6. Run**

```bash
python -m uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000**.

> **Always run tools as `python -m <tool>`** (uvicorn, alembic, pytest). If
> several Pythons are installed, bare `uvicorn` may belong to a different
> interpreter and fail with `ModuleNotFoundError`.
>
> On Windows, `--reload` sometimes misses Python file changes. If a code
> change doesn't show up, stop the server (Ctrl+C) and start it again.

### All of it in one block

Once you have cloned the repository and `cd`-ed into it:

```powershell
# Windows (PowerShell)
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(48))"   # paste into .env
python -m alembic upgrade head
python scripts/seed.py --demo-users
python -m uvicorn app.main:app --reload
```

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(48))"   # paste into .env
python -m alembic upgrade head
python scripts/seed.py --demo-users
python -m uvicorn app.main:app --reload
```

### Check that it worked

```bash
python -m pytest                   # expect: 174 passed
curl http://127.0.0.1:8000/api/health
```

`/api/health` reports the database, both AI providers, Redis and the job
queue. A healthy first run with nothing optional installed looks like this —
`ollama: healthy false` is expected and **not** an error, because the offline
provider takes over:

```json
{"status": "ok",
 "checks": {"database": {"healthy": true, "dialect": "sqlite"},
            "ai_providers": [{"name": "ollama", "healthy": false},
                             {"name": "local",  "healthy": true}],
            "ai_available": true,
            "redis": {"backend": "memory"},
            "queue": {"backend": "thread"}}}
```

Then open **http://127.0.0.1:8000** and sign in with one of the demo
accounts below.

### Demo accounts

| Role | Email | Password | What you'll see |
|---|---|---|---|
| User | `priya@nirvaan.local` | `NirvaanDemo2026` | Full demo history: checks, reflections, batch, lessons, notifications |
| Family assistant | `arun@nirvaan.local` | `NirvaanDemo2026` | Linked to Priya in Family Mode |
| Admin | `admin@nirvaan.local` | `QuietLotus7Harbour` | Admin console at `/admin` |

New accounts start empty and fill up as you use the app.

### Health check

```bash
curl -s http://127.0.0.1:8000/api/health | python -m json.tool
```

Shows the database, AI providers (Ollama / offline), Redis and job-queue
status.

---

## 5. Configuration reference

All settings come from `.env` (see `.env.example`).

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | dev placeholder | Signs tokens. **Must be changed.** |
| `APP_ENV` | `development` | `production` enables HSTS and stricter behaviour. |
| `DEBUG` | `true` | Debug logging. |
| `USE_SQLITE_FALLBACK` | `true` | Use SQLite instead of `DATABASE_URL`. |
| `SQLITE_PATH` | `data/nirvaan.db` | SQLite file location. |
| `DATABASE_URL` | Postgres URL | Used when `USE_SQLITE_FALLBACK=false`. |
| `SESSION_TTL_HOURS` | `72` | Sign-in lifetime. |
| `COOKIE_SECURE` | `false` | Set `true` behind HTTPS. |
| `RATE_LIMIT_LOGIN_PER_MIN` | `5` | Sign-in/register attempts per IP per minute. |
| `RATE_LIMIT_API_PER_MIN` | `60` | API calls per IP per minute. |
| `REDIS_URL` | empty | e.g. `redis://localhost:6379/0`. Empty = in-memory. |
| `AI_PROVIDER_ORDER` | `ollama,local` | Provider preference order. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server. |
| `OLLAMA_MODEL` | `qwen2.5:7b` | Model name. |
| `MAIL_BACKEND` | `console` | `console` prints emails to the terminal; `smtp` sends them. |
| `SMTP_*`, `MAIL_FROM` | | SMTP settings when `MAIL_BACKEND=smtp`. |
| `UPLOAD_DIR` | `data/uploads` | Where uploads are kept (only if the user allows it). |
| `MAX_UPLOAD_MB` | `10` | Upload size limit. |
| `DEMO_VIDEO_URL` | empty | Walkthrough video behind the landing page's **Watch Demo** button. Blank hides the button. |

---

## 6. Using the app

1. **Sign in** as Priya (above) or create an account.
2. **Switch language** from the top bar (English / हिन्दी / தமிழ்). The
   whole interface changes, including Talk answers and lesson content.
3. **Check a Message**: paste a suspicious message, a link, a PDF, or a
   screenshot (type the text you see if OCR isn't installed) → **Analyse**.
4. **Talk to NIRVAAN**: press **Start listening** (allow the microphone) or
   type a question such as *"What is SIP?"* or *"Is this message safe?"*.
5. **Pause & Reflect** before a decision; your answers feed the resilience
   score on the dashboard and My Journey.
6. **Learn & Explore**: open a lesson, switch between Simple / Detailed /
   Example / Analogy, press **Listen**, bookmark it, mark it complete.
7. **Privacy Center** to control what is stored and to export or delete data.

---

## 7. Testing

```bash
python -m pytest              # 174 tests, about 15 seconds
python -m pytest tests/test_check.py -q     # one area
```

| Test file | Covers |
|---|---|
| `test_auth_security.py` | registration, login, lockout, sessions, CSRF, RBAC, data isolation |
| `test_guardrails.py` | credential masking, injection detection, advice/prediction refusals, output screening |
| `test_check.py` | text / link / image / PDF analysis, privacy flags, past checks |
| `test_batch.py` | batch creation, processing, validation, ownership |
| `test_reflect.py` | reflection flow, label mapping, persistence |
| `test_learn.py` | lessons, progress, bookmarks, language content |
| `test_account.py` | settings, privacy toggles, deletions, account removal |
| `test_scalability.py` | Redis rate limiter, cache, job queue and fallbacks (fakeredis) |
| `test_landing.py` | landing page, the `/demo` redirect, and hiding **Watch Demo** when no video is configured |

Tests use their own database and force `REDIS_URL` off. Browser checks
during development were done with Playwright against a running server.

---

## 8. Languages and translation

NIRVAAN supports **English (`en`), Hindi (`hi`) and Tamil (`ta`)**. The
language comes from (in order) `?lang=`, the `nirvaan_lang` cookie, the
user's saved preference, then the browser.

There are three layers:

1. **Key-based strings** — `app/i18n/{en,hi,ta}.json`, used through `t("key")`
   in templates (auth pages, greetings, guardrail messages).
2. **Whole-page translation** — templates are written in English. After a
   page renders, `app/services/ui_translate.py` replaces every text node and
   `placeholder` / `title` / `aria-label` / `alt` attribute whose exact text is
   in `app/i18n/ui/{hi,ta}.json`. User content passes through untouched.
   Relative times ("7 min ago") are translated by pattern.
3. **Native content** — lessons (`app/services/learning_content.py`) and
   offline Talk answers (`app/services/talk_answers.py`) are written in each
   language directly.

Updating translations after changing UI text:

```bash
python -m uvicorn app.main:app            # in one terminal
python scripts/extract_ui_strings.py      # writes app/i18n/ui/source_en.json, lists what's missing
# translate the missing strings into app/i18n/ui/parts/hi_<n>.json / ta_<n>.json
python scripts/merge_ui_translations.py   # merges parts into hi.json / ta.json
```

Catalogs reload automatically when the files change. Strings that JavaScript
shows at runtime live in a hidden `<div id="...-strings">` block in each page,
so they are translated with the page.

---

## 9. Optional components (Ollama, Redis, PostgreSQL, OCR)

### Ollama — full AI answers

```bash
ollama pull qwen2.5:7b
ollama serve            # if it isn't already running
```

Without it, Talk to NIRVAAN answers from the reviewed offline bank (about ten
common topics in all three languages) and says plainly when it can't help.

### Redis — multiple workers and a real job queue

```bash
python -m pip install -r requirements-redis.txt
# .env:  REDIS_URL=redis://localhost:6379/0
python scripts/worker.py                                   # background job worker
python -m uvicorn app.main:app --workers 4                 # several web workers
```

With Redis, rate limits, AI provider health and repeated Talk answers are
shared across workers, and batch jobs go to an RQ queue. Without Redis (or if
it is unreachable, or no worker is running) everything falls back to
in-process behaviour automatically. Multiple workers in production also need
PostgreSQL (SQLite doesn't handle concurrent writes well).

### PostgreSQL

```bash
createdb nirvaan
psql nirvaan -c 'CREATE EXTENSION IF NOT EXISTS vector;'
python -m pip install -r requirements-postgres.txt
# .env:  USE_SQLITE_FALLBACK=false
#        DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/nirvaan
python -m alembic upgrade head
python scripts/seed.py --demo-users
```

### OCR for screenshots

```bash
python -m pip install -r requirements-ml.txt   # large: includes torch
```

or install `pytesseract` plus the Tesseract binary. The app detects an OCR
engine at runtime; without one, image checks ask the person to type the text.

---

## 10. Project structure

```
.
├── app/
│   ├── main.py                 # app factory, middleware (security headers), routers
│   ├── config.py               # settings from .env
│   ├── db.py, deps.py          # DB session, auth/CSRF/rate-limit dependencies
│   ├── navigation.py           # sidebar items and breadcrumbs
│   ├── templating.py           # render(), shared context, language resolution
│   ├── models/                 # SQLAlchemy models (users, analysis, reflection, learning, voice, family, system)
│   ├── routers/
│   │   ├── pages.py            # page routes (landing, dashboard, feature pages, admin)
│   │   ├── auth.py             # register / login / logout / verify / reset
│   │   ├── api.py              # health, language, notifications, talk, profile
│   │   ├── feature_check.py    # /api/check
│   │   ├── feature_batch.py    # /api/batch
│   │   ├── feature_reflect.py  # /api/reflect
│   │   ├── feature_learn.py    # /learn/{slug}, /api/learn/*
│   │   ├── feature_account.py  # /api/account/* (settings, privacy, deletions)
│   │   └── reports.py          # printable reports, CSV, data export ZIP
│   ├── page_context/           # one module per page: build(db, user) -> template data
│   ├── services/
│   │   ├── responsible_ai.py   # guardrails (input/output screening)
│   │   ├── ai/                 # provider interface, Ollama, offline provider, registry
│   │   ├── analysis.py         # safety signal engine; analysis_inputs.py: link/PDF/image extraction
│   │   ├── batch.py, jobs.py   # batch processing; job queue (thread pool or RQ)
│   │   ├── talk.py, talk_answers.py   # Talk turn pipeline; trilingual offline answers
│   │   ├── learning_content.py, learning_progress.py
│   │   ├── account.py, auth.py, audit.py, mail.py
│   │   ├── i18n.py, ui_translate.py   # translation layers
│   │   └── cache.py, redis_client.py  # optional Redis
│   ├── security/               # CSRF, rate limiting, tokens
│   ├── i18n/                   # en/hi/ta key catalogs; ui/ = whole-page translations
│   ├── templates/              # base.html, partials/, pages/, reports/
│   └── static/                 # css, js (per feature), img (avatars, hero art), service worker
├── alembic/                    # migrations
├── scripts/                    # seed, worker, translation tools, template extraction, smoke test
├── tests/                      # pytest suite
├── docs/ARCHITECTURE.md        # detailed design
├── nirvaan_*/ …                # original Google Stitch design exports (reference only, never edited)
├── requirements*.txt           # base, postgres, redis, ml extras
├── .env.example                # committed config template (.env itself is ignored)
├── .gitignore                  # secrets, .venv, generated data, caches
├── CLAUDE.md                   # conventions and rules for changing the code
└── data/                       # SQLite DB, uploads, RAG index (all git-ignored)
```

### What is and isn't committed

Everything needed to run is in the repository. These are deliberately **not**:

| Not committed | Recreate it with |
|---|---|
| `.env` | `cp .env.example .env` and set `SECRET_KEY` |
| `.venv/` | `python -m venv .venv && pip install -r requirements.txt` |
| `data/nirvaan.db` | `python -m alembic upgrade head && python scripts/seed.py --demo-users` |
| `data/uploads/`, `data/rag/` contents | created at runtime (folders kept via `.gitkeep`) |
| `app/i18n/ui/source_en.json` | `python scripts/extract_ui_strings.py` (a working file; the app never reads it) |
| `__pycache__/`, `.pytest_cache/` | regenerated automatically |

The merged translation catalogs `app/i18n/ui/hi.json` and `ta.json` **are**
committed — the app reads those at runtime.

---

## 11. API and routes

Pages (all require sign-in except landing and auth pages):

`/` · `/dashboard` · `/talk` · `/check` · `/batch` · `/reflect` · `/learn` ·
`/learn/{slug}` · `/journey` · `/decision-readiness` · `/explain` · `/family`
· `/privacy` · `/settings` · `/offline` · `/help` · `/admin` (admin only)

Eleven of those are in the sidebar. Three are reached another way, which is
worth knowing before you go looking for a button:

| Page | How you get there |
|---|---|
| `/explain` | the **Explain Simply** chip on `/talk` |
| `/offline` | **Settings → Offline & Data Saver → Offline Mode** |
| `/decision-readiness` | **by URL only** — nothing in the UI links to it yet |

Public: `/` (landing) and `/demo`, which redirects to `DEMO_VIDEO_URL`.

Auth: `GET/POST /login`, `GET/POST /register`, `POST /logout` (`all=1` signs
out every device), `/verify-email`, `/forgot-password`, `/reset-password`.

JSON / form API (all POSTs need the CSRF token, as a form field `_csrf` or
the `X-CSRF-Token` header):

| Method & path | Purpose |
|---|---|
| `GET /api/health` | Database, AI providers, Redis, queue |
| `POST /api/language` | Switch language |
| `POST /api/talk`, `POST /api/talk/end` | One Talk turn; end a voice session |
| `POST /api/check`, `GET /api/check/{id}`, `POST /api/check/{id}/journal` | Analyse text/link/image/PDF; reopen a past check; save to journal |
| `POST /api/batch`, `GET /api/batch/{id}`, `POST /api/batch/{id}/journal` | Create a batch; poll progress/results; save to journal |
| `POST /api/reflect/complete` | Save a completed reflection |
| `POST /api/learn/{slug}/view` · `/progress` · `/complete` · `/bookmark` | Lesson progress and bookmarks |
| `POST /api/account/preferences` · `/privacy` | Save settings and privacy switches |
| `GET /api/account/memories`, `POST .../memories/{id}/delete`, `.../memories/delete-all` | Manage memory |
| `POST /api/account/history/{kind}/delete` | Delete analyses, transcripts or journal |
| `POST /api/account/sessions/{id}/revoke`, `POST /api/account/delete` | End a session; delete the account |
| `POST /api/notifications/{id}/open`, `POST /api/notifications/read-all` | Read state |
| `POST /api/profile/gender` | Avatar preference |
| `GET /reports/journey`, `GET /reports/batch/{id}[.csv]`, `GET /privacy/export.zip` | Reports and data export |

---

## 12. Security and privacy

- Passwords hashed with Argon2id; sessions are random tokens stored hashed in
  the database; lockout after repeated failed sign-ins.
- CSRF protection on every state-changing request; rate limiting on sign-in
  and API calls; strict Content-Security-Policy and security headers.
- Every query for personal data is scoped to the signed-in user; other users'
  records return 404.
- Credentials (OTP, PIN, card numbers, passwords) are masked before anything
  is analysed or stored; there is no database column for them.
- Conservative defaults: memory **off**, voice transcripts **not stored**,
  uploaded files **not retained**, family access **none**, analytics
  **off**. Each is a switch in the Privacy Center.
- Administrators see aggregate numbers and system events only — never
  journals, memories, transcripts or analyses.
- People can export everything stored about them (ZIP) or delete it,
  including the whole account.

---

## 13. Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` when starting | Use `python -m uvicorn …` from the activated virtual environment. |
| Python 3.9/3.10 errors | Create the venv with Python 3.11+ (`py -3.14 -m venv .venv`). |
| "Too many attempts" on sign-in | Login is limited to 5 attempts per minute per IP; wait a minute. |
| Code change not visible | Restart the server (Windows `--reload` can miss changes). |
| Port 8000 in use | `python -m uvicorn app.main:app --port 8001`. |
| Microphone doesn't work | Use Chrome or Edge, allow microphone access, or type instead. |
| No voice for Hindi/Tamil | Install a Hindi/Tamil text-to-speech voice in the OS; the app shows a note when none is installed. |
| Talk answers are short/generic | Ollama isn't running; start it and `ollama pull qwen2.5:7b`. |
| "Text could not be read" for a PDF | It's a scanned PDF with no text layer; paste the text instead. |
| Page stuck in one language | Pick a language from the top bar, or open any page with `?lang=en`. |
| No **Watch Demo** button on the landing page | `DEMO_VIDEO_URL` is blank in `.env`. Set it and restart the server. |
| `ModuleNotFoundError: app` when running a script | Run it from the project root, not from inside `scripts/`. |

---

## 14. Status and known limitations

**Working:** every page listed above with real, user-scoped data; 174
automated tests; responsive at 390–1440 px; no console errors on any page.

**Limitations:**

- OCR is optional; without it, image checks rely on typed text.
- Links are judged by their address only; pages are never fetched.
- Without Ollama, Talk covers about ten topics from the offline answer bank.
  With Ollama on typical laptop hardware, expect **10–20 s** per answer, and
  longer for the first question after the model loads.
- **Translation coverage is uneven:** Hindi covers about **84 %** of UI
  strings, Tamil about **55 %**. Untranslated strings fall back to English,
  most visibly on Settings, Check and Learn in Tamil. Run the workflow in
  section 8 to close the gap.
- `/decision-readiness` works but nothing in the UI links to it yet.
- `nirvaan_market_education/` is the one Stitch design with no route behind
  it; the page is not built.
- Dates are shown in UTC.
- Redis support is tested with fakeredis; multi-worker deployment needs
  PostgreSQL and shared upload storage.
- Family invitations, two-factor authentication and a support-ticket system
  are not built; the UI marks them as unavailable.

---

## Licence and intent

NIRVAAN is non-commercial and built as a public good. It has nothing to sell,
takes no commission and promotes no financial product.
