"""
Tracking Router — Phase 2 + Security (Phase 5)
Handles ref code generation, visit logging, admin panel, and dashboard.
Includes rate limiting and input validation.
"""

import os
import re
import html
import secrets
import string
import smtplib
from collections import defaultdict
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from database import get_cursor


# ─── Rate Limiter (in-memory) ───
# Key: (client_ip, ref_code) → last_logged_time
# Max 1 visit log per IP per ref code per hour
_rate_limit_store: dict[tuple, datetime] = {}
RATE_LIMIT_WINDOW = timedelta(hours=1)

def _is_rate_limited(ip: str, ref_code: str) -> bool:
    """Check if this IP+ref_code combo was logged within the last hour."""
    key = (ip, ref_code)
    now = datetime.now()
    
    # Cleanup old entries (prevent memory leak)
    expired = [k for k, v in _rate_limit_store.items() if now - v > RATE_LIMIT_WINDOW]
    for k in expired:
        del _rate_limit_store[k]
    
    if key in _rate_limit_store:
        if now - _rate_limit_store[key] < RATE_LIMIT_WINDOW:
            return True  # Rate limited
    
    _rate_limit_store[key] = now
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

router = APIRouter()
templates = Jinja2Templates(directory="templates")

DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "changeme")
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL", "")
NOTIFICATION_EMAIL_PASSWORD = os.getenv("NOTIFICATION_EMAIL_PASSWORD", "")


# ─── Auth Middleware ───

