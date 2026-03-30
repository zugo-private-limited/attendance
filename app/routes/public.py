"""Public routes: terms, privacy, etc."""
import os
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

import config

router = APIRouter()

def _get_templates():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
    return Jinja2Templates(directory=TEMPLATES_DIR)

@router.get("/terms", response_class=HTMLResponse, name="terms")
async def terms(request: Request):
    """Terms and Conditions page."""
    templates = _get_templates()
    user_email = request.session.get("user_email")
    if not user_email:
        return RedirectResponse(url="/")
    is_hr = user_email == config.HR_EMAIL
    
    return templates.TemplateResponse("terms.html", {
        "request": request,
        "is_hr": is_hr
    })

@router.get("/privacy", response_class=HTMLResponse, name="privacy")
async def privacy(request: Request):
    """Privacy Policy page."""
    templates = _get_templates()
    user_email = request.session.get("user_email")
    if not user_email:
        return RedirectResponse(url="/")
    is_hr = user_email == config.HR_EMAIL
    
    return templates.TemplateResponse("privacy.html", {
        "request": request,
        "is_hr": is_hr
    })
