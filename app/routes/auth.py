"""Authentication routes: login, signup, logout."""
from fastapi import APIRouter, Request, Form, Depends, status
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

import config
from data import get_db_connection, fetch_employee_by_email, get_user_role, get_user_office_id
from employees import users as static_users
from app.utils.helpers import _build_user_from_static

router = APIRouter()

def _get_templates():
    import os
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
    return Jinja2Templates(directory=TEMPLATES_DIR)

@router.get("/", response_class=HTMLResponse, summary="Display login page")
async def login_page(request: Request):
    """Serves the login page."""
    templates = _get_templates()
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/", response_class=RedirectResponse)
async def handle_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db = Depends(get_db_connection)
):
    """Processes login form submission, authenticates user, and sets session."""
    user_email = email.strip().lower()
    password = password.strip()

    # Check if email is in allowed employees list or is an office admin
    employee = fetch_employee_by_email(db, user_email)
    if not employee:
        return RedirectResponse(url="/?error=Access+Denied:+Not+an+authorized+employee", status_code=status.HTTP_303_SEE_OTHER)
    
    if employee["password"] != password:
        return RedirectResponse(url="/?error=Invalid+Credentials", status_code=status.HTTP_303_SEE_OTHER)
    
    request.session["user_email"] = user_email
    
    # Determine user role and set office_id
    user_role = get_user_role(db, user_email)
    request.session["user_role"] = user_role
    
    # Set office_id based on user assignment (ALWAYS set it, don't skip if None)
    office_id = get_user_office_id(db, user_email)
    if office_id is None and user_role == "office_admin":
        office_id = 2
    # Default to office 1 (HQ) if not found
    request.session["office_id"] = office_id if office_id else 1
    print(f"[Login] {email} → Role: {user_role}, Office: {request.session['office_id']}")
    
    # Redirect based on role
    if user_role == "hq_admin":
        return RedirectResponse(url="/hr-management", status_code=status.HTTP_303_SEE_OTHER)
    elif user_role == "office_admin":
        return RedirectResponse(url="/hr-management", status_code=status.HTTP_303_SEE_OTHER)
    else:
        return RedirectResponse(url="/report", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/signup", response_class=HTMLResponse, summary="Handle new user registration")
async def signup(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db = Depends(get_db_connection)
):
    """Registers a new employee."""
    templates = _get_templates()
    
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
    # Determine office_id based on email domain
    # HQ emails go to office 1, others based on their assignment
    office_id = 1  # Default to HQ office
    
    cursor.execute(
        """INSERT INTO employee_details 
           (name, email, password, photo, phone, parent_phone, dob, gender, 
            employee_number, aadhar, joining_date, native, address, job_role, pan_card, salary, bank_details, office_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (name, email, password, photo, phone, parent_phone, dob, gender,
         employee_number, aadhar, joining_date, native, address, job_role, pan_card, salary, bank_details, office_id)
    )
    db.commit()
    cursor.close()
    
    request.session["user_email"] = email
    return RedirectResponse(url="/report", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/logout", summary="Log user out", name="logout")
async def logout(request: Request):
    """Clears the user session."""
    request.session.clear()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
