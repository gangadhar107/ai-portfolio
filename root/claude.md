# CLAUDE.md — AI Portfolio Project Brain

> This file is the single source of truth for Claude Code.
> Read this fully before writing any code, suggesting any change,
> or answering any question about this project.

---

## Who Is Building This

**Name:** Gangadhar Allam
**Background:** Ex-Junior Data Analyst transitioning into AI-powered development
**Location:** Bengaluru, India
**Coding level:** Not an expert. Explain everything in plain English before writing code.
**Build tool:** Google Antigravity IDE with Claude as the model
**Goal:** Get hired as an AI Engineer, Analytics Engineer, or Vibe Coder

---

## What This Project Is

A self-measuring portfolio website that tracks which job applications lead
to portfolio views and converts that data into actionable job search insights.

This is not a standard portfolio. It is a three-stage feedback loop:

- Stage 1: Did the recruiter open my portfolio link? If not — ghost job or buried inbox. Fix outreach.
- Stage 2: Did they view the portfolio? If yes — application cleared first filter.
- Stage 3: Did I get a call? If yes — profile landed. If no — something did not convert. Fix that specific thing.

**Live URL:** https://ai-portfolio-three-green.vercel.app
**GitHub:** https://github.com/gangadhar107/ai-portfolio

---

## Core Rules — Never Violate These

1. Never commit .env to GitHub under any circumstances
2. Never delete existing code — comment out, never delete
3. Never use ORMs — write raw SQL with psycopg (psycopg3)
4. Never add complexity that is not in the current phase scope
5. Never skip a phase milestone before moving to the next
6. Always explain what a file or function does in plain English before writing code
7. Always handle errors gracefully — no 500 errors exposed to visitors
8. Always keep secrets in .env locally and Vercel environment variables in production
9. When in doubt, do less — build less, ship faster, measure everything

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Language | Python | Primary language |
| Framework | FastAPI + Jinja2 | Server-side templates, no React |
| Database (dev) | PostgreSQL local | Direct psycopg (psycopg3), no ORM |
| Database (prod) | CockroachDB serverless | Swap DATABASE_URL only (set in Vercel env vars) |
| DB Adapter | psycopg[binary] (psycopg3) | Raw SQL always |
| Charts | Chart.js | Dashboard visualisations |
| Hosting | Vercel free tier | Connected to GitHub |
| Email | Python smtplib | Visit notifications |
| AI Insights | Groq free tier | llama-3.3-70b-versatile |
| Booking | Calendly free tier | Embedded on contact page |
| Security | Snyk free tier | Connected to GitHub |
| Build Tool | Google Antigravity + Claude | Free tier |
| Total Cost | $0/month | |

**Why PostgreSQL over Supabase:** Supabase API issues encountered in Phase 1.
Switched to direct PostgreSQL with psycopg (psycopg3). Simpler, more reliable.
Migration to CockroachDB requires only a connection string change.

**CockroachDB + Vercel SSL note:** Prefer `sslmode=require` in `DATABASE_URL` on Vercel. `sslmode=verify-full` needs a CA file that is not present by default in the serverless runtime.

---

## Project Structure

```
ai-portfolio/
├── main.py                   # FastAPI app, all routes
├── requirements.txt          # Python dependencies
├── .env                      # Secrets — NEVER commit this
├── .env.example              # Placeholder template — commit this
├── .gitignore                # Protects .env, __pycache__, venv
├── CLAUDE.md                 # This file — project brain
├── routers/
│   ├── __init__.py
│   ├── tracking.py           # Ref code generator, visit logger, admin, dashboard, fit routes
│   └── intelligence.py       # Portfolio Intelligence — Groq insights (v1.1)
├── database/
│   └── __init__.py           # get_connection(), get_cursor() via psycopg (psycopg3)
├── services/
│   └── fit/                   # v1.3 Fit Engine (Groq extract + deterministic scoring)
│       ├── vocabulary.py
│       ├── normalization.py
│       ├── jd_parser.py
│       ├── matcher.py
│       ├── scoring.py
│       └── repository.py
├── templates/
│   ├── base.html             # Jinja2 base layout — dark theme, nav, footer
│   ├── home.html             # Home page
│   ├── about.html            # About page
│   ├── projects_final.html    # Projects page
│   ├── blog.html              # Writing page
│   ├── contact.html          # Contact + Calendly embed
│   ├── admin.html            # Private application form — password protected
│   ├── dashboard.html        # Private analytics dashboard — password protected
│   ├── context.html          # v1.3 Fit context editor + assessment history — password protected
│   └── insights.html         # Portfolio Intelligence page — password protected
├── static/
│   └── css/                  # PostHog-inspired dark theme
└── sql_queries/              # 7 named SQL insight query files
```

