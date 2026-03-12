"""
Portfolio Intelligence Router — v1.1
Generates AI-powered insights from application and visit data using Groq.

How it works:
1. collect_portfolio_data() pulls all data from the 3 tables
2. generate_insights(data) sends that data to Groq and gets back structured insights
3. Results are cached in memory for 1 hour to avoid repeated API calls
4. Cache is cleared whenever new data arrives (visit, application, outcome change)
"""

import os
import json
import hmac
import hashlib
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from database import get_cursor
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# ─── Auth (same pattern as tracking.py) ───

DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "changeme")
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "")
SESSION_TOKEN = hmac.new(
    key=SESSION_SECRET_KEY.encode(),
    msg=DASHBOARD_PASSWORD.encode(),
    digestmod=hashlib.sha256
).hexdigest()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")


# ─── In-Memory Cache ───
# Resets on server restart. This is acceptable for a single-server free-tier app.

insight_cache = {
    "insights": [],
    "generated_at": None,
}

CACHE_TTL = timedelta(hours=1)


def get_cached_insights():
    """
    Returns the cached insights list if the cache is less than 1 hour old.
    Returns None if the cache is empty or expired.
    """
    if insight_cache["generated_at"] is None:
        return None
    if datetime.now() - insight_cache["generated_at"] > CACHE_TTL:
        return None
    return insight_cache["insights"]


def set_cached_insights(insights: list):
    """
    Saves a list of insight dicts into the cache with the current timestamp.
    """
    insight_cache["insights"] = insights
    insight_cache["generated_at"] = datetime.now()


def clear_insights_cache():
    """
    Resets the cache to empty. Called from tracking.py whenever
    new data arrives (visit logged, application saved, outcome updated).
    """
    insight_cache["insights"] = []
    insight_cache["generated_at"] = None


# ─── Data Collection ───

def collect_portfolio_data() -> dict:
    """
    Queries all 3 tables and returns a structured dict.
    Each key contains a list of dicts (one per row).
    Returns empty lists if tables have no data — never errors.
    """
    data = {
        "applications": [],
        "visits": [],
        "ref_codes": [],
    }

    try:
        with get_cursor() as cur:
            # All applications
            cur.execute("""
                SELECT id, company_name, person_name, position,
                       date_applied, outcome, ref_code, notes, created_at
                FROM applications
                ORDER BY date_applied DESC
            """)
            rows = cur.fetchall()
            for row in rows:
                data["applications"].append({
                    "id": row["id"],
                    "company_name": row["company_name"],
                    "person_name": row["person_name"] or "",
                    "position": row["position"],
                    "date_applied": row["date_applied"].strftime("%Y-%m-%d") if row["date_applied"] else "",
                    "outcome": row["outcome"] or "pending",
                    "ref_code": row["ref_code"] or "",
                    "notes": row["notes"] or "",
                })

            # All visits
            cur.execute("""
                SELECT id, ref_code, timestamp, visit_count, country
                FROM visits
                ORDER BY timestamp DESC
            """)
            rows = cur.fetchall()
            for row in rows:
                data["visits"].append({
                    "id": row["id"],
                    "ref_code": row["ref_code"],
                    "timestamp": row["timestamp"].strftime("%Y-%m-%d %H:%M") if row["timestamp"] else "",
                    "visit_count": row["visit_count"],
                    "country": row["country"] or "",
                })

            # All ref codes
            cur.execute("""
                SELECT id, ref_code, application_id, created_date, is_active
                FROM ref_codes
                ORDER BY created_date DESC
            """)
            rows = cur.fetchall()
            for row in rows:
                data["ref_codes"].append({
                    "id": row["id"],
                    "ref_code": row["ref_code"],
                    "application_id": row["application_id"],
                    "is_active": row["is_active"],
                })

    except Exception as e:
        print(f"[Intelligence] Error collecting portfolio data: {e}")

    return data


# ─── Insight Generation ───

# Exactly the system prompt the user specified
GROQ_SYSTEM_PROMPT = (
    "Return your response STRICTLY as a JSON array. "
    "No preamble, no explanation, no markdown fences. "
    "Just the raw JSON array. "
    "Format: "
    '[{"type": "conversion|outreach|timing|pattern|warning", '
    '"headline": "", "explanation": "", "action": ""}]'
)

# Fallback when Groq fails or is unavailable
FALLBACK_INSIGHTS = [{
    "type": "warning",
    "headline": "AI analysis temporarily unavailable",
    "explanation": "Could not generate insights right now.",
    "action": "Click Refresh Insights to try again.",
}]

