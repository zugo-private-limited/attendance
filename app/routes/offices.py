"""Office management routes."""
import os
from fastapi import APIRouter, Request, Form, Depends, status, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import psycopg2

import config
from data import get_db_connection, get_all_offices, get_office_by_id, get_user_role

router = APIRouter()

def _get_templates():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
    return Jinja2Templates(directory=TEMPLATES_DIR)

@router.get("/account-management", response_class=None, summary="Account Management - Add/Manage Offices")
async def account_management(request: Request, db = Depends(get_db_connection)):
    """Account management page for HQ admin to manage offices and admins."""
    from fastapi.responses import HTMLResponse
    templates = _get_templates()
    
    user_email = request.session.get("user_email")
    user_role = request.session.get("user_role", "employee")
    
    if not user_email:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    if user_role != "hq_admin":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    
    offices = get_all_offices(db)
    
    return templates.TemplateResponse("account_management.html", {
        "request": request,
        "user_email": user_email,
        "offices": offices
    })

@router.post("/api/create-office", response_class=RedirectResponse, summary="Create new office and HR admin")
async def create_office(
    request: Request,
    office_name: str = Form(...),
    admin_name: str = Form(...),
    admin_email: str = Form(...),
    admin_password: str = Form(...),
    office_latitude: float = Form(None),
    office_longitude: float = Form(None),
    office_radius: int = Form(default=500),
    db = Depends(get_db_connection)
):
    """Create a new office and its admin account."""
    user_email = request.session.get("user_email")
    user_role = request.session.get("user_role")
    
    if not user_email or user_role != "hq_admin":
        return RedirectResponse(url="/hr-management?error=Only HQ admin can create offices", status_code=status.HTTP_303_SEE_OTHER)
    
    try:
        cursor = db.cursor()
        
        cursor.execute(
            """INSERT INTO offices (office_name, admin_email, office_latitude, office_longitude, office_radius_meters)
               VALUES (%s, %s, %s, %s, %s)
               RETURNING id""",
            (office_name, admin_email, office_latitude, office_longitude, office_radius)
        )
        office_id = cursor.fetchone()[0]
        db.commit()
        
        cursor.execute(
            """INSERT INTO employee_details (name, email, password, office_id, job_role)
               VALUES (%s, %s, %s, %s, %s)""",
            (admin_name, admin_email, admin_password, office_id, "Office Admin")
        )
        db.commit()
        cursor.close()
        
        return RedirectResponse(
            url=f"/account-management?success=Office '{office_name}' created with admin '{admin_email}'",
            status_code=status.HTTP_303_SEE_OTHER
        )
    except psycopg2.IntegrityError as e:
        db.rollback()
        cursor.close()
        return RedirectResponse(
            url="/account-management?error=Admin email already exists",
            status_code=status.HTTP_303_SEE_OTHER
        )
    except Exception as e:
        db.rollback()
        cursor.close()
        return RedirectResponse(
            url=f"/account-management?error=Error creating office: {str(e)}",
            status_code=status.HTTP_303_SEE_OTHER
        )

@router.post("/api/update-office", response_class=RedirectResponse, summary="Update office details")
async def update_office(
    request: Request,
    office_id: int = Form(...),
    office_name: str = Form(...),
    office_latitude: float = Form(None),
    office_longitude: float = Form(None),
    office_radius: int = Form(default=500),
    db = Depends(get_db_connection)
):
    """Update office details."""
    user_email = request.session.get("user_email")
    user_role = request.session.get("user_role")
    
    if not user_email or user_role != "hq_admin":
        return RedirectResponse(url="/account-management?error=Only HQ admin can update offices", status_code=status.HTTP_303_SEE_OTHER)
    
    try:
        cursor = db.cursor()
        cursor.execute(
            """UPDATE offices 
               SET office_name = %s, office_latitude = %s, office_longitude = %s, office_radius_meters = %s
               WHERE id = %s""",
            (office_name, office_latitude, office_longitude, office_radius, office_id)
        )
        db.commit()
        cursor.close()
        
        return RedirectResponse(
            url=f"/account-management?success=Office '{office_name}' updated successfully",
            status_code=status.HTTP_303_SEE_OTHER
        )
    except Exception as e:
        db.rollback()
        cursor.close()
        return RedirectResponse(
            url=f"/account-management?error=Error updating office: {str(e)}",
            status_code=status.HTTP_303_SEE_OTHER
        )

@router.delete("/api/delete-office/{office_id}", response_class=JSONResponse, summary="Delete office")
async def delete_office_api(
    office_id: int,
    request: Request,
    db = Depends(get_db_connection)
):
    """Delete an office and its associated data."""
    user_email = request.session.get("user_email")
    user_role = request.session.get("user_role")
    
    if not user_email or user_role != "hq_admin":
        raise HTTPException(status_code=403, detail="Only HQ admin can delete offices")
    
    try:
        cursor = db.cursor()
        
        cursor.execute("SELECT office_name FROM offices WHERE id = %s", (office_id,))
        office = cursor.fetchone()
        
        if not office:
            cursor.close()
            return {"success": False, "error": "Office not found"}
        
        office_name = office[0]
        
        cursor.execute("DELETE FROM attendance WHERE user_email IN (SELECT email FROM employee_details WHERE office_id = %s)", (office_id,))
        cursor.execute("DELETE FROM employee_details WHERE office_id = %s", (office_id,))
        cursor.execute("DELETE FROM offices WHERE id = %s", (office_id,))
        db.commit()
        cursor.close()
        
        return {"success": True, "message": f"Office '{office_name}' deleted successfully"}
    except Exception as e:
        db.rollback()
        cursor.close()
        return {"success": False, "error": str(e)}

@router.get("/api/get-all-offices", response_class=JSONResponse, summary="Get all offices")
async def get_all_offices_api(
    request: Request,
    db = Depends(get_db_connection)
):
    """Fetch all offices for account management panel."""
    user_email = request.session.get("user_email")
    user_role = request.session.get("user_role")
    
    if not user_email or user_role != "hq_admin":
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    offices = get_all_offices(db)
    return {"offices": offices}
