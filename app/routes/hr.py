"""HR Management dashboard and manual attendance routes."""
import os
from datetime import datetime, date, timedelta, time
import pytz
import psycopg2.extras

from fastapi import APIRouter, Request, Form, Depends, status
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

import config
from data import get_db_connection, fetch_employees_by_office, get_office_by_id, fetch_employee_by_email, get_all_offices, get_user_role
from services import calculate_working_days_and_leaves_for_employee, calculate_leave_days_for_employee
from app.utils.timezone import IST, get_ist_date
from employees import users as static_users

router = APIRouter()

def _get_templates():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
    return Jinja2Templates(directory=TEMPLATES_DIR)

@router.get("/hr-management", response_class=HTMLResponse, name="hr_management", summary="HR Management Dashboard")
async def hr_management(request: Request, db = Depends(get_db_connection)):
    """HR-only page showing employees for the current office."""
    templates = _get_templates()
    user_email = request.session.get("user_email")
    office_id = request.session.get("office_id")
    user_role = request.session.get("user_role", "employee")
    
    if not user_email:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    if user_role not in ["hq_admin", "office_admin"]:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    
    employees = fetch_employees_by_office(db, office_id)
    
    current_office = get_office_by_id(db, office_id) if office_id else None
    office_name = current_office["office_name"] if current_office else "All Offices"
    all_offices = get_all_offices(db) if user_role == "hq_admin" else [current_office] if current_office else []
    
    today = get_ist_date()
    start_ist = datetime.combine(today, time.min).replace(tzinfo=IST)
    end_ist = datetime.combine(today, time.max).replace(tzinfo=IST)
    start_utc = start_ist.astimezone(pytz.UTC)
    end_utc = end_ist.astimezone(pytz.UTC)
    
    cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    for emp in employees:
        email = emp.get("email")
        if email:
            cursor.execute(
                "SELECT 1 FROM attendance WHERE user_email = %s AND event_time >= %s AND event_time <= %s LIMIT 1",
                (email, start_utc, end_utc)
            )
            emp["present_today"] = bool(cursor.fetchone())
            
            cursor.execute(
                "SELECT comment FROM attendance WHERE user_email = %s AND comment IS NOT NULL ORDER BY event_time DESC LIMIT 1",
                (email,)
            )
            comment_record = cursor.fetchone()
            emp["last_comment"] = comment_record.get("comment") if comment_record else None
            
            calculated_working_days, _, _ = calculate_working_days_and_leaves_for_employee(email, today, office_id)
            emp["total_working"] = calculated_working_days
            
            # Calculate leave days dynamically (ignoring database value which may be incorrect)
            calculated_leave_days = calculate_leave_days_for_employee(email, today, office_id)
            emp["total_leave"] = calculated_leave_days
        
        static_data = static_users.get(emp['email'], {})
        emp['salary'] = static_data.get('salary', 'Not Set')
    
    cursor.close()
    
    return templates.TemplateResponse("hr_management.html", {
        "request": request,
        "employees": employees,
        "is_hr": True,
        "user_email": user_email,
        "office_name": office_name,
        "all_offices": all_offices,
        "current_office_id": office_id
    })

@router.post("/manual-attendance", response_class=RedirectResponse, summary="Add manual attendance record")
async def manual_attendance(
    request: Request,
    employee_email: str = Form(...),
    attendance_date: str = Form(...),
    attendance_time: str = Form(...),
    action: str = Form(...),
    db = Depends(get_db_connection)
):
    """Allow HR and Office Admins to manually add attendance records for employees."""
    user_email = request.session.get("user_email")
    office_id = request.session.get("office_id", 1)
    user_role = request.session.get("user_role", "employee")
    
    if user_role not in ["hq_admin", "office_admin"]:
        return RedirectResponse(url="/?error=Access+Denied", status_code=status.HTTP_303_SEE_OTHER)
    
    try:
        employee = fetch_employee_by_email(db, employee_email)
        if not employee:
            return RedirectResponse(
                url="/hr-management?error=Employee not found",
                status_code=status.HTTP_303_SEE_OTHER
            )
        
        if user_role == "office_admin" and employee.get('office_id') != office_id:
            return RedirectResponse(
                url="/hr-management?error=Cannot add attendance for employees in other offices",
                status_code=status.HTTP_303_SEE_OTHER
            )
        
        if action not in ["check-in", "check-out"]:
            return RedirectResponse(
                url="/hr-management?error=Invalid action",
                status_code=status.HTTP_303_SEE_OTHER
            )
        
        try:
            event_date = datetime.strptime(attendance_date, "%Y-%m-%d").date()
            event_time = datetime.strptime(attendance_time, "%H:%M").time()
            event_datetime = datetime.combine(event_date, event_time)
        except ValueError:
            return RedirectResponse(
                url="/hr-management?error=Invalid date or time format",
                status_code=status.HTTP_303_SEE_OTHER
            )
        
        cursor = db.cursor()
        cursor.execute(
            """INSERT INTO attendance (user_email, action, event_time, latitude, longitude, location_text)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (employee_email, action, event_datetime, None, None, "Manual Entry by HR")
        )
        
        if action == "check-in":
            cursor.execute(
                """UPDATE employee_details 
                   SET total_working = total_working + 1 
                   WHERE email = %s""",
                (employee_email,)
            )
        
        db.commit()
        cursor.close()
        
        print(f"Manual attendance added: {employee_email} - {action} at {event_datetime} by {user_email}")
        
        return RedirectResponse(
            url="/hr-management?success=Attendance record added successfully",
            status_code=status.HTTP_303_SEE_OTHER
        )
        
    except Exception as err:
        print(f"Error in manual_attendance: {err}")
        return RedirectResponse(
            url=f"/hr-management?error=An error occurred: {str(err)}",
            status_code=status.HTTP_303_SEE_OTHER
        )
