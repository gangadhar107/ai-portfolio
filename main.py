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

load_dotenv()

app = FastAPI(
    title="AI Portfolio",
    description="AI-Powered Portfolio with ref code tracking",
    version="1.0.0"
)

# Include routers
app.include_router(tracking_router)

# Static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Environment
CALENDLY_LINK = os.getenv("CALENDLY_LINK", "https://calendly.com")


# ─── Public Pages ───

@app.get("/")
async def home(request: Request, ref: str = None):
    """Home page — also handles ref code visit logging."""
    if ref:
        log_visit(ref, request)
    return templates.TemplateResponse("home.html", {
        "request": request,
        "active_page": "home"
    })


@app.get("/about")
async def about(request: Request, ref: str = None):
    """About page."""
    if ref:
        log_visit(ref, request)
    return templates.TemplateResponse("about.html", {
        "request": request,
        "active_page": "about"
    })


@app.get("/projects")
async def projects(request: Request, ref: str = None):
    """Projects page."""
    if ref:
        log_visit(ref, request)
    return templates.TemplateResponse("projects.html", {
        "request": request,
        "active_page": "projects"
    })


@app.get("/blog")
async def blog(request: Request, ref: str = None):
    """Blog page."""
    if ref:
        log_visit(ref, request)
    return templates.TemplateResponse("blog.html", {
        "request": request,
        "active_page": "blog"
    })


@app.get("/contact")
async def contact(request: Request, ref: str = None):
    """Contact page with Calendly link."""
    if ref:
        log_visit(ref, request)
    return templates.TemplateResponse("contact.html", {
        "request": request,
        "active_page": "contact",
        "calendly_link": CALENDLY_LINK
    })


@app.get("/health")
async def health_check():
    """Health check endpoint for deployment verification."""
    return {"status": "healthy", "version": "1.0.0"}