---

## Database Schema

Schema reference: [schema.sql](file:///c:/Users/ganga/OneDrive/Desktop/ai-portfolio/ai-portfolio/database/schema.sql)

### applications
- Core: `company_name`, `position`, `date_applied`, `outcome`, `ref_code`, `notes`
- v1.2 enrichment: `outreach_channel`, `contact_person`, `role_category`, `followed_up`, `follow_up_date`, `follow_up_response`, `outcome_date`, `rejection_reason`
- v1.3 fit status: `assessment_status` (`not_run`, `completed`, `weak_jd`, `failed`)

Outcome values are validated in code and treated as a controlled vocabulary: `pending`, `got_call`, `rejected`, `no_response`.

### ref_codes
- Maps `ref_code` → `application_id`

### visits
- One row per visit (ref-code traffic only)
- v1.2 tracking fields:
  - `visit_token` (unique per pageview for correct time tracking)
  - `is_return_visit`
  - `visit_source` (derived with fixed precedence)
  - `time_on_site` (visible time, updated via `/track-time`, idempotent using `GREATEST()`)
  - `utm_source`, `utm_medium` (stored only when `ref` is present; UTM-only visits remain GA4-only and do not touch Postgres)

### application_context (v1.3)
- Stores the active JD + resume text for a specific application.
- Enforces one active context per application (`is_active = TRUE`).

### fit_assessments (v1.3)
- Stores assessment attempts (history) and the latest usable assessment for dashboard display.
- JSONB fields: `matching_skills`, `missing_skills`, `jd_weights`, `rejected_terms`
- Key text fields:
  - `fit_score` (from matcher LLM)
  - `fit_confidence` and `confidence_score` (deterministic Python scoring)
  - `failure_reason` (controlled reasons like `jd_extraction_invalid`, `jd_extraction_empty`, `matcher_invalid`, `weighted_total_zero`, `score_invalid`)

**Key relationship:** ref_code connects all three tables.
Application has a ref_code. Visits log that ref_code. Join all three for full funnel view.

---

## Environment Variables

```bash
# Local PostgreSQL (dev)
DATABASE_URL=postgresql://portfolio_user:password@localhost:5432/portfolio_db

# CockroachDB (prod — set in Vercel dashboard only)
# Prefer sslmode=require on Vercel to avoid missing CA file errors.
# DATABASE_URL=postgresql://user:pass@host.cockroachlabs.cloud:26257/defaultdb?sslmode=require

# Dashboard and admin password
DASHBOARD_PASSWORD=your_password_here

# HMAC secret used to sign the auth cookie token (must be set)
SESSION_SECRET_KEY=your_random_hex_string

# Email notification settings
NOTIFICATION_EMAIL=your_gmail@gmail.com
NOTIFICATION_EMAIL_PASSWORD=your_gmail_app_password

# Base URL for ref code links
BASE_URL=https://ai-portfolio-three-green.vercel.app

# Calendly embed link
CALENDLY_LINK=https://calendly.com/your-link

# Groq API key for Portfolio Intelligence
GROQ_API_KEY=your_groq_key_here

# GA4 (frontend + server-side Measurement Protocol)
GA4_MEASUREMENT_ID=G-XXXXXXXXXX
GA4_API_SECRET=your_ga4_api_secret

# Internal traffic exclusion (comma-separated IPs)
EXCLUDED_IPS=1.2.3.4,5.6.7.8
```

---

## Routes

### Public Routes
| Method | Path | Description |
|---|---|---|
| GET | / | Home page — triggers visit logger if ?ref= present |
| GET | /about | About page |
| GET | /projects | Projects page |
| GET | /blog | Writing page |
| GET | /contact | Contact page with Calendly embed |

### Private Routes (password protected)
| Method | Path | Description |
|---|---|---|
| GET | /admin | Application form — generate ref codes |
| POST | /admin/application | Save application + generate ref link |
| GET | /dashboard | Analytics dashboard |
| POST | /dashboard/update-outcome | Update application outcome |
| GET | /admin/context/{application_id} | v1.3 Fit context editor + assessment history |
| POST | /admin/context/{application_id} | Save JD + resume context (activates new context, resets status) |
| POST | /admin/assess-fit | Run fit assessment and store results |
| GET | /insights | Portfolio Intelligence full page |
| POST | /insights/refresh | Clear cache and regenerate insights |

### API Routes
| Method | Path | Description |
|---|---|---|
| POST | /generate-ref | Generate ref code, return full URL |
| POST | /track-time | Update `time_on_site` for a single visit using `visit_token` (idempotent) |

---

## Key Functions

### routers/tracking.py
- `generate_ref_code()` — Python secrets module, 8-char alphanumeric, unique
- `save_application()` — inserts to applications + ref_codes in a transaction
- `log_visit()` — inserts a new visits row and returns `visit_token`; also clears insight cache
- `/track-time` — updates one row by `visit_token` and uses `GREATEST()` so duplicate beacons are safe
- Internal traffic exclusion:
  - IP-based via `X-Forwarded-For` + `EXCLUDED_IPS`
  - cookie-based via `portfolio_owner=true` after admin login
- Rate limiting: caps rapid repeats per `(ip, ref_code)` window (dedupe + anti-spam)
- Email notifications (optional): when configured, sends an email on first recruiter visit for a ref code
- GA4 Measurement Protocol (server-side): sends `recruiter_visit` when GA4 creds exist and `_ga` cookie provides a client_id

### routers/intelligence.py
- `collect_portfolio_data()` — queries all three tables, returns structured dict
- `generate_insights(data)` — calls Groq API, returns list of insight dicts
- `get_cached_insights()` — returns cache if under 1 hour old, else None
- `set_cached_insights(insights)` — saves insights with timestamp
- `clear_insights_cache()` — resets cache to empty

**Cache structure:**
```python
insight_cache = {
    "insights": [],
    "generated_at": None,  # datetime or None
}
```

**Cache is in-memory only. Resets on server restart. This is acceptable.**
Do not use Redis or database caching — unnecessary complexity.

**Cache invalidation triggers:**
- New visit logged
- New application created
- Application outcome updated

### database/__init__.py
- `get_connection()` — returns psycopg (psycopg3) connection from DATABASE_URL
- `get_cursor()` — returns connection + cursor together

### services/fit (v1.3 Fit Engine)
- `jd_parser.py` — Groq extracts JD requirements into `must_have / important / nice_to_have` JSON. Non-string items make the extraction invalid.
- `normalization.py` — normalizes skill terms onto a canonical vocabulary using synonyms + RapidFuzz; creates weighted JD weights.
- `matcher.py` — Groq produces canonical `matching_skills / missing_skills` + `fit_score` JSON. Non-string items make the match invalid.
- `scoring.py` — deterministic confidence score in Python + validation (`score_invalid` if out-of-range or non-finite).
- `repository.py` — raw SQL read/write for `application_context` and `fit_assessments`; dashboard query uses "latest attempt vs latest usable assessment" semantics.

---

## Security Rules

- All secrets in .env locally, Vercel env vars in production — never in code
- Ref codes use Python secrets module — cryptographically secure
- /admin and /dashboard fully blocked without correct password
- Invalid ?ref= values silently ignored — no 500 errors, no fake rows
- Internal traffic excluded via owner cookie and/or IP allowlist
- XSS inputs in ref codes handled safely
- Snyk scan connected to GitHub — all high/critical issues resolved
- .env verified never appears in git history

---

## Design System

| Property | Value |
|---|---|
| Background | #0f0f0f |
| Text | #f5f0e8 |
| Accent | #e8d44d |
| Card background | #1a1a1a |
| Card border | 1px solid rgba(255,255,255,0.1) |
| Body font | Inter |
| Code font | JetBrains Mono |
| Cards | 1px visible border, subtle hover lift, no floating shadows |
| Responsive | Mobile-first, 320px minimum width |

**Design inspiration:** PostHog.com — dark theme, bold typography, dense but readable.

---

## SQL Query Library

Saved in `/sql_queries/` — each file answers one specific question:

| File | Question |
|---|---|
| viewed_applications.sql | All applications where portfolio viewed at least once |
| high_intent.sql | Applications viewed more than once |
| viewed_no_call.sql | Viewed but no call received |
| conversion_rate.sql | Overall view-to-call conversion rate |
| conversion_by_position.sql | Conversion rate by position type |
| avg_time_to_view.sql | Average days from application to first view |
| weekly_trend.sql | Weekly view volume over time |

---

## Build Phase Status

| Phase | What Was Built | Status |
|---|---|---|
| Phase 0 | Project init, GitHub, .gitignore, FastAPI setup | COMPLETE |
| Phase 1 | PostgreSQL — 3 tables, psycopg (psycopg3) connection | COMPLETE |
| Phase 2 | Ref code tracking, visit logger, email, dashboard | COMPLETE |
| Phase 3 | Portfolio pages, PostHog dark theme, mobile responsive | COMPLETE |
| Phase 4 | SQL analytics, Chart.js charts, stat cards | COMPLETE |
| Phase 5 | Security audit, Snyk, rate limiting, input validation | COMPLETE |
| Phase 6 | Deployed to Vercel (DATABASE_URL points to cloud DB) | COMPLETE |
| v1.1 | Portfolio Intelligence — Groq AI insights layer | COMPLETE |
| v1.2 | GA4 + UTM-aware visit logging + time-on-site token tracking | COMPLETE |
| v1.3 | Fit Engine (context + deterministic scoring + dashboard columns) | IN PROGRESS |
| v1.4 | GA4 Cold Email Recruiter Intelligence events | IN PROGRESS |

---

## Version Roadmap

**v1.0 — LIVE**
Portfolio + ref code tracking + private dashboard + SQL analytics.
Zero AI features. $0/month.

**v1.1 — COMPLETE**
Portfolio Intelligence. Groq + LLaMA 3.3 70B analyses visit and application data and generates actionable insights.
Event-based + manual refresh. Insight cards on dashboard and full /insights page.

**v1.2 — COMPLETE**
Visit-quality improvements: per-visit tokens for time-on-site, internal traffic exclusion, GA4 integration, and UTM capture for ref-code visits.

**v1.3 — IN PROGRESS**
Fit Engine: store per-application JD + resume context, run LLM extraction/matching, and compute a deterministic fit confidence score. Add Context/Assessment/Fit/Priority/Disagreement columns to dashboard.

**v1.4 — IN PROGRESS**
GA4 Recruiter Intelligence for cold email traffic: `cold_email_visit_started`, `section_reached`, `project_engaged`, `active_time_milestone`, `outreach_initiated`.

**v2.0 — PLANNED**
RAG chatbot powered by Groq free tier. Single agent. Knows your work.
Surfaces Calendly link on booking intent. LangChain + ChromaDB.

**v3.0 — FUTURE**
Multi-agent layer using Claude Code subagents. PM routing agent, project
explainer agent, AI engineer agent, booking agent. Build after hired.

---

## Guiding Principles

These came from mentor feedback early in the project. Never violate them.

1. **Build less, ship faster, measure everything, iterate with data**
2. **Portfolio must stand on its own without AI** — if the chatbot disappeared tomorrow would a recruiter still be impressed?
3. **Never skip a milestone** before moving to the next phase
4. **Write a blog update after every milestone** — debugging stories are portfolio content
5. **Start applying while building** — tracking works from Phase 2 onward
6. **Resist adding complexity** when the current phase is unfinished
7. **Every feature must solve a real problem** — no building for building's sake

---

## Job Search Decision Framework

Use this to interpret your dashboard data:

- **Viewed + Got Call** → Profile and presentation working. Double down.
- **Viewed + No Call** → Something did not convert. Review project matching the role. Reorder cards.
- **Did Not View** → Outreach problem. Resume or email subject line needs work, not the portfolio.

---

## What Good Output Looks Like

When Claude Code finishes a task, the result should:
- Not break any existing route or template
- Handle all error cases gracefully
- Follow the dark theme design system
- Use raw SQL via psycopg (psycopg3) — no ORMs
- Keep secrets out of code
- Have a plain English explanation before every function
- End with a git commit message suggestion

---

## Current Task Context

**Active features:** Fit Engine (v1.3) + GA4 Recruiter Intelligence (v1.4)
**Fit engine scope:** Private admin only (dashboard + context editor). Reproducible scoring: LLM extracts/matches, Python computes weighted confidence score.
**GA4 cold-email scope:** Only fires GA4 events when `utm_medium=cold_email` and a `ref` exists (stored in sessionStorage); adds `data-*` hooks only to existing template elements.
**Model used:** Groq llama-3.3-70b-versatile
**Key constraints:**
- Raw SQL via psycopg (psycopg3)
- In-memory cache only for insights (no Redis)
- Do not store anonymous UTM-only visits in Postgres (GA4-only)
