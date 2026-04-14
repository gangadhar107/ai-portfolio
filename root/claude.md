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
| Database (prod) | Neon free tier | Swap DATABASE_URL only |
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
Migration to Neon at deploy time requires only a connection string change.

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
│   ├── tracking.py           # Ref code generator, visit logger, email notify
│   └── intelligence.py       # Portfolio Intelligence — Groq insights
├── database/
│   └── __init__.py           # get_connection(), get_cursor() via psycopg (psycopg3)
├── templates/
│   ├── base.html             # Jinja2 base layout — dark theme, nav, footer
│   ├── home.html             # Home page
│   ├── about.html            # About page
│   ├── projects.html         # Projects page
│   ├── contact.html          # Contact + Calendly embed
│   ├── admin.html            # Private application form — password protected
│   ├── dashboard.html        # Private analytics dashboard — password protected
│   └── insights.html         # Portfolio Intelligence page — password protected
├── static/
│   └── css/                  # PostHog-inspired dark theme
└── sql_queries/              # 7 named SQL insight query files
```

---

## Database Schema

### applications
```sql
CREATE TYPE outcome_type AS ENUM ('pending', 'got_call', 'rejected', 'no_response');

CREATE TABLE applications (
    id            SERIAL PRIMARY KEY,
    company_name  TEXT NOT NULL,
    person_name   TEXT,
    position      TEXT NOT NULL,
    date_applied  DATE NOT NULL,
    outcome       outcome_type DEFAULT 'pending',
    ref_code      TEXT UNIQUE,
    notes         TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
```

### visits
```sql
CREATE TABLE visits (
    id            SERIAL PRIMARY KEY,
    ref_code      TEXT NOT NULL,
    timestamp     TIMESTAMPTZ DEFAULT NOW(),
    visit_count   INTEGER DEFAULT 1,
    pages_visited TEXT,
    country       TEXT
);
```

### ref_codes
```sql
CREATE TABLE ref_codes (
    id              SERIAL PRIMARY KEY,
    ref_code        TEXT UNIQUE NOT NULL,
    application_id  INTEGER REFERENCES applications(id),
    created_date    TIMESTAMPTZ DEFAULT NOW(),
    is_active       BOOLEAN DEFAULT TRUE
);
```

**Key relationship:** ref_code connects all three tables.
Application has a ref_code. Visits log that ref_code. Join all three for full funnel view.

---

## Environment Variables

```bash
# Local PostgreSQL (dev)
DATABASE_URL=postgresql://portfolio_user:password@localhost:5432/portfolio_db

# Neon cloud PostgreSQL (prod — set in Vercel dashboard only)
# DATABASE_URL=postgresql://user:pass@host.neon.tech/portfolio_db

# Dashboard and admin password
DASHBOARD_PASSWORD=your_password_here

# Email notification settings
NOTIFICATION_EMAIL=your_gmail@gmail.com
NOTIFICATION_EMAIL_PASSWORD=your_gmail_app_password

# Base URL for ref code links
BASE_URL=https://ai-portfolio-three-green.vercel.app

# Calendly embed link
CALENDLY_LINK=https://calendly.com/your-link

# Groq API key for Portfolio Intelligence
GROQ_API_KEY=your_groq_key_here
```

---

## Routes

### Public Routes
| Method | Path | Description |
|---|---|---|
| GET | / | Home page — triggers visit logger if ?ref= present |
| GET | /about | About page |
| GET | /projects | Projects page |
| GET | /contact | Contact page with Calendly embed |

### Private Routes (password protected)
| Method | Path | Description |
|---|---|---|
| GET | /admin | Application form — generate ref codes |
| POST | /admin/application | Save application + generate ref link |
| GET | /dashboard | Analytics dashboard |
| POST | /dashboard/update-outcome | Update application outcome |
| GET | /insights | Portfolio Intelligence full page |
| POST | /insights/refresh | Clear cache and regenerate insights |

### API Routes
| Method | Path | Description |
|---|---|---|
| POST | /generate-ref | Generate ref code, return full URL |

---

## Key Functions

### routers/tracking.py
- `generate_ref_code()` — Python secrets module, 8-char alphanumeric, unique
- `save_application()` — inserts to applications + ref_codes in a transaction
- `log_visit()` — inserts to visits, clears insight cache on success
- Email notification via smtplib — fires on first visit only per ref code

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

---

## Security Rules

- All secrets in .env locally, Vercel env vars in production — never in code
- Ref codes use Python secrets module — cryptographically secure
- /admin and /dashboard fully blocked without correct password
- Invalid ?ref= values silently ignored — no 500 errors, no fake rows
- Rate limiting on visit logger — 1 log per IP per hour per ref code
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
| Phase 6 | Deployed to Vercel + Neon, live URL | COMPLETE |
| v1.1 | Portfolio Intelligence — Groq AI insights layer | IN PROGRESS |

---

## Version Roadmap

**v1.0 — LIVE**
Portfolio + ref code tracking + private dashboard + SQL analytics.
Zero AI features. $0/month.

**v1.1 — IN PROGRESS**
Portfolio Intelligence. Groq + LLaMA 3.3 70B analyses visit and application
data and generates actionable insights. Event-based + manual refresh.
Insight cards on dashboard and full /insights page.

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

**Active feature:** Portfolio Intelligence (v1.1)
**Files to create:** routers/intelligence.py + templates/insights.html
**Files to modify:** templates/dashboard.html (add 2-card summary section)
**Security status:** Complete — both issues resolved and committed
**Last commit:** d608615 — fix: move HMAC session key to environment variable
**Model used:** Groq llama-3.3-70b-versatile
**Key constraint:** In-memory cache only, resets on restart, acceptable for this project
**Do not:** Use Redis, database caching, or any paid services
**Do not:** Touch any existing routes or templates except dashboard.html (add insights summary card)
