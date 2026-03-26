import os
import uvicorn
import csv
import io
import uuid
import psycopg2
import psycopg2.extras
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta, timezone, time
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from starlette.middleware.sessions import SessionMiddleware
from typing import Optional
import logging

import config
from bills_services import (
    create_invoice,
    fetch_invoice_by_id,
    fetch_invoice_by_number,
    fetch_all_invoices,
    update_invoice,
    update_invoice_status,
    delete_invoice,
    create_gst_bill,
    fetch_gst_bill_by_id,
    fetch_gst_bill_by_number,
    fetch_all_gst_bills,
    update_gst_bill_status,
    delete_gst_bill,
    get_invoice_summary,
    get_gst_bill_summary,
    DuplicateInvoiceNumberError,
)
from bills_schema import InvoiceCreate, InvoiceUpdate, GSTBillCreate, GSTBillUpdate
from bills_models import initialize_billing_schema

#  --- Local Imports ---
from employees import users as static_users 
from data import (
    get_db_connection, fetch_attendance_for_today, fetch_all_employees, fetch_employee_by_email,
    submit_employee_comment, get_employee_comments, get_unread_comments_for_hr, 
    get_all_comments_for_hr, mark_comment_as_read, get_unread_comment_count,
    fetch_attendance_for_period, get_all_offices, get_office_by_id, get_user_office_id, 
    get_user_role, fetch_employees_by_office
)
from services import calculate_working_days_and_leaves_for_employee, is_at_office, mark_leaves_for_absent_employees
from schema import initialize_database_schema 

# ===========================================================================
# TIMEZONE CONFIGURATION
# ===========================================================================
IST = pytz.timezone('Asia/Kolkata')  # India Standard Time

def get_ist_now():
    """Get current time in IST (Asia/Kolkata)."""
    return datetime.now(IST)

def get_ist_date():
    """Get current date in IST."""
    return get_ist_now().date() 

# ===========================================================================
# FastAPI APP INITIALIZATION
# ===========================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Application startup...") 
    initialize_database_schema()
    initialize_billing_schema()  # Initialize billing tables
    
    # Initialize APScheduler for daily absence marking
    scheduler = BackgroundScheduler()
    
    # Schedule job to run every day at 8 PM IST (which is 2:30 PM UTC, but we'll use a simpler hour)
    # The job will check for employees who haven't clocked in for 3+ days
    scheduler.add_job(mark_leaves_for_absent_employees, 'cron', hour=14, minute=30, timezone='Asia/Kolkata')
    
    try:
        scheduler.start()
        print("✓ Scheduler started - Absence marking enabled")
    except Exception as e:
        print(f"⚠️ Scheduler initialization failed: {e}")
    
    yield
    
    print("Application shutdown...")
    if scheduler.running:
        scheduler.shutdown()


# Set absolute paths for Render compatibility
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

app = FastAPI(title="Zugo Attendance Management System", lifespan=lifespan)

