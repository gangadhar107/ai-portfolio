# AI-Powered Portfolio

A self-measuring portfolio website that tracks which job applications lead to portfolio views and converts that data into actionable job search insights. It includes a private admin panel + dashboard for application tracking, plus optional Groq-powered insights and a resume/JD fit assessment workflow.

## What This Solves

Most applications disappear into a black box. This project turns your job search into a measurable funnel:

- Did the recruiter open the portfolio link?
- Did they actually view the portfolio?
- Did it convert into a call?

## Key Features

- **Ref-code tracking links**: every application gets a unique `?ref=` link.
- **Visit logging (Postgres)**: stores ref-code traffic, first visit timestamp, return visits, and time-on-site.
- **UTM attribution + GA4**: supports UTM capture for ref-code visits and server-side GA4 Measurement Protocol events (when configured).
- **Private admin panel**: create applications and generate ref links (password-protected).
- **Private dashboard**: view application funnel metrics, outcome tracking, and prioritization signals.
- **Portfolio Intelligence (Groq)**: generates insights from your tracked data (optional).
- **Fit Engine (Groq)**: store per-application context (industry + JD + resume), run a single Groq call to get:
  - `total_score` (0–100)
  - 5-category breakdown
  - dealbreaker gaps, missed opportunities
  - rewrite suggestions
  - recommendation (`apply_as_is` / `revise_first` / `significant_mismatch`)

## Tech Stack

- **Backend**: Python, FastAPI
- **Templates**: Jinja2 (server-rendered)
- **Database**: PostgreSQL (dev), Neon Postgres (prod via `DATABASE_URL`)
- **DB Driver**: psycopg3 (raw SQL, no ORM)
- **Charts**: Chart.js
- **AI**: Groq (llama-3.3-70b-versatile)

## Project Structure

```
ai-portfolio/
├── main.py
├── apply_schema.py
├── database/
│   └── __init__.py
├── routers/
│   ├── tracking.py
│   └── intelligence.py
├── services/
│   └── fit/
│       ├── evaluator.py
│       └── repository.py
├── templates/
│   ├── home.html
│   ├── projects_final.html
│   ├── contact.html
│   ├── admin.html
│   ├── dashboard.html
│   ├── context.html
│   └── insights.html
└── static/
    └── css/
```

## Local Setup

### 1) Create and activate a virtual environment

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Create a `.env` file (never commit this)

Create `ai-portfolio/.env` and set at least:

```bash
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME
DASHBOARD_PASSWORD=your_password_here
SESSION_SECRET_KEY=your_random_hex_string
GROQ_API_KEY=your_groq_key_here
```

Optional (enables additional features):

```bash
GA4_MEASUREMENT_ID=G-XXXXXXXXXX
GA4_API_SECRET=your_ga4_api_secret
EXCLUDED_IPS=1.2.3.4,5.6.7.8
CALENDLY_LINK=https://calendly.com/your-link
BASE_URL=http://127.0.0.1:8000
```

### 4) Apply the database schema

```bash
python apply_schema.py
```

### 5) Run the server

```bash
uvicorn main:app --reload
```

Open:

- Public site: `http://127.0.0.1:8000/`
- Admin login: `http://127.0.0.1:8000/admin`
- Dashboard: `http://127.0.0.1:8000/dashboard`

## How To Use

### Create an application + ref link

1. Go to `/admin` and log in with `DASHBOARD_PASSWORD`.
2. Create an application.
3. Copy the generated portfolio link containing `?ref=...` and use it in your outreach.

### View analytics

Open `/dashboard` to see application status, visits, follow-ups, and fit signals.

### Run a fit assessment (private)

1. Open `/admin/context/{application_id}`.
2. Fill **Industry / Domain**, **JD text**, **Resume text** and save.
3. Click **Assess Fit**.
4. The page shows the full breakdown and keeps all historical attempts visible.

## Environment & Security Notes

- Never commit `.env` to GitHub.
- Admin routes are protected using an HMAC-signed session token derived from:
  - `DASHBOARD_PASSWORD`
  - `SESSION_SECRET_KEY`
- If Groq returns token-limit errors, reduce JD/resume size.

## Deployment (Vercel)

- Set environment variables in Vercel (do not upload `.env`).
- Set `DATABASE_URL` to your Neon Postgres connection string.
- Prefer `sslmode=require` unless you manage CA files.