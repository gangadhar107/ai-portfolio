"""
Tracking Router — Phase 2 + Security (Phase 5)
Handles ref code generation, visit logging, admin panel, and dashboard.
Includes rate limiting and input validation.
"""

import os
import re
import json
import html
import hmac
import hashlib
import secrets
import string
import smtplib
import urllib.request as urlrequest
import urllib.parse as urlparse
from collections import defaultdict
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from database import get_cursor


# ─── Rate Limiter (in-memory) ───
# Key: (client_ip, ref_code) → last_logged_time
# Deduplicate rapid reloads per IP per ref code
_rate_limit_store: dict[tuple, list[datetime]] = {}
RATE_LIMIT_WINDOW = timedelta(seconds=60)
MAX_VISITS_PER_WINDOW = 5

def _is_rate_limited(ip: str, ref_code: str) -> bool:
    """Check if this IP+ref_code combo was logged very recently."""
    key = (ip, ref_code)
    now = datetime.now()

    window_start = now - RATE_LIMIT_WINDOW
    times = _rate_limit_store.get(key, [])
    times = [t for t in times if t >= window_start]
    if len(times) >= MAX_VISITS_PER_WINDOW:
        _rate_limit_store[key] = times
        return True
    times.append(now)
    _rate_limit_store[key] = times
    return False


# ─── Input Validation ───

def _sanitize(text: str, max_length: int = 200) -> str:
    """Sanitize and truncate user input."""
    if not text:
        return text
    text = text.strip()[:max_length]
    text = html.escape(text)
    return text

def _validate_application_input(company: str, position: str):
    """Validate required fields for application submission."""
    if not company or len(company.strip()) < 2:
        raise HTTPException(status_code=400, detail="Company name must be at least 2 characters")
    if not position or len(position.strip()) < 2:
        raise HTTPException(status_code=400, detail="Position must be at least 2 characters")
    if len(company) > 200:
        raise HTTPException(status_code=400, detail="Company name too long (max 200 chars)")
    if len(position) > 200:
        raise HTTPException(status_code=400, detail="Position too long (max 200 chars)")

V12_OUTREACH_CHANNELS = {"cold_founder_email", "hr_email", "linkedin_dm", "portal_apply", "referral"}
V12_CONTACT_PERSONS = {"founder", "hr", "hiring_manager", "unknown"}
V12_ROLE_CATEGORIES = {"data_analyst", "apm", "founders_office", "ai_engineer", "business_analyst", "other"}
V12_FOLLOW_UP_RESPONSES = {"no_response", "positive", "negative", "interview_scheduled"}
VISIT_SOURCES = {"email_click", "direct", "linkedin", "unknown"}

router = APIRouter()
templates = Jinja2Templates(directory="templates")

DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "changeme")

# ─── Session Token (replaces storing plaintext password in cookie) ───
# HMAC-sign the password so the cookie never contains the actual password.
# Same password always produces the same token, so sessions survive restarts.
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "")
if not SESSION_SECRET_KEY:
    raise RuntimeError(
        "SESSION_SECRET_KEY is not set. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\" "
        "and add it to your .env file."
    )
SESSION_TOKEN = hmac.new(
    key=SESSION_SECRET_KEY.encode(),
    msg=DASHBOARD_PASSWORD.encode(),
    digestmod=hashlib.sha256
).hexdigest()

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL", "")
NOTIFICATION_EMAIL_PASSWORD = os.getenv("NOTIFICATION_EMAIL_PASSWORD", "")

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def _is_internal_visit(request: Request) -> bool:
    excluded = [ip.strip() for ip in os.getenv("EXCLUDED_IPS", "").split(",") if ip.strip()]
    if request.cookies.get("portfolio_owner") == "true":
        return True
    ip = get_client_ip(request)
    return ip in excluded

def _parse_ga_client_id(request: Request) -> str | None:
    ga_cookie = request.cookies.get("_ga")
    if not ga_cookie:
        return None
    parts = [p for p in ga_cookie.split(".") if p]
    if len(parts) < 4:
        return None
    return f"{parts[-2]}.{parts[-1]}"