# Add SessionMiddleware before mounting static files
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET_KEY", "change_me_in_production_use_strong_random_key"))

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Jinja2 Templates setup
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Custom exception handler for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Log validation errors for debugging"""
    logging.error(f"Validation error on {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body}
    )

@app.get("/", response_class=HTMLResponse, summary="Display login page")
async def login_page(request: Request): 
    """Serves the login page."""
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/", response_class=RedirectResponse)
async def handle_login(
    request: Request, 
    email: str = Form(...), 
    password: str = Form(...),
    db = Depends(get_db_connection)
):
    """Processes login form submission, authenticates user, and sets session."""
    # Check if email is in allowed employees list or is an office admin
    employee = fetch_employee_by_email(db, email)
    if not employee:
        return RedirectResponse(url="/?error=Access+Denied:+Not+an+authorized+employee", status_code=status.HTTP_303_SEE_OTHER)
    
    if employee["password"] != password:
        return RedirectResponse(url="/?error=Invalid+Credentials", status_code=status.HTTP_303_SEE_OTHER)
    
    request.session["user_email"] = email
    
    # Determine user role and set office_id
    user_role = get_user_role(db, email)
    request.session["user_role"] = user_role
    
    # Set office_id based on user assignment
    office_id = get_user_office_id(db, email)
    if office_id:
        request.session["office_id"] = office_id
    
    # Redirect based on role
    if user_role == "hq_admin":
        return RedirectResponse(url="/hr-management", status_code=status.HTTP_303_SEE_OTHER)
    elif user_role == "office_admin":
        return RedirectResponse(url="/hr-management", status_code=status.HTTP_303_SEE_OTHER)
    else:
        return RedirectResponse(url="/report", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/signup", response_class=HTMLResponse, summary="Handle new user registration")
async def signup(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db = Depends(get_db_connection)
):
    """Registers a new employee."""
    # Check if email is in allowed employees list
    if email not in static_users:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Email not authorized. Contact HR."})
    
    if fetch_employee_by_email(db, email):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Email already registered"})
    
    user_data = static_users.get(email)
    if user_data:
        name = user_data.get("name", name)
        photo = user_data.get("photo", "profile.jpg")
        phone = user_data.get("phone")
        parent_phone = user_data.get("parent_phone")
        dob = user_data.get("dob")
        gender = user_data.get("gender")
        employee_number = user_data.get("employee_number")
        aadhar = user_data.get("aadhar")
        joining_date = user_data.get("joining_date")
        native = user_data.get("native")
        address = user_data.get("address")
        job_role = user_data.get("job_role", "Employee")
        pan_card = user_data.get("pan_card")
        salary = user_data.get("salary")
        bank_details = user_data.get("bank_details")
    else:
        photo = "profile.jpg"
        phone = parent_phone = dob = gender = employee_number = aadhar = joining_date = native = address = None
        job_role = "Employee"
        pan_card = None
        salary = None
        bank_details = None
    
    cursor = db.cursor()
    cursor.execute(
        """INSERT INTO employee_details 
           (name, email, password, photo, phone, parent_phone, dob, gender, 
            employee_number, aadhar, joining_date, native, address, job_role, pan_card, salary, bank_details)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (name, email, password, photo, phone, parent_phone, dob, gender,
         employee_number, aadhar, joining_date, native, address, job_role, pan_card, salary, bank_details)
    )
    db.commit()
    cursor.close()
    
    request.session["user_email"] = email
    return RedirectResponse(url="/report", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/report", response_class=HTMLResponse, name="report", summary="Display employee attendance")
async def report(request: Request, period: str = "30", db = Depends(get_db_connection)):
    """Shows the main dashboard for a logged-in employee."""
    user_email = request.session.get("user_email")
    if not user_email:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    if user_email == config.HR_EMAIL:
        return RedirectResponse(url="/hr-management", status_code=status.HTTP_303_SEE_OTHER)

    user_data = fetch_employee_by_email(db, user_email) or _build_user_from_static(user_email)
    if not user_data:
        request.session.clear()
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    records = fetch_attendance_for_today(db, user_email)
    sorted_records = sorted(records, key=lambda x:  x["event_time"], reverse=True)

    # Map period parameter to days
    period_map = {"30": 30, "180": 180, "365": 365}
    days = period_map.get(period, 30)
    
    report_data, total_seconds, leave_count, sunday_count = _build_report_for_user(db, user_email, days=days)
    total_hours = total_seconds / 3600 if total_seconds else 0

    is_hr = user_email == config.HR_EMAIL

    return templates.TemplateResponse("report.html", {
        "request": request,
        "user":  user_data,
        "records": sorted_records,
        "report_data": report_data,
        "total_working_hours": f"{total_hours:.2f}",
        "error": request.query_params.get("error"),
        "success": request.query_params.get("success"),
        "is_hr": is_hr,
        "user_email": user_email,
        "period": period
    }) 

@app.get("/download_report", summary="Download attendance report as CSV")
async def download_report(request: Request, period: str = "30", db = Depends(get_db_connection)):
    """Return a CSV file of the user's attendance report."""
    user_email = request.session.get("user_email")
    if not user_email:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    # Map period parameter to days
    period_map = {"30": 30, "180": 180, "365": 365}
    days = period_map.get(period, 30)
    
    report_data, _, _, _ = _build_report_for_user(db, user_email, days=days)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Check In", "Check Out", "Total Hours Worked"])
    for row in report_data:
        writer.writerow([row.get("day"), row.get("check_in"), row.get("check_out"), row.get("total_hours")])

    csv_content = output.getvalue()
    output.close()
    
    period_label = f"{days} days"
    if days == 180:
        period_label = "6 months"
    elif days == 365:
        period_label = "12 months"
    elif days == 30:
        period_label = "1 month"

    filename = f"attendance_{user_email.replace('@', '_at_')}_{period_label.replace(' ', '_')}.csv"
    return Response(content=csv_content, media_type="text/csv", headers={
        "Content-Disposition":  f"attachment; filename={filename}"
    })

@app.get("/dashboard", response_class=HTMLResponse, name="dashboard_view", summary="Display employee dashboard (profile view)")
async def dashboard_view(request: Request, db = Depends(get_db_connection)):
    """Render dashboard.html showing the employee's full profile."""
    user_email = request.session.get("user_email")
    if not user_email:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    user = fetch_employee_by_email(db, user_email) or _build_user_from_static(user_email)
    if not user:
        request.session.clear()
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    user_role = get_user_role(db, user_email)
    is_hr = user_role in ["hq_admin", "office_admin"]

    return templates.TemplateResponse("dashboard.html", {
        "request":  request,
        "user": user,
        "is_hr":  is_hr,
        "user_role": user_role,
        "user_email": user_email,
        "error": request.query_params.get("error"),
        "success": request.query_params.get("success")
    })

@app.post("/attendance", summary="Handle check-in/check-out actions")
async def handle_attendance(
    request: Request,
    action: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    comment: str = Form(None),
    timezone_offset: int = Form(default=330),  # Default IST (UTC+5:30 = 330 minutes)
    db = Depends(get_db_connection)
):
    """Processes check-in and check-out requests.""" 
    user_email = request.session.get("user_email")
    if not user_email:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    try:
        if not is_at_office(float(latitude), float(longitude)):
            return RedirectResponse(
                url=f"/report?error=Location+outside+office+bounds: +{latitude:.6f},+{longitude:.6f}",
                status_code=status.HTTP_303_SEE_OTHER
            )
    except ValueError:
        return RedirectResponse(
            url="/report?error=Invalid+location+data. +Please+enable+location+services",
            status_code=status.HTTP_303_SEE_OTHER
        )

    # Get current time in IST
    now_ist = get_ist_now()
    current_time = now_ist.time()
    today = now_ist.date()
    
    # Store as UTC for database (convert IST to UTC)
    now_utc = datetime.now(pytz.UTC)
    
    cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(
        """
        SELECT * FROM attendance 
        WHERE user_email = %s AND DATE(event_time AT TIME ZONE 'Asia/Kolkata') = %s
        ORDER BY event_time DESC
        """,
        (user_email, today)
    )
    todays_records = cursor.fetchall()
    cursor.close()

    if action == "check-in":
        is_morning = config.CHECKIN_MORNING_START <= current_time <= config.CHECKIN_MORNING_END
        is_afternoon = config.CHECKIN_AFTERNOON_START <= current_time <= config.CHECKIN_AFTERNOON_END

        if not (is_morning or is_afternoon):
            return RedirectResponse(
                url=f"/report?error=Check-in+only+allowed+between+{config.CHECKIN_MORNING_START}+and+{config.CHECKIN_MORNING_END}+or+between+{config.CHECKIN_AFTERNOON_START}+and+{config.CHECKIN_AFTERNOON_END}",
                status_code=status.HTTP_303_SEE_OTHER
            )

        if any(r['action'] == 'check-in' for r in todays_records):
            return RedirectResponse(
                url="/report?error=Already+checked+in+today",
                status_code=status.HTTP_303_SEE_OTHER
            )

    elif action == "check-out":  
        if current_time < config.CHECKOUT_MIN_TIME:
            return RedirectResponse(
                url=f"/report?error=Check-out+only+allowed+after+{config.CHECKOUT_MIN_TIME}",
                status_code=status.HTTP_303_SEE_OTHER
            )

        if not any(r['action'] == 'check-in' for r in todays_records):
            return RedirectResponse(
                url="/report?error=Must+check-in+before+checking+out",
                status_code=status.HTTP_303_SEE_OTHER
            )

        if any(r['action'] == 'check-out' for r in todays_records):
            return RedirectResponse(
                url="/report? error=Already+checked+out+today",
                status_code=status.HTTP_303_SEE_OTHER
            )

    try:
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO attendance 
            (user_email, action, event_time, latitude, longitude, location_text, comment)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (user_email, action, now_utc, latitude, longitude, f"{latitude:.6f}, {longitude:.6f}", comment if comment else None)
        )
        db.commit()
        cursor.close()

        if action == "check-in":  
            working_days, _, _ = calculate_working_days_and_leaves_for_employee(user_email, today)
            cursor = db.cursor()
            cursor.execute(
                "UPDATE employee_details SET total_working = %s WHERE email = %s",
                (working_days, user_email)
            )
            db.commit()
            cursor.close()

        success_msg = f"Successfully+{action.replace('-', '+')}+at+{now_ist.strftime('%I:%M+%p')}"
        return RedirectResponse(
            url=f"/report?success={success_msg}",
            status_code=status.HTTP_303_SEE_OTHER
        )
    except Exception as e:  
        return RedirectResponse(
            url=f"/report?error=Database+error: +{str(e)}",
            status_code=status.HTTP_303_SEE_OTHER
        )

@app.get("/employees", response_class=HTMLResponse, name="employees_page", summary="Display employees list")
async def employees_page(request: Request, db = Depends(get_db_connection)):
    """Display list of employees for current office."""
    user_email = request.session.get("user_email")
    office_id = request.session.get("office_id")
    user_role = request.session.get("user_role", "employee")
    
    if not user_email:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        
    is_hr = user_role in ["hq_admin", "office_admin"]
    
    # Get employees for this office
    all_employees = fetch_employees_by_office(db, office_id)
    all_employees = [emp for emp in all_employees if emp.get("email") != config.HR_EMAIL]
    
    # Get current office name
    current_office = get_office_by_id(db, office_id) if office_id else None
    office_name = current_office["office_name"] if current_office else "All Offices"
    
    try:
        cursor = db.cursor()
        today = get_ist_date()
        start_ist = datetime.combine(today, time.min).replace(tzinfo=IST)
        end_ist = datetime.combine(today, time.max).replace(tzinfo=IST)
        start_utc = start_ist.astimezone(pytz.UTC)
        end_utc = end_ist.astimezone(pytz.UTC)
        for emp in all_employees:
            email = emp.get("email")
            if email:
                cursor.execute(
                    "SELECT 1 FROM attendance WHERE user_email = %s AND event_time >= %s AND event_time <= %s LIMIT 1",
                    (email, start_utc, end_utc)
                )
                emp["present_today"] = bool(cursor.fetchone())
                
                if is_hr:
                    static_data = static_users.get(email, {})
                    emp["salary"] = static_data.get("salary", "Not Set")
                    
        cursor.close()
    except Exception:
        for emp in all_employees:
            emp["present_today"] = False
            if is_hr:
                emp["salary"] = None
                
    return templates.TemplateResponse("employee_list.html", {
        "request": request,
        "employees": all_employees,
        "is_hr": is_hr,
        "user_email": user_email,
        "office_name": office_name
    })

@app.get("/hr-management", response_class=HTMLResponse, name="hr_management", summary="HR Management Dashboard")
async def hr_management(request: Request, db = Depends(get_db_connection)):
    """HR-only page showing employees for the current office."""
    user_email = request.session.get("user_email")
    office_id = request.session.get("office_id")
    user_role = request.session.get("user_role", "employee")
    
    if not user_email:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    # Only HQ admin and office admin can access
    if user_role not in ["hq_admin", "office_admin"]:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    
    # Get employees for this office
    employees = fetch_employees_by_office(db, office_id)
    
    # Get current office name and all offices for dropdown
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
            
            # Fetch latest comment from employee
            cursor.execute(
                "SELECT comment FROM attendance WHERE user_email = %s AND comment IS NOT NULL ORDER BY event_time DESC LIMIT 1",
                (email,)
            )
            comment_record = cursor.fetchone()
            emp["last_comment"] = comment_record.get("comment") if comment_record else None
            
            calculated_working_days, period_start, period_end = calculate_working_days_and_leaves_for_employee(email, today)
            emp["total_working"] = calculated_working_days
        
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