def verify_password(password: str):
    """Simple password check for admin/dashboard routes."""
    if password != DASHBOARD_PASSWORD:
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
                     notes: str = None, date_applied: str = None) -> dict:
    """
    Save a new job application and generate its ref code.
    Inserts into both applications and ref_codes tables in sequence.
    Returns dict with application details and generated ref link.
    """
    ref_code = generate_ref_code()
    applied_date = date_applied or datetime.now().strftime('%Y-%m-%d')
    
    with get_cursor() as cur:
        # Insert application
        cur.execute(
            """INSERT INTO applications (company_name, person_name, position, date_applied, ref_code, notes)
               VALUES (%s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (company_name, person_name or None, position, applied_date, ref_code, notes or None)
        )
        app_id = cur.fetchone()["id"]
        
        # Insert ref code mapping
        cur.execute(
            """INSERT INTO ref_codes (ref_code, application_id, is_active)
               VALUES (%s, %s, TRUE)""",
            (ref_code, app_id)
        )
    
    ref_link = f"{BASE_URL}/?ref={ref_code}"
    return {
        "id": app_id,
        "company_name": company_name,
        "position": position,
        "ref_code": ref_code,
        "ref_link": ref_link
    }


def log_visit(ref_code: str, request: Request = None) -> bool:
    """
    Log a portfolio visit for a given ref code.
    Silently ignores invalid/non-existent ref codes — no errors, no fake rows.
    Returns True if visit was logged, False if ref code was invalid.
    """
    # First verify the ref code exists and is active
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, is_active FROM ref_codes WHERE ref_code = %s",
            (ref_code,)
        )
        ref_record = cur.fetchone()
        
        if ref_record is None or not ref_record["is_active"]:
            # Silently ignore — no 500 error, no fake visit row
            return False
        
        # Rate limit check: 1 log per IP per ref code per hour
        client_ip = "unknown"
        if request:
            client_ip = request.client.host if request.client else "unknown"
        
        if _is_rate_limited(client_ip, ref_code):
            return False  # Silently skip — already logged recently
        
        # Count existing visits for this ref code
        cur.execute(
            "SELECT COUNT(*) as cnt FROM visits WHERE ref_code = %s",
            (ref_code,)
        )
        visit_count = cur.fetchone()["cnt"] + 1
        
        # Get country from request if available (basic)
        country = None
        
        # Insert visit
        cur.execute(
            """INSERT INTO visits (ref_code, visit_count, country)
               VALUES (%s, %s, %s)""",
            (ref_code, visit_count, country)
        )
        
        # Send email notification on FIRST visit only
        if visit_count == 1:
            _send_first_visit_notification(ref_code)
    
    return True


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
    return templates.TemplateResponse("admin.html", {"request": request})


@router.post("/admin/login")
async def admin_login(request: Request, password: str = Form(...)):
    """Verify admin password and redirect to admin panel."""
    if password != DASHBOARD_PASSWORD:
        return templates.TemplateResponse("admin_login.html", {
            "request": request,
            "error": "Incorrect password"
        })
    response = RedirectResponse(url="/admin/panel", status_code=303)
    response.set_cookie("auth", DASHBOARD_PASSWORD, httponly=True, samesite="strict")
    return response


@router.get("/admin/panel", response_class=HTMLResponse)
async def admin_panel(request: Request):
    """Admin panel with application form — requires auth cookie."""
    auth = request.cookies.get("auth")
    if auth != DASHBOARD_PASSWORD:
        return templates.TemplateResponse("admin_login.html", {"request": request})
    return templates.TemplateResponse("admin.html", {"request": request, "authenticated": True})


@router.post("/admin/application")
async def submit_application(
    request: Request,
    company_name: str = Form(...),
    position: str = Form(...),
    person_name: str = Form(""),
    notes: str = Form(""),
    date_applied: str = Form("")
):
    """Save a new application and return the generated ref link."""
    auth = request.cookies.get("auth")
    if auth != DASHBOARD_PASSWORD:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Input validation
    _validate_application_input(company_name, position)
    
    result = save_application(
        _sanitize(company_name), 
        _sanitize(position), 
        _sanitize(person_name) if person_name else None, 
        _sanitize(notes, 500) if notes else None, 
        date_applied or None
    )
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "authenticated": True,
        "success": True,
        "result": result
    })


# ─── Dashboard Routes ───

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Private dashboard — shows all applications with visit data and analytics."""
    auth = request.cookies.get("auth")
    if auth != DASHBOARD_PASSWORD:
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
                a.notes,
                COUNT(v.id) AS visit_count,
                MIN(v.timestamp) AS first_visit,
                MAX(v.timestamp) AS last_visit
            FROM applications a
            LEFT JOIN visits v ON a.ref_code = v.ref_code
            GROUP BY a.id
            ORDER BY a.date_applied DESC
        """)
        applications = cur.fetchall()
        
        # ── Stat Cards ──
        cur.execute("SELECT COUNT(*) AS cnt FROM applications")
        total_apps = cur.fetchone()["cnt"]
        
        cur.execute("""
            SELECT COUNT(DISTINCT a.id) AS cnt 
            FROM applications a 
            INNER JOIN visits v ON a.ref_code = v.ref_code
        """)
        viewed_count = cur.fetchone()["cnt"]
        
        cur.execute("SELECT COUNT(*) AS cnt FROM applications WHERE outcome = 'got_call'")
        calls_count = cur.fetchone()["cnt"]
        
        conversion_rate = round(calls_count / total_apps * 100, 1) if total_apps > 0 else 0
        view_rate = round(viewed_count / total_apps * 100, 1) if total_apps > 0 else 0
        
        # ── Weekly Trend (for chart) ──
        cur.execute("""
            SELECT 
                DATE_TRUNC('week', v.timestamp)::date AS week_start,
                COUNT(*) AS total_views,
                COUNT(DISTINCT v.ref_code) AS unique_refs
            FROM visits v
            GROUP BY DATE_TRUNC('week', v.timestamp)
            ORDER BY week_start ASC
        """)
        weekly_data = cur.fetchall()
        
        # ── Conversion by Position (for chart) ──
        cur.execute("""
            SELECT 
                a.position,
                COUNT(*) AS total,
                COUNT(CASE WHEN v.ref_code IS NOT NULL THEN 1 END) AS viewed,
                COUNT(CASE WHEN a.outcome = 'got_call' THEN 1 END) AS got_call
            FROM applications a
            LEFT JOIN (SELECT DISTINCT ref_code FROM visits) v ON a.ref_code = v.ref_code
            GROUP BY a.position
            ORDER BY total DESC
            LIMIT 8
        """)
        position_data = cur.fetchall()
        
        # ── Avg Time to View ──
        cur.execute("""
            SELECT ROUND(AVG(sub.days_to_view), 1) AS avg_days
            FROM (
                SELECT 
                    EXTRACT(DAY FROM MIN(v.timestamp) - a.date_applied::timestamp) AS days_to_view
                FROM applications a
                INNER JOIN visits v ON a.ref_code = v.ref_code
                GROUP BY a.id
            ) sub
        """)
        avg_days_row = cur.fetchone()
        avg_days_to_view = float(avg_days_row["avg_days"]) if avg_days_row and avg_days_row["avg_days"] else 0
        
        # ── High Intent (viewed > 1 time) ──
        cur.execute("""
            SELECT COUNT(*) AS cnt
            FROM (
                SELECT a.id
                FROM applications a
                INNER JOIN visits v ON a.ref_code = v.ref_code
                GROUP BY a.id
                HAVING COUNT(v.id) > 1
            ) sub
        """)
        high_intent_count = cur.fetchone()["cnt"]
    
    # Prepare chart data as JSON-safe
    import json
    weekly_labels = [str(row["week_start"]) for row in weekly_data]
    weekly_views = [row["total_views"] for row in weekly_data]
    weekly_unique = [row["unique_refs"] for row in weekly_data]
    
    position_labels = [row["position"] for row in position_data]
    position_applied = [row["total"] for row in position_data]
    position_viewed = [row["viewed"] for row in position_data]
    position_calls = [row["got_call"] for row in position_data]
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "applications": applications,
        # Stat cards
        "total_apps": total_apps,
        "viewed_count": viewed_count,
        "calls_count": calls_count,
        "conversion_rate": conversion_rate,
        "view_rate": view_rate,
        "avg_days_to_view": avg_days_to_view,
        "high_intent_count": high_intent_count,
        # Chart data (JSON strings)
        "weekly_labels": json.dumps(weekly_labels),
        "weekly_views": json.dumps(weekly_views),
        "weekly_unique": json.dumps(weekly_unique),
        "position_labels": json.dumps(position_labels),
        "position_applied": json.dumps(position_applied),
        "position_viewed": json.dumps(position_viewed),
        "position_calls": json.dumps(position_calls),
    })


@router.post("/dashboard/update-outcome")
async def update_outcome(
    request: Request,
    application_id: int = Form(...),
    outcome: str = Form(...)
):
    """Update application outcome from the dashboard."""
    auth = request.cookies.get("auth")
    if auth != DASHBOARD_PASSWORD:
        raise HTTPException(status_code=403, detail="Access denied")
    
    valid_outcomes = ['pending', 'got_call', 'rejected', 'no_response']
    if outcome not in valid_outcomes:
        raise HTTPException(status_code=400, detail=f"Invalid outcome. Must be one of: {valid_outcomes}")
    
    with get_cursor() as cur:
        cur.execute(
            "UPDATE applications SET outcome = %s WHERE id = %s",
            (outcome, application_id)
        )
    
    return RedirectResponse(url="/dashboard", status_code=303)

