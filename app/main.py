"""
Main FastAPI Application
Zugo Attendance Management System

This is the entry point for the application. All routes are imported from 
modular route files organized by feature domain.
"""
import os
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from starlette.middleware.sessions import SessionMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

import config
from schema import initialize_database_schema
from bills_models import initialize_billing_schema
from services import mark_leaves_for_absent_employees, send_event_wishes
from app.routes import auth, attendance, employees, hr, offices, comments, billing, public

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===========================================================================
# Lifespan Context Manager - Startup & Shutdown
# ===========================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle app startup and shutdown events."""
    print("Application startup...")
    initialize_database_schema()
    initialize_billing_schema()
    
    # Initialize APScheduler for scheduled tasks
    scheduler = BackgroundScheduler()
    
    # Job 1: Check for employees who haven't clocked in for 3+ days (2:30 PM IST)
    scheduler.add_job(mark_leaves_for_absent_employees, 'cron', hour=14, minute=30, timezone='Asia/Kolkata')
    
    # Job 2: Send birthday and anniversary wishes (9:00 AM IST)
    scheduler.add_job(send_event_wishes, 'cron', hour=9, minute=0, timezone='Asia/Kolkata')
    
    try:
        scheduler.start()
        print("✓ Scheduler started")
        print("  • Absence marking: 2:30 PM IST daily")
        print("  • Birthday & Anniversary wishes: 9:00 AM IST daily")
    except Exception as e:
        print(f"⚠️ Scheduler initialization failed: {e}")
    
    yield
    
    print("Application shutdown...")
    if scheduler.running:
        scheduler.shutdown()

# ===========================================================================
# FastAPI Application Setup
# ===========================================================================

# Set absolute paths for Render compatibility
# Go up one level from app/main.py to get to project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Create FastAPI app with lifespan
app = FastAPI(
    title="Zugo Attendance Management System",
    description="Employee attendance tracking and management system",
    version="1.0.0",
    lifespan=lifespan
)

# ===========================================================================
# Middleware Setup
# ===========================================================================

# Add SessionMiddleware before mounting static files
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "change_me_in_production_use_strong_random_key")
)

# ===========================================================================
# Static Files & Templates
# ===========================================================================

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Jinja2 Templates setup
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# ===========================================================================
# Exception Handlers
# ===========================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors for debugging"""
    logging.error(f"Validation error on {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body}
    )

# ===========================================================================
# Route Routers - Import and include all route modules
# ===========================================================================

# Authentication routes (login, signup, logout)
app.include_router(auth.router)

# Attendance and reporting routes
app.include_router(attendance.router)

# Employee management routes
app.include_router(employees.router)

# HR management and manual attendance
app.include_router(hr.router)

# Office management routes
app.include_router(offices.router)

# Employee comments and messaging
app.include_router(comments.router)

# Billing, invoices, and GST bills
app.include_router(billing.router)

# Public pages (terms, privacy)
app.include_router(public.router)

# ===========================================================================
# Application Entry Point
# ===========================================================================

if __name__ == "__main__":
    # Detect environment (Render deployment vs local development)
    is_render = os.getenv("RENDER")
    
    if is_render:
        # Production on Render
        port = int(os.getenv("PORT", "8000"))
        uvicorn.run("app:app", host="0.0.0.0", port=port)
    else:
        # Local development
        if os.getenv("DEBUG", "False").lower() == "true":
            uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
        else:
            uvicorn.run("app:app", host="127.0.0.1", port=8000)