@app.get("/account-management", response_class=HTMLResponse, summary="Account Management - Add/Manage Offices")
async def account_management(request: Request, db = Depends(get_db_connection)):
    """Account management page for HQ admin to manage offices and admins."""
    user_email = request.session.get("user_email")
    user_role = request.session.get("user_role", "employee")
    
    if not user_email:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    # Only HQ admin can access account management
    if user_role != "hq_admin":
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    
    # Get all offices
    offices = get_all_offices(db)
    
    return templates.TemplateResponse("account_management.html", {
        "request": request,
        "user_email": user_email,
        "offices": offices
    })

@app.get("/api/employee/{email}", summary="Get employee details by email")
async def get_employee_api(email: str, request: Request, db = Depends(get_db_connection)):
    """API endpoint to fetch employee details for editing."""
    user_email = request.session.get("user_email")
    if not user_email or user_email != config.HR_EMAIL:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    employee = fetch_employee_by_email(db, email)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    return employee

@app.get("/api/check-hr-access", summary="Check if user has HR access")
async def check_hr_access(request: Request):
    """Check if logged-in user has admin access."""
    user_email = request.session.get("user_email")
    user_role = request.session.get("user_role", "employee")
    
    if not user_email:
        return {"is_hr": False, "message": "Not logged in"}
    
    is_admin = user_role in ["hq_admin", "office_admin"]
    if is_admin:
        return {"is_hr": True, "email": user_email, "role": user_role, "message": "Admin access granted"}
    else:
        return {"is_hr": False, "email": user_email, "role": user_role, "message": "Regular employee access only"}

