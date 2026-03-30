"""Employee management routes."""
import os
import uuid
import psycopg2
import psycopg2.extras

from fastapi import APIRouter, Request, Form, Depends, HTTPException, File, UploadFile, status
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

import config
from data import get_db_connection, fetch_employee_by_email, get_user_role, fetch_employees_by_office, get_office_by_id
from app.utils.timezone import IST, get_ist_date
from datetime import datetime, time
import pytz

router = APIRouter()

def _get_templates():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
    return Jinja2Templates(directory=TEMPLATES_DIR)

def _get_static_dir():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(BASE_DIR, "static")

@router.get("/employees", response_class=None, name="employees_page", summary="Display employees list")
async def employees_page(request: Request, db = Depends(get_db_connection)):
    """Display list of employees for current office."""
    from fastapi.responses import HTMLResponse
    templates = _get_templates()
    from employees import users as static_users
    
    user_email = request.session.get("user_email")
    office_id = request.session.get("office_id")
    user_role = request.session.get("user_role", "employee")
    
    if not user_email:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        
    is_hr = user_role in ["hq_admin", "office_admin"]
    
    all_employees = fetch_employees_by_office(db, office_id)
    all_employees = [emp for emp in all_employees if emp.get("email") != config.HR_EMAIL]
    
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

@router.get("/dashboard", response_class=None, name="dashboard_view", summary="Display employee dashboard")
async def dashboard_view(request: Request, db = Depends(get_db_connection)):
    """Render dashboard.html showing the employee's full profile."""
    from fastapi.responses import HTMLResponse
    templates = _get_templates()
    from app.utils.helpers import _build_user_from_static
    
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
        "request": request,
        "user": user,
        "is_hr": is_hr,
        "user_role": user_role,
        "user_email": user_email,
        "error": request.query_params.get("error"),
        "success": request.query_params.get("success")
    })

@router.get("/api/employee/{email}", summary="Get employee details by email")
async def get_employee_api(email: str, request: Request, db = Depends(get_db_connection)):
    """API endpoint to fetch employee details for editing."""
    user_email = request.session.get("user_email")
    if not user_email or user_email != config.HR_EMAIL:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    employee = fetch_employee_by_email(db, email)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    return employee

@router.get("/api/check-hr-access", summary="Check if user has HR access")
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

@router.post("/manage-employee", response_class=RedirectResponse, summary="Add or edit employee")
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
    
    if user_role not in ["hq_admin", "office_admin"]:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    
    try:
        cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        photo_filename = None
        if photo and photo.filename:
            allowed_extensions = {'jpg', 'jpeg', 'png', 'gif'}
            file_ext = photo.filename.rsplit('.', 1)[1].lower() if '.' in photo.filename else ''
            
            if file_ext not in allowed_extensions:
                return RedirectResponse(url="/hr-management?error=Invalid+photo+format", status_code=status.HTTP_303_SEE_OTHER)
            
            unique_id = str(uuid.uuid4())[:8]
            photo_filename = f"employee_{unique_id}_{name.replace(' ', '_')}.{file_ext}"
            photo_path = os.path.join(_get_static_dir(), photo_filename)
            
            try:
                contents = await photo.read()
                with open(photo_path, 'wb') as f:
                    f.write(contents)
            except Exception as e:
                print(f"Error saving photo: {e}")
                return RedirectResponse(url="/hr-management?error=Error+uploading+photo", status_code=status.HTTP_303_SEE_OTHER)
        
        if action == "add":
            cursor.execute("SELECT email FROM employee_details WHERE email = %s", (new_email,))
            if cursor.fetchone():
                cursor.close()
                return RedirectResponse(url="/hr-management?error=Email already exists", status_code=status.HTTP_303_SEE_OTHER)
            
            cursor.execute("SELECT name FROM employee_details WHERE LOWER(name) = LOWER(%s)", (name,))
            if cursor.fetchone():
                cursor.close()
                return RedirectResponse(url="/hr-management?error=Employee name already exists", status_code=status.HTTP_303_SEE_OTHER)
            
            final_photo = photo_filename if photo_filename else "profile.jpg"
            
            cursor.execute(
                """INSERT INTO employee_details 
                   (name, email, password, phone, parent_phone, employee_number, job_role, dob, gender, joining_date, native, address, aadhar, pan_card, bank_details, salary, photo, office_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (name, new_email, password, phone, parent_phone, employee_number, job_role, dob, gender, joining_date, native, address, aadhar, pan_card, bank_details, salary, final_photo, office_id)
            )
            db.commit()
            
        elif action == "edit":
            if new_email != email:
                cursor.execute("SELECT email FROM employee_details WHERE email = %s AND email != %s", (new_email, email))
                if cursor.fetchone():
                    cursor.close()
                    return RedirectResponse(url="/hr-management?error=Email already exists", status_code=status.HTTP_303_SEE_OTHER)
            
            cursor.execute("SELECT name FROM employee_details WHERE LOWER(name) = LOWER(%s) AND email != %s", (name, email))
            if cursor.fetchone():
                cursor.close()
                return RedirectResponse(url="/hr-management?error=Employee name already exists", status_code=status.HTTP_303_SEE_OTHER)
            
            if user_role == "office_admin":
                cursor.execute("SELECT office_id FROM employee_details WHERE email = %s", (email,))
                emp_office = cursor.fetchone()
                if not emp_office or emp_office.get('office_id') != office_id:
                    cursor.close()
                    return RedirectResponse(url="/hr-management?error=Cannot edit employees from other offices", status_code=status.HTTP_303_SEE_OTHER)
            
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

@router.post("/delete-employee", response_class=RedirectResponse, summary="Delete employee")
async def delete_employee(
    request: Request,
    email: str = Form(...),
    db = Depends(get_db_connection)
):
    """Delete an employee (HR and Office Admins)."""
    user_email = request.session.get("user_email")
    office_id = request.session.get("office_id", 1)
    user_role = request.session.get("user_role", "employee")
    
    if user_role not in ["hq_admin", "office_admin"]:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    if email == config.HR_EMAIL:
        return RedirectResponse(url="/hr-management?error=Cannot delete HR account", status_code=status.HTTP_303_SEE_OTHER)
    
    try:
        cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
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

@router.post("/api/hr/edit-employee", summary="Edit employee details")
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

@router.post("/api/hr/delete-employee", summary="Delete employee")
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
