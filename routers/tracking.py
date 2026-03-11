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
    date_applied: str = Form("")
):
    """Save a new application and return the generated ref link."""
    auth = request.cookies.get("auth", "")
    if not hmac.compare_digest(auth, SESSION_TOKEN):
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
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "json_data": json.dumps(all_applications),
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
            "UPDATE applications SET outcome = %s WHERE id = %s",
            (outcome, application_id)
        )
    
    return RedirectResponse(url="/dashboard", status_code=303)

