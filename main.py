"""
AI-Powered Portfolio — FastAPI Application
v1.0: Portfolio + Ref Code Tracking + SQL Analytics
"""

import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from routers.tracking import router as tracking_router, log_visit
from routers.intelligence import router as intelligence_router

load_dotenv()

app = FastAPI(
    title="AI Portfolio",
    description="AI-Powered Portfolio with ref code tracking",
    version="1.0.0"
)

# Include routers
app.include_router(tracking_router)
app.include_router(intelligence_router)

# Static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory="templates")
templates.env.globals["GA4_MEASUREMENT_ID"] = os.getenv("GA4_MEASUREMENT_ID", "").strip()

# Environment
CALENDLY_LINK = os.getenv("CALENDLY_LINK", "https://calendly.com")


# ─── Public Pages ───

@app.get("/")
async def home(request: Request, ref: str = None):
    """Home page — also handles ref code visit logging."""
    visit_token = None
    if ref:
        visit_token = log_visit(ref, request)
    return templates.TemplateResponse("home.html", {
        "request": request,
        "active_page": "home",
        "visit_token": visit_token
    })


@app.get("/about")
async def about(request: Request, ref: str = None):
    """About page."""
    visit_token = None
    if ref:
        visit_token = log_visit(ref, request)
    return templates.TemplateResponse("about.html", {
        "request": request,
        "active_page": "about",
        "visit_token": visit_token
    })


@app.get("/projects")
async def projects(request: Request, ref: str = None):
    """Projects page."""
    visit_token = None
    if ref:
        visit_token = log_visit(ref, request)
    return templates.TemplateResponse("projects_final.html", {
        "request": request,
        "active_page": "projects",
        "visit_token": visit_token
    })


@app.get("/blog")
async def blog(request: Request, ref: str = None):
    """Blog page — case studies and build logs."""
    visit_token = None
    if ref:
        visit_token = log_visit(ref, request)
    return templates.TemplateResponse("blog.html", {
        "request": request,
        "active_page": "blog",
        "visit_token": visit_token
    })


@app.get("/contact")
async def contact(request: Request, ref: str = None):
    """Contact page with Calendly link."""
    visit_token = None
    if ref:
        visit_token = log_visit(ref, request)
    return templates.TemplateResponse("contact.html", {
        "request": request,
        "active_page": "contact",
        "calendly_link": CALENDLY_LINK,
        "visit_token": visit_token
    })


@app.get("/health")
async def health_check():
    """Health check endpoint for deployment verification."""
    return {"status": "healthy", "version": "1.0.0"}