def _fire_ga4_recruiter_visit_event(
    *,
    request: Request,
    ref_code: str,
    company_name: str,
    position: str,
    is_return_visit: bool,
    visit_source: str,
    utm_source: str | None,
    utm_medium: str | None,
):
    measurement_id = os.getenv("GA4_MEASUREMENT_ID", "").strip()
    api_secret = os.getenv("GA4_API_SECRET", "").strip()
    if not measurement_id or not api_secret:
        print("[GA4] GA4_MEASUREMENT_ID/GA4_API_SECRET not set — skipping server event")
        return

    client_id = _parse_ga_client_id(request)
    if not client_id:
        print("[GA4] _ga cookie missing/unparseable — skipping server event")
        return

    endpoint = f"https://www.google-analytics.com/mp/collect?{urlparse.urlencode({'measurement_id': measurement_id, 'api_secret': api_secret})}"
    payload = {
        "client_id": client_id,
        "events": [{
            "name": "recruiter_visit",
            "params": {
                "ref_code": ref_code,
                "company": company_name,
                "position": position,
                "is_return_visit": is_return_visit,
                "visit_source": visit_source,
                "utm_source": utm_source or "",
                "utm_medium": utm_medium or "",
            }
        }]
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urlrequest.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlrequest.urlopen(req, timeout=2) as resp:
            if resp.status >= 400:
                print(f"[GA4] Event failed: HTTP {resp.status}")
    except Exception as e:
        print(f"[GA4] Event error: {e}")


# ─── Auth Middleware ───

def verify_password(password: str):
    """Timing-safe password check for admin/dashboard routes."""
    if not hmac.compare_digest(password, DASHBOARD_PASSWORD):
        raise HTTPException(status_code=403, detail="Access denied")
    return True


# ─── Core Functions ───

def generate_ref_code() -> str:
    """
    Generate a unique 8-character alphanumeric ref code.
    Uses Python secrets module for cryptographic randomness.
    Checks database to guarantee uniqueness.
    """
    alphabet = string.ascii_lowercase + string.digits
    while True:
        code = ''.join(secrets.choice(alphabet) for _ in range(8))
        # Check uniqueness
        with get_cursor() as cur:
            cur.execute("SELECT id FROM ref_codes WHERE ref_code = %s", (code,))
            if cur.fetchone() is None:
                return code


def save_application(company_name: str, position: str, person_name: str = None, 
                     notes: str = None, date_applied: str = None,
                     outreach_channel: str | None = None,
                     contact_person: str | None = None,
                     role_category: str | None = None,
                     followed_up: bool = False,
                     follow_up_date: str | None = None,
                     follow_up_response: str | None = None,
                     rejection_reason: str | None = None) -> dict:
    """
    Save a new job application and generate its ref code.
    Inserts into both applications and ref_codes tables in sequence.
    Returns dict with application details and generated ref link.
    """
    ref_code = generate_ref_code()
    applied_date = date_applied or datetime.now().strftime('%Y-%m-%d')

    if outreach_channel and outreach_channel not in V12_OUTREACH_CHANNELS:
        raise HTTPException(status_code=400, detail="Invalid outreach_channel value")
    if contact_person and contact_person not in V12_CONTACT_PERSONS:
        raise HTTPException(status_code=400, detail="Invalid contact_person value")
    if role_category and role_category not in V12_ROLE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid role_category value")
    if follow_up_response and follow_up_response not in V12_FOLLOW_UP_RESPONSES:
        raise HTTPException(status_code=400, detail="Invalid follow_up_response value")
    if follow_up_date and not re.match(r"^\d{4}-\d{2}-\d{2}$", follow_up_date):
        raise HTTPException(status_code=400, detail="Invalid follow_up_date format (YYYY-MM-DD)")
    
    with get_cursor() as cur:
        # Insert application
        cur.execute(
            """INSERT INTO applications (
                    company_name, person_name, position, date_applied, ref_code, notes,
                    outreach_channel, contact_person, role_category,
                    followed_up, follow_up_date, follow_up_response, rejection_reason
               )
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (
                company_name, person_name or None, position, applied_date, ref_code, notes or None,
                outreach_channel or None, contact_person or None, role_category or None,
                bool(followed_up), follow_up_date or None, follow_up_response or None,
                rejection_reason or None
            )
        )
        app_id = cur.fetchone()["id"]
        
        # Insert ref code mapping
        cur.execute(
            """INSERT INTO ref_codes (ref_code, application_id, is_active)
               VALUES (%s, %s, TRUE)""",
            (ref_code, app_id)
        )

    try:
        from routers.intelligence import clear_insights_cache
        clear_insights_cache()
    except Exception:
        pass
    
    ref_link = f"{BASE_URL}/?ref={ref_code}"
    return {
        "id": app_id,
        "company_name": company_name,
        "position": position,
        "ref_code": ref_code,
        "ref_link": ref_link
    }


def _derive_visit_source(request: Request, utm_source: str | None, utm_medium: str | None) -> str:
    if utm_medium:
        m = utm_medium.strip().lower()
        if "email" in m:
            return "email_click"
    if utm_source:
        s = utm_source.strip().lower()
        if s == "linkedin":
            return "linkedin"

    referer = request.headers.get("referer") if request else None
    if referer and "linkedin.com" in referer.lower():
        return "linkedin"
    if not referer:
        return "direct"
    return "unknown"


def log_visit(ref_code: str, request: Request = None) -> str | None:
    """
    Log a portfolio visit for a given ref code.
    Silently ignores invalid/non-existent ref codes — no errors, no fake rows.
    Returns a per-visit token if a row was inserted, else None.
    """
    if not request:
        return None
    if _is_internal_visit(request):
        return None

    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT id, is_active FROM ref_codes WHERE ref_code = %s",
                (ref_code,)
            )
            ref_record = cur.fetchone()

            if ref_record is None or not ref_record["is_active"]:
                return None

            client_ip = get_client_ip(request)
            if _is_rate_limited(client_ip, ref_code):
                return None

            utm_source = request.query_params.get("utm_source")
            utm_medium = request.query_params.get("utm_medium")
            if utm_source:
                utm_source = _sanitize(utm_source, 100)
            if utm_medium:
                utm_medium = _sanitize(utm_medium, 100)

            visit_source = _derive_visit_source(request, utm_source, utm_medium)
            if visit_source not in VISIT_SOURCES:
                visit_source = "unknown"

            cur.execute(
                "SELECT COUNT(*) as cnt FROM visits WHERE ref_code = %s",
                (ref_code,)
            )
            cnt = cur.fetchone()["cnt"]
            visit_count = cnt + 1
            is_return_visit = cnt > 0

            country = None
            visit_token = secrets.token_urlsafe(16)

            cur.execute(
                """INSERT INTO visits (
                        ref_code, visit_count, country,
                        visit_token, is_return_visit, visit_source,
                        utm_source, utm_medium
                   )
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    ref_code, visit_count, country,
                    visit_token, is_return_visit, visit_source,
                    utm_source or None, utm_medium or None
                )
            )

            if visit_count == 1:
                _send_first_visit_notification(ref_code)

            try:
                from routers.intelligence import clear_insights_cache
                clear_insights_cache()
            except Exception:
                pass

            cur.execute("""
                SELECT a.company_name, a.position
                FROM applications a
                JOIN ref_codes rc ON rc.application_id = a.id
                WHERE rc.ref_code = %s
            """, (ref_code,))
            app = cur.fetchone()

        if app:
            _fire_ga4_recruiter_visit_event(
                request=request,
                ref_code=ref_code,
                company_name=app["company_name"],
                position=app["position"],
                is_return_visit=is_return_visit,
                visit_source=visit_source,
                utm_source=utm_source,
                utm_medium=utm_medium,
            )

        return visit_token
    except Exception as e:
        print(f"[Tracking] log_visit error: {e}")
        return None