# Shown when there are fewer than 3 applications
NOT_ENOUGH_DATA_INSIGHTS = [{
    "type": "warning",
    "headline": "Not enough data yet",
    "explanation": "Add at least 3 applications to generate insights.",
    "action": "Go to Admin and log more applications.",
}]

# Valid insight types — used to validate Groq output
VALID_TYPES = {"conversion", "outreach", "timing", "pattern", "warning"}


def generate_insights(data: dict) -> list:
    """
    Sends portfolio data to Groq and returns a list of insight dicts.

    Rules:
    - Skips the API call if fewer than 3 applications exist
    - Uses a 5-second timeout to avoid hanging
    - Returns a fallback insight on ANY error (network, parse, timeout)
    - Validates each insight dict has the required keys and valid type
    """
    # Skip if not enough data
    if len(data.get("applications", [])) < 3:
        return NOT_ENOUGH_DATA_INSIGHTS

    # Skip if no API key configured
    if not GROQ_API_KEY:
        print("[Intelligence] GROQ_API_KEY not set — returning fallback")
        return FALLBACK_INSIGHTS

    try:
        from groq import Groq

        client = Groq(api_key=GROQ_API_KEY, timeout=5.0)

        # Build user prompt with the actual data
        user_prompt = (
            "Analyse this job search portfolio data and return actionable insights.\n\n"
            f"Applications ({len(data['applications'])} total):\n"
            f"{json.dumps(data['applications'], indent=2)}\n\n"
            f"Portfolio Visits ({len(data['visits'])} total):\n"
            f"{json.dumps(data['visits'], indent=2)}\n\n"
            "Focus on: conversion patterns, outreach effectiveness, "
            "timing patterns, and anything concerning. "
            "Return 3 to 6 insights."
        )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": GROQ_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
            max_tokens=2000,
        )

        raw = response.choices[0].message.content.strip()

        # Parse the JSON response
        parsed = json.loads(raw)

        # Handle both {"insights": [...]} wrapper and raw [...]
        if isinstance(parsed, dict):
            # Groq might wrap it in a key — extract the list
            for key in parsed:
                if isinstance(parsed[key], list):
                    parsed = parsed[key]
                    break
            else:
                print(f"[Intelligence] Unexpected dict structure: {list(parsed.keys())}")
                return FALLBACK_INSIGHTS

        if not isinstance(parsed, list):
            print(f"[Intelligence] Expected list, got {type(parsed).__name__}")
            return FALLBACK_INSIGHTS

        # Validate each insight has the required keys
        validated = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            # Ensure all 4 keys exist
            if not all(k in item for k in ("type", "headline", "explanation", "action")):
                continue
            # Clamp type to valid values
            if item["type"] not in VALID_TYPES:
                item["type"] = "pattern"
            validated.append({
                "type": item["type"],
                "headline": str(item["headline"]),
                "explanation": str(item["explanation"]),
                "action": str(item["action"]),
            })

        if not validated:
            print("[Intelligence] No valid insights after validation")
            return FALLBACK_INSIGHTS

        return validated

    except json.JSONDecodeError as e:
        print(f"[Intelligence] Failed to parse Groq response as JSON: {e}")
        return FALLBACK_INSIGHTS
    except Exception as e:
        print(f"[Intelligence] Groq API error: {e}")
        return FALLBACK_INSIGHTS


# ─── Routes ───

@router.get("/insights", response_class=HTMLResponse)
async def insights_page(request: Request):
    """
    Portfolio Intelligence page — password protected.
    Shows AI-generated insight cards with type badges.
    """
    auth = request.cookies.get("auth", "")
    if not hmac.compare_digest(auth, SESSION_TOKEN):
        return templates.TemplateResponse("admin_login.html", {
            "request": request,
            "redirect_to": "/insights"
        })

    # Try cache first
    insights = get_cached_insights()

    if insights is None:
        # Generate fresh insights
        data = collect_portfolio_data()
        insights = generate_insights(data)
        set_cached_insights(insights)

    return templates.TemplateResponse("insights.html", {
        "request": request,
        "insights": insights,
        "generated_at": insight_cache["generated_at"],
    })


@router.post("/insights/refresh")
async def refresh_insights(request: Request):
    """
    Clears the cache, regenerates insights, and returns the new insights
    as JSON.  Password protected.
    """
    auth = request.cookies.get("auth", "")
    if not hmac.compare_digest(auth, SESSION_TOKEN):
        raise HTTPException(status_code=403, detail="Access denied")

    clear_insights_cache()

    # Regenerate now so the caller gets fresh data
    data = collect_portfolio_data()
    insights = generate_insights(data)
    set_cached_insights(insights)

    return {"insights": insights}

