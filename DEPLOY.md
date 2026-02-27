# AI Portfolio — Deployment Guide

## Overview
This guide covers deploying your AI-powered portfolio to **Vercel** (app) + **Neon** (PostgreSQL).

---

## Step 1: Set Up Neon Database

1. Go to [neon.tech](https://neon.tech) and create a free account
2. Create a new project called `portfolio-db`
3. Copy the **connection string** — it looks like:
   ```
   postgresql://portfolio_user:PASSWORD@ep-xxx.us-east-2.aws.neon.tech/portfolio_db?sslmode=require
   ```
4. Open the **SQL Editor** in Neon and run the contents of `database/schema.sql`
5. Verify tables were created by running:
   ```sql
   SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
   ```
   You should see: `applications`, `visits`, `ref_codes`

---

## Step 2: Deploy to Vercel

### Option A: Via GitHub (Recommended)

1. Push your code to GitHub:
   ```bash
   git init
   git add .
   git commit -m "AI Portfolio v1.0 — ready for deployment"
   git remote add origin https://github.com/gangadhar107/ai-portfolio.git
   git push -u origin main
   ```

2. Go to [vercel.com](https://vercel.com) and sign in with GitHub
3. Click **"Add New Project"** → Import your `ai-portfolio` repository
4. In **Settings → Environment Variables**, add:

   | Variable | Value |
   |----------|-------|
   | `DATABASE_URL` | Your Neon connection string |
   | `DASHBOARD_PASSWORD` | A strong password for admin access |
   | `NOTIFICATION_EMAIL` | `gangadhar.allam2810@gmail.com` |
   | `NOTIFICATION_EMAIL_PASSWORD` | Gmail App Password (see below) |
   | `BASE_URL` | `https://your-project.vercel.app` |
   | `CALENDLY_LINK` | Your Calendly link (if you have one) |

5. Click **Deploy**

### Option B: Via Vercel CLI

```bash
npm i -g vercel
cd ai-portfolio
vercel --prod
```

---

## Step 3: Gmail App Password (for email notifications)

1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** if not already enabled
3. Go to **App Passwords** → Generate one for "Mail"
4. Use this 16-character password as `NOTIFICATION_EMAIL_PASSWORD`

---

## Step 4: Verify Deployment

After deployment, test these URLs:

| URL | Expected |
|-----|----------|
| `https://your-site.vercel.app/` | Home page with dark theme |
| `https://your-site.vercel.app/health` | `{"status": "ok"}` |
| `https://your-site.vercel.app/admin` | Login page |
| `https://your-site.vercel.app/dashboard` | Login page |
| `https://your-site.vercel.app/?ref=testcode` | Home page (visit NOT logged — invalid code) |

### Generate Your First Real Ref Code

1. Log into `/admin` with your dashboard password
2. Fill in a real job application (company, position)
3. Copy the generated ref link
4. Send this link in your job application
5. When the recruiter clicks it → visit is logged + you get an email

---

## Step 5: Custom Domain (Optional)

1. In Vercel → Project Settings → Domains
2. Add your custom domain
3. Update DNS records as shown by Vercel
4. Update `BASE_URL` env var to your custom domain

---

## File Structure for Deployment

```
ai-portfolio/
├── main.py              ← FastAPI entry point (Vercel uses this)
├── vercel.json          ← Vercel routing config
├── requirements.txt     ← Python dependencies
├── database/
│   ├── __init__.py      ← DB connection layer
│   └── schema.sql       ← Run this in Neon SQL editor
├── routers/
│   └── tracking.py      ← All API routes
├── templates/           ← Jinja2 HTML templates
├── static/              ← CSS, JS, images
└── .env                 ← Local only (NOT deployed)
```

> **Important:** `.env` is in `.gitignore` and will NOT be pushed to GitHub.
> All secrets go into Vercel's Environment Variables dashboard.