@app.post("/manage-employee", response_class=RedirectResponse, summary="Add or edit employee")
async def manage_employee(
    request: Request,
    action: str = Form(...),
    name: str = Form(...),
    new_email: str = Form(...),
    password: str = Form(default=""),
    phone: str = Form(default=""),
    parent_phone: str = Form(default=""),
    employee_number: str = Form(default=""),
    job_role: str = Form(default="Employee"),
    dob: str = Form(default=""),
    gender: str = Form(default=""),
    joining_date: str = Form(default=""),
    native: str = Form(default=""),
    address: str = Form(default=""),
    aadhar: str = Form(default=""),
    pan_card: str = Form(default=""),
    bank_details: str = Form(default=""),
    salary: str = Form(default=""),
    email: str = Form(default=""),
    photo: UploadFile = File(None),
    db = Depends(get_db_connection)
):
    """Handle adding or editing employees (HR and Office Admins)."""
    user_email = request.session.get("user_email")
    office_id = request.session.get("office_id", 1)
    user_role = request.session.get("user_role", "employee")
    
    # Only HQ admin and office admin can manage employees
    if user_role not in ["hq_admin", "office_admin"]:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    
    # Office admins can only create employees in their own office
    # HQ admin can create employees in any office (defaults to 1)
    
    try:
        cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Handle photo upload
        photo_filename = None
        if photo and photo.filename:
            # Validate file
            allowed_extensions = {'jpg', 'jpeg', 'png', 'gif'}
            file_ext = photo.filename.rsplit('.', 1)[1].lower() if '.' in photo.filename else ''
            
            if file_ext not in allowed_extensions:
                return RedirectResponse(url="/hr-management?error=Invalid+photo+format", status_code=status.HTTP_303_SEE_OTHER)
            
            # Generate unique filename
            unique_id = str(uuid.uuid4())[:8]
            photo_filename = f"employee_{unique_id}_{name.replace(' ', '_')}.{file_ext}"
            photo_path = os.path.join(STATIC_DIR, photo_filename)
            
            # Save file
            try:
                contents = await photo.read()
                with open(photo_path, 'wb') as f:
                    f.write(contents)
            except Exception as e:
                print(f"Error saving photo: {e}")
                return RedirectResponse(url="/hr-management?error=Error+uploading+photo", status_code=status.HTTP_303_SEE_OTHER)
        
        if action == "add":
            # Check for duplicate email
            cursor.execute("SELECT email FROM employee_details WHERE email = %s", (new_email,))
            if cursor.fetchone():
                cursor.close()
                return RedirectResponse(url="/hr-management?error=Email already exists", status_code=status.HTTP_303_SEE_OTHER)
            
            # Check for duplicate name
            cursor.execute("SELECT name FROM employee_details WHERE LOWER(name) = LOWER(%s)", (name,))
            if cursor.fetchone():
                cursor.close()
                return RedirectResponse(url="/hr-management?error=Employee name already exists", status_code=status.HTTP_303_SEE_OTHER)
            
            # Use provided photo or default
            final_photo = photo_filename if photo_filename else "profile.jpg"
            
            cursor.execute(
                """INSERT INTO employee_details 
                   (name, email, password, phone, parent_phone, employee_number, job_role, dob, gender, joining_date, native, address, aadhar, pan_card, bank_details, salary, photo, office_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (name, new_email, password, phone, parent_phone, employee_number, job_role, dob, gender, joining_date, native, address, aadhar, pan_card, bank_details, salary, final_photo, office_id)
            )
            db.commit()
            
        elif action == "edit":
            # Check if email is being changed and if new email already exists (excluding current employee)
            if new_email != email:
                cursor.execute("SELECT email FROM employee_details WHERE email = %s AND email != %s", (new_email, email))
                if cursor.fetchone():
                    cursor.close()
                    return RedirectResponse(url="/hr-management?error=Email already exists", status_code=status.HTTP_303_SEE_OTHER)
            
            # Check if name is being changed and if new name already exists (excluding current employee)
            cursor.execute("SELECT name FROM employee_details WHERE LOWER(name) = LOWER(%s) AND email != %s", (name, email))
            if cursor.fetchone():
                cursor.close()
                return RedirectResponse(url="/hr-management?error=Employee name already exists", status_code=status.HTTP_303_SEE_OTHER)
            
            # Office admins can only edit employees in their office
            if user_role == "office_admin":
                cursor.execute("SELECT office_id FROM employee_details WHERE email = %s", (email,))
                emp_office = cursor.fetchone()
                if not emp_office or emp_office.get('office_id') != office_id:
                    cursor.close()
                    return RedirectResponse(url="/hr-management?error=Cannot edit employees from other offices", status_code=status.HTTP_303_SEE_OTHER)
            
            # Get current photo if not updating
            if not photo_filename:
                cursor.execute("SELECT photo FROM employee_details WHERE email = %s", (email,))
                result = cursor.fetchone()
                photo_filename = result.get('photo') if result else 'profile.jpg'
            
            if password:
                cursor.execute(
                    """UPDATE employee_details 
                       SET name = %s, email = %s, phone = %s, parent_phone = %s, employee_number = %s, job_role = %s, dob = %s, gender = %s, joining_date = %s, native = %s, address = %s, aadhar = %s, pan_card = %s, bank_details = %s, salary = %s, password = %s, photo = %s
                       WHERE email = %s""",
                    (name, new_email, phone, parent_phone, employee_number, job_role, dob, gender, joining_date, native, address, aadhar, pan_card, bank_details, salary, password, photo_filename, email)
                )
            else:
                cursor.execute(
                    """UPDATE employee_details 
                       SET name = %s, email = %s, phone = %s, parent_phone = %s, employee_number = %s, job_role = %s, dob = %s, gender = %s, joining_date = %s, native = %s, address = %s, aadhar = %s, pan_card = %s, bank_details = %s, salary = %s, photo = %s
                       WHERE email = %s""",
                    (name, new_email, phone, parent_phone, employee_number, job_role, dob, gender, joining_date, native, address, aadhar, pan_card, bank_details, salary, photo_filename, email)
                )
            db.commit()
        
        cursor.close()
        
    except psycopg2.Error as err:
        print(f"Database error: {err}")
        return RedirectResponse(url="/hr-management?error=Database error", status_code=status.HTTP_303_SEE_OTHER)
    
    return RedirectResponse(url="/hr-management?success=Employee saved", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/delete-employee", response_class=RedirectResponse, summary="Delete employee")
async def delete_employee(
    request: Request,
    email: str = Form(...),
    db = Depends(get_db_connection)
):
    """Delete an employee (HR and Office Admins)."""
    user_email = request.session.get("user_email")
    office_id = request.session.get("office_id", 1)
    user_role = request.session.get("user_role", "employee")
    
    # Only HQ admin and office admin can delete employees
    if user_role not in ["hq_admin", "office_admin"]:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    if email == config.HR_EMAIL:
        return RedirectResponse(url="/hr-management?error=Cannot delete HR account", status_code=status.HTTP_303_SEE_OTHER)
    
    try:
        cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Office admins can only delete employees in their office
        if user_role == "office_admin":
            cursor.execute("SELECT office_id FROM employee_details WHERE email = %s", (email,))
            emp = cursor.fetchone()
            if not emp or emp.get('office_id') != office_id:
                cursor.close()
                return RedirectResponse(url="/hr-management?error=Cannot delete employees from other offices", status_code=status.HTTP_303_SEE_OTHER)
        
        cursor.execute("DELETE FROM employee_details WHERE email = %s", (email,))
        db.commit()
        cursor.close()
        
    except psycopg2.Error as err:
        print(f"Database error: {err}")
        return RedirectResponse(url="/hr-management?error=Database error", status_code=status.HTTP_303_SEE_OTHER)
    
    return RedirectResponse(url="/hr-management?success=Employee deleted", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/manual-attendance", response_class=RedirectResponse, summary="Add manual attendance record")
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
    
    # Only HQ admin and office admin can add manual attendance
    if user_role not in ["hq_admin", "office_admin"]:
        return RedirectResponse(url="/?error=Access+Denied", status_code=status.HTTP_303_SEE_OTHER)
    
    try:
        employee = fetch_employee_by_email(db, employee_email)
        if not employee:
            return RedirectResponse(
                url="/hr-management?error=Employee not found",
                status_code=status.HTTP_303_SEE_OTHER
            )
        
        # Office admins can only add attendance for employees in their office
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
        
        # If check-in, increment total_working days
        if action == "check-in":
            cursor.execute(
                """UPDATE employee_details 
                   SET total_working = total_working + 1 
                   WHERE email = %s""",
                (employee_email,)
            )
        
        db.commit()
        cursor.close()
        
        print(f"Manual attendance added:  {employee_email} - {action} at {event_datetime} by {user_email}")
        
        return RedirectResponse(
            url="/hr-management?success=Attendance record added successfully",
            status_code=status.HTTP_303_SEE_OTHER
        )
        
    except psycopg2.Error as err:
        print(f"Database error in manual_attendance: {err}")
        return RedirectResponse(
            url="/hr-management?error=Database error occurred:  " + str(err),
            status_code=status.HTTP_303_SEE_OTHER
        )
    except Exception as err:
        print(f"Error in manual_attendance: {err}")
        return RedirectResponse(
            url="/hr-management?error=An error occurred: " + str(err),
            status_code=status.HTTP_303_SEE_OTHER
        )

@app.get("/api/attendance/{attendance_id}", summary="Get attendance record by ID")
async def get_attendance_record(attendance_id: int, request: Request, db = Depends(get_db_connection)):
    """Get a single attendance record (HR only)"""
    user_email = request.session.get("user_email")
    if not user_email or user_email != config.HR_EMAIL:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM attendance WHERE id = %s", (attendance_id,))
    record = cursor.fetchone()
    cursor.close()
    
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    
    return record


@app.get("/employee/{email}/attendance-report", response_class=HTMLResponse, summary="View employee attendance report")
async def view_employee_attendance_report(
    email: str,
    request: Request,
    period: str = "30",
    db = Depends(get_db_connection)
):
    """View attendance report for a specific employee (HR only)"""
    user_email = request.session.get("user_email")
    if not user_email or user_email != config.HR_EMAIL:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    employee = fetch_employee_by_email(db, email)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Map period parameter to days
    period_map = {"30": 30, "180": 180, "365": 365}
    days = period_map.get(period, 30)
    
    # Fetch attendance records with IDs
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    records = fetch_attendance_for_period(email, start_date, end_date)
    
    # Build report data and include attendance IDs
    report_data, total_seconds, leave_count, sunday_count = _build_report_for_user(db, email, days=days)
    total_hours = total_seconds / 3600 if total_seconds else 0
    
    # Enhance report_data with attendance IDs for edit/delete
    # Create a dictionary mapping dates to records for faster lookup
    records_by_date = {}
    for r in records:
        # Handle both timezone-aware and naive datetime objects
        event_time = r['event_time']
        if hasattr(event_time, 'date'):
            # Convert UTC to IST for date extraction (matching _build_report_for_user logic)
            if event_time.tzinfo is None:
                event_time_ist = IST.localize(event_time)
            else:
                event_time_ist = event_time.astimezone(IST)
            record_date = event_time_ist.date()
        else:
            # If it's a string, parse it
            if isinstance(event_time, str):
                event_time = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
            if event_time.tzinfo is None:
                event_time_ist = IST.localize(event_time)
            else:
                event_time_ist = event_time.astimezone(IST)
            record_date = event_time_ist.date()
        
        date_str = record_date.isoformat()
        if date_str not in records_by_date:
            records_by_date[date_str] = []
        records_by_date[date_str].append(r)
    
    # Now match report_data with records
    for day_record in report_data:
        day_str = day_record.get('day')
        if day_str and day_str in records_by_date:
            day_records = records_by_date[day_str]
            # Get check-in and check-out IDs
            check_in_rec = next((r for r in day_records if r.get('action') == 'check-in'), None)
            check_out_rec = next((r for r in day_records if r.get('action') == 'check-out'), None)
            day_record['check_in_id'] = check_in_rec.get('id') if check_in_rec and 'id' in check_in_rec else None
            day_record['check_out_id'] = check_out_rec.get('id') if check_out_rec and 'id' in check_out_rec else None
            # Use first record ID as primary for the row
            day_record['attendance_id'] = day_records[0].get('id') if day_records and 'id' in day_records[0] else None
    
    return templates.TemplateResponse("employee_report.html", {
        "request": request,
        "employee": employee,
        "records": sorted(records, key=lambda x: x["event_time"], reverse=True),
        "report_data": report_data,
        "total_working_hours": f"{total_hours:.2f}",
        "period": period,
        "is_hr": True
    })


@app.post("/attendance/{attendance_id}/delete", summary="Delete attendance record")
async def delete_attendance_record(
    attendance_id: int,
    request: Request,
    db = Depends(get_db_connection)
):
    """Delete an attendance record (HR only)"""
    user_email = request.session.get("user_email")
    if not user_email or user_email != config.HR_EMAIL:
        return {"success": False, "message": "Unauthorized"}
    
    try:
        cursor = db.cursor()
        # Get the record first to check if it's a check-in (to update total_working)
        cursor.execute("SELECT user_email, action FROM attendance WHERE id = %s", (attendance_id,))
        record = cursor.fetchone()
        
        if not record:
            cursor.close()
            return {"success": False, "message": "Attendance record not found"}
        
        user_email_emp, action = record
        
        # Delete the record
        cursor.execute("DELETE FROM attendance WHERE id = %s", (attendance_id,))
        
        # If it was a check-in, decrement total_working
        if action == "check-in":
            cursor.execute(
                """UPDATE employee_details 
                   SET total_working = GREATEST(total_working - 1, 0)
                   WHERE email = %s""",
                (user_email_emp,)
            )
        
        db.commit()
        cursor.close()
        
        return {"success": True, "message": "Attendance record deleted successfully"}
    except Exception as e:
        logging.error(f"Error deleting attendance record: {str(e)}", exc_info=True)
        return {"success": False, "message": f"Failed to delete attendance record: {str(e)}"}


@app.post("/attendance/{attendance_id}/update", summary="Update attendance record")
async def update_attendance_record(
    attendance_id: int,
    request: Request,
    attendance_date: str = Form(...),
    attendance_time: str = Form(...),
    action: str = Form(...),
    db = Depends(get_db_connection)
):
    """Update an attendance record (HR only)"""
    user_email = request.session.get("user_email")
    if not user_email or user_email != config.HR_EMAIL:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    try:
        # Get existing record
        cursor = db.cursor()
        cursor.execute("SELECT user_email, action FROM attendance WHERE id = %s", (attendance_id,))
        record = cursor.fetchone()
        
        if not record:
            cursor.close()
            return RedirectResponse(
                url="/hr-management?error=Attendance record not found",
                status_code=status.HTTP_303_SEE_OTHER
            )
        
        user_email_emp, old_action = record
        
        # Parse new datetime
        event_date = datetime.strptime(attendance_date, "%Y-%m-%d").date()
        event_time = datetime.strptime(attendance_time, "%H:%M").time()
        event_datetime = datetime.combine(event_date, event_time)
        
        # Update the record
        cursor.execute(
            "UPDATE attendance SET event_time = %s, action = %s WHERE id = %s",
            (event_datetime, action, attendance_id)
        )
        
        # If action changed from check-in to check-out or vice versa, update total_working
        if old_action == "check-in" and action == "check-out":
            cursor.execute(
                """UPDATE employee_details 
                   SET total_working = GREATEST(total_working - 1, 0)
                   WHERE email = %s""",
                (user_email_emp,)
            )
        elif old_action == "check-out" and action == "check-in":
            cursor.execute(
                """UPDATE employee_details 
                   SET total_working = total_working + 1
                   WHERE email = %s""",
                (user_email_emp,)
            )
        
        db.commit()
        cursor.close()
        
        return RedirectResponse(
            url="/hr-management?success=Attendance record updated successfully",
            status_code=status.HTTP_303_SEE_OTHER
        )
    except Exception as e:
        logging.error(f"Error updating attendance record: {str(e)}", exc_info=True)
        return RedirectResponse(
            url=f"/hr-management?error=Failed to update attendance: {str(e)}",
            status_code=status.HTTP_303_SEE_OTHER
        )


@app.post("/api/create-office", response_class=RedirectResponse, summary="Create new office and HR admin")
async def create_office(
    request: Request,
    office_name: str = Form(...),
    admin_name: str = Form(...),
    admin_email: str = Form(...),
    admin_password: str = Form(...),
    office_latitude: Optional[float] = Form(None),
    office_longitude: Optional[float] = Form(None),
    office_radius: int = Form(default=500),
    db = Depends(get_db_connection)
):
    """Create a new office and its admin account."""
    user_email = request.session.get("user_email")
    user_role = request.session.get("user_role")
    
    # Only HQ admin can create offices
    if not user_email or user_role != "hq_admin":
        return RedirectResponse(url="/hr-management?error=Only HQ admin can create offices", status_code=status.HTTP_303_SEE_OTHER)
    
    try:
        cursor = db.cursor()
        
        # 1. Create the office
        cursor.execute(
            """INSERT INTO offices (office_name, admin_email, office_latitude, office_longitude, office_radius_meters)
               VALUES (%s, %s, %s, %s, %s)
               RETURNING id""",
            (office_name, admin_email, office_latitude, office_longitude, office_radius)
        )
        office_id = cursor.fetchone()[0]
        db.commit()
        
        # 2. Create the HR/admin account for this office
        cursor.execute(
            """INSERT INTO employee_details (name, email, password, office_id, job_role)
               VALUES (%s, %s, %s, %s, %s)""",
            (admin_name, admin_email, admin_password, office_id, "Office Admin")
        )
        db.commit()
        cursor.close()
        
        # Redirect back with success message
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


@app.post("/api/update-office", response_class=RedirectResponse, summary="Update office details")
async def update_office(
    request: Request,
    office_id: int = Form(...),
    office_name: str = Form(...),
    office_latitude: Optional[float] = Form(None),
    office_longitude: Optional[float] = Form(None),
    office_radius: int = Form(default=500),
    db = Depends(get_db_connection)
):
    """Update office details."""
    user_email = request.session.get("user_email")
    user_role = request.session.get("user_role")
    
    # Only HQ admin can update offices
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


@app.delete("/api/delete-office/{office_id}", response_class=JSONResponse, summary="Delete office")
async def delete_office_api(
    office_id: int,
    request: Request,
    db = Depends(get_db_connection)
):
    """Delete an office and its associated data."""
    user_email = request.session.get("user_email")
    user_role = request.session.get("user_role")
    
    # Only HQ admin can delete offices
    if not user_email or user_role != "hq_admin":
        raise HTTPException(status_code=403, detail="Only HQ admin can delete offices")
    
    try:
        cursor = db.cursor()
        
        # Check if office exists
        cursor.execute("SELECT office_name FROM offices WHERE id = %s", (office_id,))
        office = cursor.fetchone()
        
        if not office:
            cursor.close()
            return {"success": False, "error": "Office not found"}
        
        office_name = office[0]
        
        # Delete associated employee records and attendance records
        cursor.execute("SELECT email FROM employee_details WHERE office_id = %s AND job_role = 'Office Admin'", (office_id,))
        admins = cursor.fetchall()
        
        # Delete attendance records for employees in this office
        cursor.execute("DELETE FROM attendance WHERE user_email IN (SELECT email FROM employee_details WHERE office_id = %s)", (office_id,))
        
        # Delete employee records from this office
        cursor.execute("DELETE FROM employee_details WHERE office_id = %s", (office_id,))
        
        # Delete the office itself
        cursor.execute("DELETE FROM offices WHERE id = %s", (office_id,))
        db.commit()
        cursor.close()
        
        return {"success": True, "message": f"Office '{office_name}' deleted successfully"}
    except Exception as e:
        db.rollback()
        cursor.close()
        return {"success": False, "error": str(e)}


@app.get("/api/get-all-offices", response_class=JSONResponse, summary="Get all offices")
async def get_all_offices_api(
    request: Request,
    db = Depends(get_db_connection)
):
    """Fetch all offices for account management panel."""
    user_email = request.session.get("user_email")
    user_role = request.session.get("user_role")
    
    # Only HQ admin can view all offices
    if not user_email or user_role != "hq_admin":
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    offices = get_all_offices(db)
    return {"offices": offices}


@app.get("/logout", summary="Log user out", name="logout")
async def logout(request: Request):
    """Clears the user session."""
    request.session.clear()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/terms", response_class=HTMLResponse, name="terms")
async def terms(request: Request):
    """Terms and Conditions page."""
    user_email = request.session.get("user_email")
    if not user_email:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    is_hr = user_email == config.HR_EMAIL
    
    return templates.TemplateResponse("terms.html", {
        "request": request,
        "is_hr": is_hr
    })

@app.get("/privacy", response_class=HTMLResponse, name="privacy")
async def privacy(request: Request):
    """Privacy Policy page."""
    user_email = request.session.get("user_email")
    if not user_email:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    is_hr = user_email == config.HR_EMAIL
    
    return templates.TemplateResponse("privacy.html", {
        "request": request,
        "is_hr": is_hr
    })

# ===========================================================================
# HELPER FUNCTIONS
# ===========================================================================

def _build_user_from_static(email):
    """Return a dict user object from the static `static_users` if available."""
    u = static_users.get(email)
    if not u:
        return None
    return {
        "name": u.get("name"),
        "email": u.get("email", email),
        "photo": u.get("photo", "profile.jpg"),
        "phone": u.get("phone"),
        "employee_number": u.get("employee_number"),
        "aadhar":  u.get("aadhar") or u.get("AADHAR"),
        "dob": u.get("dob"),
        "gender": u.get("gender"),
        "job_role": u.get("job_role", "Employee"),
        "native":  u.get("native"),
        "address": u.get("address"),
        "joining_date": u.get("joining_date"),
        "parent_phone": u.get("parent_phone"),
        "total_working":  u.get("total_working", 0),
        "total_leave": u.get("total_leave", 0),
        "pan_card": u.get("pan_card"),
        "salary": u.get("salary"),
        "bank_details": u.get("bank_details")
    }

def _build_report_for_user(db, user_email, days: int = 30):
    """Build report rows for the last `days` days for the given user."""
    # Use IST for date calculations
    end_date = get_ist_now()
    start_date = end_date - timedelta(days=days)
    
    # Convert start_date to UTC for database comparison
    start_date_utc = start_date.astimezone(pytz.UTC)

    cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(
        """
        SELECT event_time, action FROM attendance
        WHERE user_email = %s AND event_time >= %s
        ORDER BY event_time ASC
        """,
        (user_email, start_date_utc)
    )
    rows = cursor.fetchall()
    cursor.close()

    by_date = {}
    for r in rows:
        # Convert UTC to IST for display
        event_time_ist = r["event_time"].astimezone(IST) if r["event_time"].tzinfo else IST.localize(r["event_time"])
        d = event_time_ist.date().isoformat()
        by_date.setdefault(d, []).append({"event_time": event_time_ist, "action": r["action"]})

    report = []
    total_working_seconds = 0
    leave_count = 0
    sunday_count = 0
    
    # Generate all dates in the range
    current_date = start_date.date()
    end_date_only = end_date.date()
    
    while current_date <= end_date_only:
        day_str = current_date.isoformat()
        is_sunday = current_date.weekday() == 6  # 6 = Sunday in Python
        
        if day_str in by_date:
            # Date has attendance records
            events = by_date[day_str]
            check_ins = [e["event_time"] for e in events if e["action"] == "check-in"]
            check_outs = [e["event_time"] for e in events if e["action"] == "check-out"]

            check_in = min(check_ins).strftime("%I:%M %p") if check_ins else "-"
            check_out = max(check_outs).strftime("%I:%M %p") if check_outs else "-"

            seconds = 0
            if check_ins and check_outs:
                seconds = int((max(check_outs) - min(check_ins)).total_seconds())
                total_working_seconds += seconds

            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            total_str = f"{hours}h {minutes}m" if seconds else "-"
            
            # Determine status
            if is_sunday:
                status = "Sunday Work" if check_ins else "Sunday (Off)"
                sunday_count += 1 if check_ins else 0
            else:
                status = "Present" if check_ins else "Partial"

            report.append({
                "day": day_str,
                "check_in": check_in,
                "check_out": check_out,
                "total_hours": total_str,
                "status": status,
                "is_sunday": is_sunday
            })
        else:
            # Date has no attendance records
            if is_sunday:
                # Sunday with no attendance = office closed (don't count as leave)
                report.append({
                    "day": day_str,
                    "check_in": "-",
                    "check_out": "-",
                    "total_hours": "-",
                    "status": "Sunday (Off)",
                    "is_sunday": True
                })
            else:
                # Weekday with no attendance = leave/absent
                leave_count += 1
                report.append({
                    "day": day_str,
                    "check_in": "-",
                    "check_out": "-",
                    "total_hours": "-",
                    "status": "Absent/Leave",
                    "is_sunday": False
                })
        
        current_date += timedelta(days=1)

    return report, total_working_seconds, leave_count, sunday_count

# ===========================================================================
# EMPLOYEE COMMENTS & MESSAGING ENDPOINTS
# ===========================================================================

@app.post("/api/submit-comment", summary="Submit a comment to HR")
async def submit_comment(
    request: Request,
    comment_text: str = Form(...),
    db = Depends(get_db_connection)
):
    """Allow employees to submit comments/messages to HR."""
    user_email = request.session.get("user_email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Not logged in")
    
    if user_email == config.HR_EMAIL:
        raise HTTPException(status_code=403, detail="HR cannot submit comments")
    
    if not comment_text or not comment_text.strip():
        raise HTTPException(status_code=400, detail="Comment cannot be empty")
    
    success = submit_employee_comment(db, user_email, comment_text.strip())
    
    if success:
        return {"success": True, "message": "Comment submitted successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to submit comment")


@app.get("/api/my-comments", summary="Get my submitted comments")
async def get_my_comments(request: Request, db = Depends(get_db_connection)):
    """Get all comments submitted by the logged-in employee."""
    user_email = request.session.get("user_email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Not logged in")
    
    comments = get_employee_comments(db, user_email)
    return {"comments": comments}


@app.get("/api/hr/unread-comments-count", summary="Get unread comment count for HR")
async def get_unread_count(request: Request, db = Depends(get_db_connection)):
    """Get count of unread comments for HR notification badge."""
    user_email = request.session.get("user_email")
    if not user_email or user_email != config.HR_EMAIL:
        raise HTTPException(status_code=403, detail="HR access required")
    
    count = get_unread_comment_count(db)
    return {"unread_count": count}


@app.get("/api/hr/comments", summary="Get all comments for HR")
async def get_hr_comments(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    db = Depends(get_db_connection)
):
    """Get all employee comments for HR dashboard."""
    user_email = request.session.get("user_email")
    if not user_email or user_email != config.HR_EMAIL:
        raise HTTPException(status_code=403, detail="HR access required")
    
    comments = get_all_comments_for_hr(db, limit, offset)
    unread_count = get_unread_comment_count(db)
    
    return {
        "comments": comments,
        "unread_count": unread_count,
        "total": len(comments)
    }


@app.post("/api/hr/mark-comment-read/{comment_id}", summary="Mark comment as read")
async def mark_read(
    comment_id: int,
    request: Request,
    db = Depends(get_db_connection)
):
    """Mark a comment as read by HR."""
    user_email = request.session.get("user_email")
    if not user_email or user_email != config.HR_EMAIL:
        raise HTTPException(status_code=403, detail="HR access required")
    
    success = mark_comment_as_read(db, comment_id)
    
    if success:
        return {"success": True, "message": "Comment marked as read"}
    else:
        raise HTTPException(status_code=500, detail="Failed to mark comment as read")


@app.delete("/api/hr/delete-comment/{comment_id}", summary="Delete a comment")
async def delete_comment_endpoint(
    comment_id: int,
    request: Request,
    db = Depends(get_db_connection)
):
    """Delete a comment (HR only)."""
    user_email = request.session.get("user_email")
    if not user_email or user_email != config.HR_EMAIL:
        raise HTTPException(status_code=403, detail="HR access required")
    
    from data import delete_comment
    success = delete_comment(db, comment_id)
    
    if success:
        return {"success": True, "message": "Comment deleted"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete comment")


@app.post("/api/hr/edit-employee", summary="Edit employee details")
async def edit_employee_details(
    email: str = Form(...),
    name: str = Form(None),
    phone: str = Form(None),
    parent_phone: str = Form(None),
    dob: str = Form(None),
    gender: str = Form(None),
    employee_number: str = Form(None),
    aadhar: str = Form(None),
    joining_date: str = Form(None),
    native: str = Form(None),
    address: str = Form(None),
    job_role: str = Form(None),
    request: Request = None,
    db = Depends(get_db_connection)
):
    """Allow HR to edit employee details."""
    user_email = request.session.get("user_email") if request else None
    if not user_email or user_email != config.HR_EMAIL:
        raise HTTPException(status_code=403, detail="HR access required")
    
    try:
        cursor = db.cursor()
        update_fields = []
        update_values = []
        
        if name is not None:
            update_fields.append("name = %s")
            update_values.append(name)
        if phone is not None:
            update_fields.append("phone = %s")
            update_values.append(phone)
        if parent_phone is not None:
            update_fields.append("parent_phone = %s")
            update_values.append(parent_phone)
        if dob is not None:
            update_fields.append("dob = %s")
            update_values.append(dob)
        if gender is not None:
            update_fields.append("gender = %s")
            update_values.append(gender)
        if employee_number is not None:
            update_fields.append("employee_number = %s")
            update_values.append(employee_number)
        if aadhar is not None:
            update_fields.append("aadhar = %s")
            update_values.append(aadhar)
        if joining_date is not None:
            update_fields.append("joining_date = %s")
            update_values.append(joining_date)
        if native is not None:
            update_fields.append("native = %s")
            update_values.append(native)
        if address is not None:
            update_fields.append("address = %s")
            update_values.append(address)
        if job_role is not None:
            update_fields.append("job_role = %s")
            update_values.append(job_role)
        
        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        update_values.append(email)
        
        query = f"UPDATE employee_details SET {', '.join(update_fields)} WHERE email = %s"
        cursor.execute(query, update_values)
        db.commit()
        cursor.close()
        
        return {"success": True, "message": "Employee details updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating employee: {str(e)}")


@app.post("/api/hr/delete-employee", summary="Delete employee")
async def delete_employee_endpoint(
    email: str = Form(...),
    request: Request = None,
    db = Depends(get_db_connection)
):
    """Allow HR to delete an employee."""
    user_email = request.session.get("user_email") if request else None
    if not user_email or user_email != config.HR_EMAIL:
        raise HTTPException(status_code=403, detail="HR access required")
    
    if email == config.HR_EMAIL:
        raise HTTPException(status_code=403, detail="Cannot delete HR account")
    
    try:
        cursor = db.cursor()
        cursor.execute("DELETE FROM employee_details WHERE email = %s", (email,))
        db.commit()
        cursor.close()
        
        return {"success": True, "message": "Employee deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting employee: {str(e)}")

# FastAPI endpoints for invoice and GST bill management
def require_hr(request: Request):
    """Dependency to ensure HR/Admin access"""
    user_email = request.session.get("user_email")
    user_role = request.session.get("user_role", "employee")
    
    # Allow HQ admin and office admin
    if user_role not in ["hq_admin", "office_admin"]:
        raise HTTPException(status_code=403, detail="Access denied. Admin privileges required.")
    return user_email


# =========================================================================
# API ENDPOINTS FOR BILLING (AJAX CALLS)
# =========================================================================

@app.get("/api/invoice/{invoice_id}")
async def api_get_invoice(invoice_id: int, hr_email: str = Depends(require_hr)):
    """Get invoice details for API"""
    invoice = fetch_invoice_by_id(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@app.get("/api/gst-bill/{bill_id}")
async def api_get_gst_bill(bill_id: int, hr_email: str = Depends(require_hr)):
    """Get GST bill details for API"""
    bill = fetch_gst_bill_by_id(bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="GST bill not found")
    return bill


# =========================================================================
# INVOICE ENDPOINTS
# =========================================================================

@app.get("/billing", response_class=HTMLResponse, name="billing", summary="Display billing page")
async def get_billing(request: Request, hr_email: str = Depends(require_hr)):
    """Display billing dashboard with invoices and GST bills"""
    try:
        user_email = request.session.get("user_email")
        invoices = fetch_all_invoices(limit=100)
        bills = fetch_all_gst_bills(limit=100)
        
        # Calculate summaries
        invoice_summary = get_invoice_summary()
        bill_summary = get_gst_bill_summary()
        
        return templates.TemplateResponse("billing.html", {
            "request": request,
            "invoices": invoices,
            "bills": bills,
            "invoice_summary": invoice_summary,
            "bill_summary": bill_summary,
            "is_hr": True,
            "user_email": user_email
        })
    except Exception as e:
        print(f"Error in /billing endpoint: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Billing page error: {str(e)}")


@app.get("/quotation", response_class=HTMLResponse, summary="Display quotation page")
async def get_quotation(request: Request, hr_email: str = Depends(require_hr)):
    """Display quotation page for creating or viewing quotations"""
    from datetime import date
    return templates.TemplateResponse("quotation.html", {
        "request": request,
        "quote_date": date.today().isoformat()
    })


@app.get("/invoices", response_class=HTMLResponse, summary="Display invoices page")
async def get_invoices(request: Request, hr_email: str = Depends(require_hr)):
    """Display all invoices with filtering and search"""
    invoices = fetch_all_invoices(limit=100)
    
    # Calculate summary
    summary = get_invoice_summary()
    
    return templates.TemplateResponse("billing.html", {
        "request": request,
        "invoices": invoices,
        "summary": summary,
        "page": "invoices"
    })


@app.get("/invoice/{invoice_id}", response_class=HTMLResponse)
async def get_invoice_detail(invoice_id: int, request: Request, hr_email: str = Depends(require_hr)):
    """Get detailed view of a single invoice"""
    invoice = fetch_invoice_by_id(invoice_id)
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Normalize nullable fields to avoid template errors
    def to_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    
    # Extract and normalize values
    quantity = to_float(invoice.get("quantity"))
    rate = to_float(invoice.get("rate"))
    cgst = to_float(invoice.get("cgst"))
    sgst = to_float(invoice.get("sgst"))
    igst = to_float(invoice.get("igst"))
    
    # Calculate amounts
    subtotal = quantity * rate
    taxable_value = subtotal  # Same as subtotal, used in template
    cgst_amount = subtotal * cgst / 100
    sgst_amount = subtotal * sgst / 100
    igst_amount = subtotal * igst / 100
    total_tax_amount = cgst_amount + sgst_amount + igst_amount
    total_amount = subtotal + total_tax_amount

    # Round-off to nearest 2 decimal places (for display and amount in words)
    grand_total = round(total_amount, 2)
    round_off = round(grand_total - total_amount, 2)

    invoice = {
        **invoice,
        "vendor_address": invoice.get("vendor_address") or "",
        "customer_address": invoice.get("customer_address") or "",
        "vendor_gstin": invoice.get("vendor_gstin") or "",
        "customer_gstin": invoice.get("customer_gstin") or "",
        "hsn_code": invoice.get("hsn_code") or "",
        "uom": invoice.get("uom") or "No",
        "quantity": quantity,
        "rate": rate,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        # Calculated fields for template
        "subtotal": subtotal,
        "taxable_value": taxable_value,
        "cgst_amount": cgst_amount,
        "sgst_amount": sgst_amount,
        "igst_amount": igst_amount,
        "total_tax_amount": total_tax_amount,
        "total_amount": total_amount,
        "round_off": round_off,
        "grand_total": grand_total,
    }
    
    # Bank details for invoice
    bank_details = {
        "account_holder": "ZUGO PRIVATE LIMITED",
        "bank_name": "AXIS BANK",
        "account_number": "925020039794750",
        "ifsc_code": "UTIB0002810",
        "branch": "Kumar Nagar"
    }
    
    return templates.TemplateResponse("invoice_view.html", {
        "request": request,
        "invoice": invoice,
        "bank_details": bank_details,
        # Also pass calculated fields at root level for template access
        "taxable_value": taxable_value,
        "cgst_amount": cgst_amount,
        "sgst_amount": sgst_amount,
        "igst_amount": igst_amount,
        "total_amount": total_amount,
    })


@app.post("/invoice/create")
async def create_new_invoice(
    request: Request,
    invoice_no: str = Form(...),
    invoice_date: str = Form(...),
    vendor_name: str = Form(...),
    vendor_gstin: Optional[str] = Form(None),
    vendor_address: Optional[str] = Form(None),
    customer_name: str = Form(...),
    customer_gstin: Optional[str] = Form(None),
    customer_address: Optional[str] = Form(None),
    description: str = Form(...),
    hsn_code: Optional[str] = Form(None),
    uom: Optional[str] = Form(None),
    quantity: str = Form(...),
    rate: str = Form(...),
    cgst: Optional[str] = Form("0"),
    sgst: Optional[str] = Form("0"),
    igst: Optional[str] = Form("0"),
    notes: Optional[str] = Form(None),
    hr_email: str = Depends(require_hr)
):
    """Create a new invoice"""
    try:
        # Convert string form values to floats, handling empty strings
        def to_float(value: str, default: float = 0.0) -> float:
            if not value or value.strip() == "":
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        
        invoice_data = {
            "invoice_no": invoice_no,
            "date": invoice_date,
            "vendor_name": vendor_name,
            "vendor_gstin": vendor_gstin,
            "vendor_address": vendor_address,
            "customer_name": customer_name,
            "customer_gstin": customer_gstin,
            "customer_address": customer_address,
            "description": description,
            "hsn_code": hsn_code,
            "uom": uom,
            "quantity": to_float(quantity, 1.0),
            "rate": to_float(rate, 0.0),
            "cgst": to_float(cgst, 0.0),
            "sgst": to_float(sgst, 0.0),
            "igst": to_float(igst, 0.0),
            "notes": notes,
            "status": "draft"
        }
        
        result = create_invoice(invoice_data)
        return RedirectResponse(url=f"/invoice/{result['id']}", status_code=303)
    except DuplicateInvoiceNumberError as e:
        logging.warning(f"Duplicate invoice number when creating invoice: {invoice_no}")
        raise HTTPException(
            status_code=409,
            detail="Invoice number already exists. Please use a different invoice number."
        )
    except psycopg2.errors.UniqueViolation:
        logging.warning(f"Duplicate invoice number when creating invoice: {invoice_no}")
        raise HTTPException(
            status_code=409,
            detail="Invoice number already exists. Please use a different invoice number."
        )
    except ValueError as e:
        logging.warning(f"Validation error when creating invoice: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.error(f"Error creating invoice: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail="Failed to create invoice. Please try again or contact support.")


@app.post("/invoice/{invoice_id}/update-status")
async def update_invoice_status_endpoint(
    invoice_id: int,
    status: str = Form(...),
    request: Request = None,
    hr_email: str = Depends(require_hr)
):
    """Update invoice status"""
    try:
        success = update_invoice_status(invoice_id, status)
        if not success:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return {"message": "Invoice status updated", "status": status}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update invoice: {str(e)}")


@app.post("/delete-invoice/{invoice_id}")
async def delete_invoice_post_endpoint(
    invoice_id: int,
    hr_email: str = Depends(require_hr)
):
    """Delete an invoice (POST method for frontend compatibility)"""
    try:
        success = delete_invoice(invoice_id)
        if not success:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return {"success": True, "message": "Invoice deleted"}
    except Exception as e:
        logging.error(f"Error deleting invoice: {str(e)}", exc_info=True)
        return {"success": False, "message": f"Failed to delete invoice: {str(e)}"}


@app.delete("/invoice/{invoice_id}")
async def delete_invoice_endpoint(
    invoice_id: int,
    hr_email: str = Depends(require_hr)
):
    """Delete an invoice"""
    try:
        success = delete_invoice(invoice_id)
        if not success:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return {"message": "Invoice deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to delete invoice: {str(e)}")


@app.post("/invoice/{invoice_id}/update")
async def update_invoice_endpoint(
    invoice_id: int,
    request: Request,
    invoice_no: str = Form(...),
    invoice_date: str = Form(...),
    vendor_name: str = Form(...),
    vendor_gstin: Optional[str] = Form(None),
    vendor_address: Optional[str] = Form(None),
    customer_name: str = Form(...),
    customer_gstin: Optional[str] = Form(None),
    customer_address: Optional[str] = Form(None),
    description: str = Form(...),
    hsn_code: Optional[str] = Form(None),
    uom: Optional[str] = Form(None),
    quantity: str = Form(...),
    rate: str = Form(...),
    cgst: Optional[str] = Form("0"),
    sgst: Optional[str] = Form("0"),
    igst: Optional[str] = Form("0"),
    notes: Optional[str] = Form(None),
    invoice_status: Optional[str] = Form("draft"),
    hr_email: str = Depends(require_hr)
):
    """Update an existing invoice"""
    try:
        # Convert string form values to floats, handling empty strings
        def to_float(value: str, default: float = 0.0) -> float:
            if not value or value.strip() == "":
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        
        invoice_data = {
            "invoice_no": invoice_no,
            "date": invoice_date,
            "vendor_name": vendor_name,
            "vendor_gstin": vendor_gstin,
            "vendor_address": vendor_address,
            "customer_name": customer_name,
            "customer_gstin": customer_gstin,
            "customer_address": customer_address,
            "description": description,
            "hsn_code": hsn_code,
            "uom": uom,
            "quantity": to_float(quantity, 1.0),
            "rate": to_float(rate, 0.0),
            "cgst": to_float(cgst, 0.0),
            "sgst": to_float(sgst, 0.0),
            "igst": to_float(igst, 0.0),
            "notes": notes,
            "status": invoice_status or "draft"
        }
        
        success = update_invoice(invoice_id, invoice_data)
        if not success:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return RedirectResponse(url=f"/invoice/{invoice_id}", status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error updating invoice: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to update invoice: {str(e)}")


# =========================================================================
# GST BILL ENDPOINTS
# =========================================================================

@app.get("/gst-bills", response_class=HTMLResponse, summary="Display GST bills page")
async def get_gst_bills(request: Request, hr_email: str = Depends(require_hr)):
    """Display all GST bills with filtering and search"""
    bills = fetch_all_gst_bills(limit=100)
    
    # Calculate summary
    summary = get_gst_bill_summary()
    
    return templates.TemplateResponse("billing.html", {
        "request": request,
        "bills": bills,
        "summary": summary,
        "page": "gst_bills"
    })


@app.get("/gst-bill/{bill_id}", response_class=HTMLResponse)
async def get_gst_bill_detail(bill_id: int, request: Request, hr_email: str = Depends(require_hr)):
    """Get detailed view of a single GST bill"""
    bill = fetch_gst_bill_by_id(bill_id)
    
    if not bill:
        raise HTTPException(status_code=404, detail="GST bill not found")
    
    return templates.TemplateResponse("gst_bill_view.html", {
        "request": request,
        "bill": bill,
    })


@app.post("/gst-bill/create")
async def create_new_gst_bill(
    request: Request,
    bill_no: str = Form(...),
    bill_date: str = Form(...),
    vendor_name: str = Form(...),
    vendor_gstin: str = Form(...),
    amount: float = Form(...),
    supply_type: str = Form("intra"),
    cgst: Optional[float] = Form(0),
    sgst: Optional[float] = Form(0),
    igst: Optional[float] = Form(0),
    description: Optional[str] = Form(None),
    hr_email: str = Depends(require_hr)
):
    """Create a new GST bill"""
    try:
        bill_data = {
            "bill_no": bill_no,
            "date": bill_date,
            "vendor_name": vendor_name,
            "vendor_gstin": vendor_gstin,
            "amount": amount,
            "supply_type": supply_type,
            "cgst": cgst or 0,
            "sgst": sgst or 0,
            "igst": igst or 0,
            "description": description,
            "status": "received"
        }
        
        result = create_gst_bill(bill_data)
        return RedirectResponse(url=f"/gst-bill/{result['id']}", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create GST bill: {str(e)}")


@app.post("/gst-bill/{bill_id}/update-status")
async def update_gst_bill_status_endpoint(
    bill_id: int,
    status: str = Form(...),
    request: Request = None,
    hr_email: str = Depends(require_hr)
):
    """Update GST bill status"""
    try:
        success = update_gst_bill_status(bill_id, status)
        if not success:
            raise HTTPException(status_code=404, detail="GST bill not found")
        return {"message": "GST bill status updated", "status": status}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update GST bill: {str(e)}")


@app.delete("/gst-bill/{bill_id}")
async def delete_gst_bill_endpoint(
    bill_id: int,
    hr_email: str = Depends(require_hr)
):
    """Delete a GST bill"""
    try:
        success = delete_gst_bill(bill_id)
        if not success:
            raise HTTPException(status_code=404, detail="GST bill not found")
        return {"message": "GST bill deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to delete GST bill: {str(e)}")


# =========================================================================
# REPORTING ENDPOINTS
# =========================================================================

@app.get("/summary")
async def get_billing_summary(
    hr_email: str = Depends(require_hr)
):
    """Get billing summary statistics"""
    invoice_summary = get_invoice_summary()
    bill_summary = get_gst_bill_summary()
    
    return {
        "invoices": invoice_summary,
        "gst_bills": bill_summary,
        "total_revenue": (invoice_summary.get('total_amount', 0) or 0),
        "pending_invoices": invoice_summary.get('total_invoices', 0) - invoice_summary.get('paid_count', 0),
        "total_bills": bill_summary.get('total_bills', 0)
    }


# ===========================================================================
# REPORT BUILDER FUNCTION
# ===========================================================================

if __name__ == "__main__":  
    # Detect environment
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