class TrackTimePayload(BaseModel):
    visit_token: str
    elapsed_seconds: int


@router.post("/track-time")
async def track_time(request: Request, payload: TrackTimePayload):
    if _is_internal_visit(request):
        return {"ok": True}

    token = (payload.visit_token or "").strip()
    if not token or len(token) > 200:
        raise HTTPException(status_code=400, detail="Invalid visit_token")

    seconds = int(payload.elapsed_seconds)
    if seconds < 0 or seconds > 6 * 60 * 60:
        raise HTTPException(status_code=400, detail="Invalid elapsed_seconds")

    try:
        with get_cursor() as cur:
            cur.execute(
                """
                UPDATE visits
                SET time_on_site = CASE
                    WHEN time_on_site IS NULL THEN %s
                    ELSE GREATEST(time_on_site, %s)
                END
                WHERE visit_token = %s
                """,
                (seconds, seconds, token)
            )
        return {"ok": True}
    except Exception as e:
        print(f"[Tracking] track_time error: {e}")
        return {"ok": True}


def _send_first_visit_notification(ref_code: str):
    """
    Send email notification when a ref link is opened for the first time.
    Silently fails if email is not configured.
    """
    if not NOTIFICATION_EMAIL or not NOTIFICATION_EMAIL_PASSWORD:
        print(f"[Notification] First visit to ref:{ref_code} — email not configured, skipping")
        return
    
    # Get application details for the notification
    with get_cursor() as cur:
        cur.execute("""
            SELECT a.company_name, a.position 
            FROM applications a 
            JOIN ref_codes rc ON rc.application_id = a.id 
            WHERE rc.ref_code = %s
        """, (ref_code,))
        app = cur.fetchone()
    
    if not app:
        return
    
    subject = f"🔔 Portfolio Viewed: {app['company_name']} — {app['position']}"
    body = f"""
    Your portfolio has been viewed!
    
    Company: {app['company_name']}
    Position: {app['position']}
    Ref Code: {ref_code}
    Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    
    This is the first time someone from this application opened your portfolio link.
    """
    
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = NOTIFICATION_EMAIL
        msg['To'] = NOTIFICATION_EMAIL
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(NOTIFICATION_EMAIL, NOTIFICATION_EMAIL_PASSWORD)
            server.send_message(msg)
        
        print(f"[Notification] Email sent for ref:{ref_code} → {app['company_name']}")
    except Exception as e:
        print(f"[Notification] Failed to send email: {e}")


