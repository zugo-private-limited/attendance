import os
import uvicorn
import csv
import io
import uuid
import psycopg2
import psycopg2.extras
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta

from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

#  --- Local Imports ---
import config
from employees import users as static_users 
from data import (
    get_db_connection, fetch_attendance_for_today, fetch_all_employees, fetch_employee_by_email,
    submit_employee_comment, get_employee_comments, get_unread_comments_for_hr, 
    get_all_comments_for_hr, mark_comment_as_read, get_unread_comment_count
)
from services import calculate_working_days_and_leaves_for_employee, is_at_office
from schema import initialize_database_schema 

# ===========================================================================
# FastAPI APP INITIALIZATION
# ===========================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Application startup...") 
    initialize_database_schema()
    yield
    print("Application shutdown...")

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

@app.get("/", response_class=HTMLResponse, summary="Display login page")
async def login_page(request: Request): 
    """Serves the login page."""
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/", response_class=RedirectResponse)
async def handle_login(request: Request, email: str = Form(...), password: str = Form(...), db = Depends(get_db_connection)):
    """Processes login form submission, authenticates user, and sets session."""
    # Check if email is in allowed employees list
    if email not in static_users:
        return RedirectResponse(url="/?error=Access+Denied:+Not+an+authorized+employee", status_code=status.HTTP_303_SEE_OTHER)
    
    employee = fetch_employee_by_email(db, email)
    if employee and employee["password"] == password:
        request.session["user_email"] = email
        if email == config.HR_EMAIL:  
            return RedirectResponse(url="/hr-management", status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse(url="/report", status_code=status.HTTP_303_SEE_OTHER)
    
    return RedirectResponse(url="/?error=Invalid+Credentials", status_code=status.HTTP_303_SEE_OTHER)

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
async def report(request: Request, db = Depends(get_db_connection)):
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

    report_data, total_seconds = _build_report_for_user(db, user_email, days=30)
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
        "is_hr": is_hr
    })