# ─── API Routes ───

@router.post("/generate-ref")
async def generate_ref_endpoint(
    company_name: str = Form(...),
    position: str = Form(...),
    person_name: str = Form(None),
    notes: str = Form(None),
    date_applied: str = Form(None)
):
    """Generate a ref code for a new application and return the full ref link."""
    result = save_application(company_name, position, person_name, notes, date_applied)
    return result


# ─── Admin Routes ───

@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Private admin page — application submission form."""
    auth = request.cookies.get("auth", "")
    if not hmac.compare_digest(auth, SESSION_TOKEN):
        return templates.TemplateResponse("admin_login.html", {
            "request": request,
            "redirect_to": "/admin"
        })
    return templates.TemplateResponse("admin.html", {"request": request, "authenticated": True})


@router.post("/admin/login")
async def admin_login(
    request: Request, 
    password: str = Form(...),
    redirect_to: str = Form("/admin")
):
    """Verify admin password and redirect to the requested page."""
    if not hmac.compare_digest(password, DASHBOARD_PASSWORD):
        return templates.TemplateResponse("admin_login.html", {
            "request": request,
            "error": "Incorrect password",
            "redirect_to": redirect_to
        })
    response = RedirectResponse(url=redirect_to, status_code=303)
    response.set_cookie("auth", SESSION_TOKEN, httponly=True, samesite="strict")
    response.set_cookie("portfolio_owner", "true", httponly=True, samesite="strict")
    return response


@router.get("/admin/panel", response_class=HTMLResponse)
async def admin_panel(request: Request):
    """Legacy admin panel route — redirects to /admin."""
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/admin/application")
async def submit_application(
    request: Request,
    company_name: str = Form(...),
    position: str = Form(...),
    person_name: str = Form(""),
    notes: str = Form(""),
    date_applied: str = Form(""),
    outreach_channel: str = Form(""),
    contact_person: str = Form(""),
    role_category: str = Form(""),
    followed_up: str = Form(""),
    follow_up_date: str = Form(""),
    follow_up_response: str = Form("")
):
    """Save a new application and return the generated ref link."""
    auth = request.cookies.get("auth", "")
    if not hmac.compare_digest(auth, SESSION_TOKEN):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Input validation
    _validate_application_input(company_name, position)

    followed_up_bool = str(followed_up).lower() in {"true", "on", "1", "yes"}
    if follow_up_date and not followed_up_bool:
        follow_up_date = ""
    if follow_up_response and not followed_up_bool:
        follow_up_response = ""

    try:
        result = save_application(
            _sanitize(company_name),
            _sanitize(position),
            _sanitize(person_name) if person_name else None,
            _sanitize(notes, 500) if notes else None,
            date_applied or None,
            outreach_channel=outreach_channel or None,
            contact_person=contact_person or None,
            role_category=role_category or None,
            followed_up=followed_up_bool,
            follow_up_date=follow_up_date or None,
            follow_up_response=follow_up_response or None,
        )
        return templates.TemplateResponse("admin.html", {
            "request": request,
            "authenticated": True,
            "success": True,
            "result": result
        })
    except HTTPException as e:
        return templates.TemplateResponse("admin.html", {
            "request": request,
            "authenticated": True,
            "success": False,
            "error": e.detail
        })
    except Exception as e:
        print(f"[Admin] Failed to save application: {type(e).__name__}: {e}")
        return templates.TemplateResponse("admin.html", {
            "request": request,
            "authenticated": True,
            "success": False,
            "error": f"{type(e).__name__}: {str(e)[:200]}"
        })


# ─── Dashboard Routes ───

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Private dashboard — shows all applications with visit data and analytics."""
    auth = request.cookies.get("auth", "")
    if not hmac.compare_digest(auth, SESSION_TOKEN):
        return templates.TemplateResponse("admin_login.html", {
            "request": request,
            "redirect_to": "/dashboard"
        })
    
    with get_cursor() as cur:
        # Get all applications with visit counts
        cur.execute("""
            SELECT 
                a.id,
                a.company_name,
                a.person_name,
                a.position,
                a.date_applied,
                a.outcome,
                a.ref_code,
                COUNT(v.id) AS visit_count,
                MIN(v.timestamp) AS first_visit
            FROM applications a
            LEFT JOIN visits v ON a.ref_code = v.ref_code
            GROUP BY a.id
            ORDER BY a.date_applied DESC
        """)
        applications = cur.fetchall()
    
    # Build the complete dataset as JSON for client-side filtering
    all_applications = []
    for app in applications:
        first_viewed = None
        if app["first_visit"]:
            first_viewed = app["first_visit"].strftime("%Y-%m-%d %H:%M")
        
        all_applications.append({
            "id": app["id"],
            "company_name": app["company_name"],
            "person_name": app["person_name"] or "",
            "position": app["position"],
            "date_applied": app["date_applied"].strftime("%Y-%m-%d") if app["date_applied"] else "",
            "outcome": app["outcome"],
            "ref_code": app["ref_code"] or "",
            "views": app["visit_count"],
            "first_viewed": first_viewed,
            "viewed": app["visit_count"] > 0,
        })
    
    # ── AI Insights ──
    from routers.intelligence import get_cached_insights, generate_insights, collect_portfolio_data
    insights = get_cached_insights()
    if insights is None:
        try:
            data = collect_portfolio_data()
            insights = generate_insights(data)
        except Exception:
            insights = []
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "json_data": json.dumps(all_applications),
        "insights_json": json.dumps(insights),
    })


@router.post("/dashboard/update-outcome")
async def update_outcome(
    request: Request,
    application_id: int = Form(...),
    outcome: str = Form(...)
):
    """Update application outcome from the dashboard."""
    auth = request.cookies.get("auth", "")
    if not hmac.compare_digest(auth, SESSION_TOKEN):
        raise HTTPException(status_code=403, detail="Access denied")
    
    valid_outcomes = ['pending', 'got_call', 'rejected', 'no_response']
    if outcome not in valid_outcomes:
        raise HTTPException(status_code=400, detail=f"Invalid outcome. Must be one of: {valid_outcomes}")
    
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE applications
            SET outcome = %s,
                outcome_date = CASE WHEN %s = 'pending' THEN NULL ELSE CURRENT_DATE END
            WHERE id = %s
            """,
            (outcome, outcome, application_id)
        )

    try:
        from routers.intelligence import clear_insights_cache
        clear_insights_cache()
    except Exception:
        pass
    
    return RedirectResponse(url="/dashboard", status_code=303)