@app.get("/download_report", summary="Download attendance report as CSV")
async def download_report(request: Request, db = Depends(get_db_connection)):
    """Return a CSV file of the user's attendance report (last 30 days)."""
    user_email = request.session.get("user_email")
    if not user_email:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    report_data, _ = _build_report_for_user(db, user_email, days=30)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Day", "Check In", "Check Out", "Total Hours"])
    for row in report_data:
        writer.writerow([row.get("day"), row.get("check_in"), row.get("check_out"), row.get("total_hours")])

    csv_content = output.getvalue()
    output.close()

    filename = f"attendance_{user_email.replace('@', '_at_')}.csv"
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

    is_hr = user_email == config.HR_EMAIL

    return templates.TemplateResponse("dashboard.html", {
        "request":  request,
        "user": user,
        "is_hr":  is_hr,
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
    timezone_offset: int = Form(default=0),
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

    # Get current UTC time and apply timezone offset (in minutes)
    now = datetime.utcnow()
    now = now + timedelta(minutes=timezone_offset)
    current_time = now.time()
    today = now.date()
    
    cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(
        """
        SELECT * FROM attendance 
        WHERE user_email = %s AND DATE(event_time) = %s
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
            (user_email, action, now, latitude, longitude, f"{latitude:.6f}, {longitude:.6f}", comment if comment else None)
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

        success_msg = f"Successfully+{action.replace('-', '+')}+at+{now.strftime('%I:%M+%p')}"
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
    """Display list of all employees."""
    user_email = request.session.get("user_email")
    if not user_email:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        
    is_hr = user_email == config.HR_EMAIL
    all_employees = fetch_all_employees(db)
    all_employees = [emp for emp in all_employees if emp.get("email") != config.HR_EMAIL]
    
    try:
        cursor = db.cursor()
        today = date.today()
        for emp in all_employees:
            email = emp.get("email")
            if email:  
                cursor.execute(
                    "SELECT 1 FROM attendance WHERE user_email = %s AND DATE(event_time) = %s LIMIT 1",
                    (email, today)
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
        "is_hr": is_hr
    })

@app.get("/hr-management", response_class=HTMLResponse, name="hr_management", summary="HR Management Dashboard")
async def hr_management(request: Request, db = Depends(get_db_connection)):
    """HR-only page showing all employees with details."""
    user_email = request.session.get("user_email")
    if not user_email:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    if user_email != config.HR_EMAIL:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    
    cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(
        "SELECT * FROM employee_details WHERE email != %s ORDER BY name ASC",      
        (config.HR_EMAIL,)
    )
    employees = cursor.fetchall()
    
    today = date.today()
    for emp in employees:
        email = emp.get("email")
        if email: 
            cursor.execute(
                "SELECT 1 FROM attendance WHERE user_email = %s AND DATE(event_time) = %s LIMIT 1",
                (email, today)
            )
            emp["present_today"] = bool(cursor.fetchone())
            
            # Fetch latest comment from employee
            cursor.execute(
                "SELECT comment FROM attendance WHERE user_email = %s AND comment IS NOT NULL ORDER BY event_time DESC LIMIT 1",
                (email,)
            )
            comment_record = cursor.fetchone()
            emp["last_comment"] = comment_record.get("comment") if comment_record else None
        
        static_data = static_users.get(emp['email'], {})
        emp['salary'] = static_data.get('salary', 'Not Set')
    
    cursor.close()
    
    return templates.TemplateResponse("hr_management.html", {
        "request": request,
        "employees": employees,
        "is_hr": True,
        "user_email": user_email
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
    """Check if logged-in user has HR access."""
    user_email = request.session.get("user_email")
    if not user_email:
        return {"is_hr": False, "message": "Not logged in"}
    
    is_hr = user_email == config.HR_EMAIL
    if is_hr:
        return {"is_hr": True, "email": user_email, "message": "HR access granted"}
    else:
        return {"is_hr": False, "email": user_email, "message": "Regular employee access only"}
        raise HTTPException(status_code=404, detail="Employee not found")
    
    return employee

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
    """Handle adding or editing employees (HR only)."""
    user_email = request.session.get("user_email")
    if not user_email or user_email != config.HR_EMAIL:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
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
                   (name, email, password, phone, parent_phone, employee_number, job_role, dob, gender, joining_date, native, address, aadhar, pan_card, bank_details, salary, photo)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (name, new_email, password, phone, parent_phone, employee_number, job_role, dob, gender, joining_date, native, address, aadhar, pan_card, bank_details, salary, final_photo)
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
    """Delete an employee (HR only)."""
    user_email = request.session.get("user_email")
    if not user_email or user_email != config.HR_EMAIL:  
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    if email == config.HR_EMAIL:
        return RedirectResponse(url="/hr-management?error=Cannot delete HR account", status_code=status.HTTP_303_SEE_OTHER)
    
    try:
        cursor = db.cursor()
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
    """Allow HR to manually add attendance records for employees."""
    user_email = request.session.get("user_email")
    if not user_email or user_email != config.HR_EMAIL:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    try:
        employee = fetch_employee_by_email(db, employee_email)
        if not employee:
            return RedirectResponse(
                url="/hr-management?error=Employee not found",
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

def _build_report_for_user(db, user_email, days:  int = 30):
    """Build report rows for the last `days` days for the given user."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(
        """
        SELECT event_time, action FROM attendance
        WHERE user_email = %s AND event_time BETWEEN %s AND %s
        ORDER BY event_time ASC
        """,
        (user_email, start_date, end_date)
    )
    rows = cursor.fetchall()
    cursor.close()

    by_date = {}
    for r in rows:
        d = r["event_time"].date().isoformat()
        by_date.setdefault(d, []).append(r)

    report = []
    total_working_seconds = 0
    for day, events in sorted(by_date.items()):
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

        report.append({
            "day": day,
            "check_in": check_in,
            "check_out": check_out,
            "total_hours": total_str
        })

    return report, total_working_seconds

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