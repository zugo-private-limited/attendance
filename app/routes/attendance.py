"""Attendance and reporting routes."""
import io
import csv
from datetime import datetime, date, timedelta, time
import pytz
import psycopg2.extras

from fastapi import APIRouter, Request, Form, Depends, status
from fastapi.responses import RedirectResponse, Response, HTMLResponse
from fastapi.templating import Jinja2Templates

import config
from data import get_db_connection, fetch_attendance_for_today, fetch_employee_by_email, fetch_attendance_for_period
from services import calculate_working_days_and_leaves_for_employee, is_at_office
from app.utils.timezone import IST, get_ist_now, get_ist_date
from app.utils.helpers import _build_user_from_static, _build_report_for_user

router = APIRouter()

def _get_templates():
    import os
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
    return Jinja2Templates(directory=TEMPLATES_DIR)

@router.get("/report", response_class=HTMLResponse, name="report", summary="Display employee attendance")
async def report(request: Request, period: str = "30", db = Depends(get_db_connection)):
    """Shows the main dashboard for a logged-in employee."""
    templates = _get_templates()
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
    sorted_records = sorted(records, key=lambda x: x["event_time"], reverse=True)

    # Map period parameter to days
    period_map = {"30": 30, "180": 180, "365": 365}
    days = period_map.get(period, 30)
    
    report_data, total_seconds, leave_count, sunday_count = _build_report_for_user(db, user_email, days=days)
    total_hours = total_seconds / 3600 if total_seconds else 0

    is_hr = user_email == config.HR_EMAIL

    return templates.TemplateResponse("report.html", {
        "request": request,
        "user": user_data,
        "records": sorted_records,
        "report_data": report_data,
        "total_working_hours": f"{total_hours:.2f}",
        "error": request.query_params.get("error"),
        "success": request.query_params.get("success"),
        "is_hr": is_hr,
        "user_email": user_email,
        "period": period
    })

@router.get("/download_report", summary="Download attendance report as CSV")
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
        "Content-Disposition": f"attachment; filename={filename}"
    })

@router.post("/attendance", summary="Handle check-in/check-out actions")
async def handle_attendance(
    request: Request,
    action: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    comment: str = Form(None),
    timezone_offset: int = Form(default=330),
    db = Depends(get_db_connection)
):
    """
    Processes check-in and check-out requests with office-aware validation.
    
    Main HQ (office_id=1):
        ✅ Enforces location-based check-in
        ✅ Enforces time windows (morning/afternoon)
        ✅ Enforces checkout time restrictions
    
    Branch Offices (office_id > 1):
        ✅ No location validation
        ✅ No time restrictions
        ✅ Any time allowed
    """
    user_email = request.session.get("user_email")
    if not user_email:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    # Get office_id for this employee
    office_id = request.session.get("office_id", 1)
    
    # Location validation (Main HQ only)
    if office_id == 1:
        try:
            if not is_at_office(float(latitude), float(longitude), office_id, db):
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
    
    # Store as UTC for database
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
        # Check-in time validation (Main HQ only)
        if office_id == 1:
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
        # Check-out time validation (Main HQ only)
        if office_id == 1:
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
                url="/report?error=Already+checked+out+today",
                status_code=status.HTTP_303_SEE_OTHER
            )

    try:
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO attendance 
            (user_email, action, event_time, latitude, longitude, location_text, comment, office_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user_email, action, now_utc, latitude, longitude, f"{latitude:.6f}, {longitude:.6f}", comment if comment else None, office_id)
        )
        db.commit()
        cursor.close()

        if action == "check-in":
            working_days, _, _ = calculate_working_days_and_leaves_for_employee(user_email, today, office_id)
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

@router.get("/employee/{email}/attendance-report", response_class=HTMLResponse, summary="View employee attendance report")
async def view_employee_attendance_report(
    email: str,
    request: Request,
    period: str = "30",
    db = Depends(get_db_connection)
):
    """View attendance report for a specific employee (HR only)"""
    from fastapi import HTTPException
    templates = _get_templates()
    
    user_email = request.session.get("user_email")
    if not user_email or user_email != config.HR_EMAIL:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    employee = fetch_employee_by_email(db, email)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Map period parameter to days
    period_map = {"30": 30, "180": 180, "365": 365}
    days = period_map.get(period, 30)
    
    # Fetch attendance records
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    records = fetch_attendance_for_period(email, start_date, end_date)
    
    # Build report data
    report_data, total_seconds, leave_count, sunday_count = _build_report_for_user(db, email, days=days)
    total_hours = total_seconds / 3600 if total_seconds else 0
    
    # Enhance report_data with attendance IDs
    records_by_date = {}
    for r in records:
        event_time = r['event_time']
        if hasattr(event_time, 'date'):
            if event_time.tzinfo is None:
                event_time_ist = IST.localize(event_time)
            else:
                event_time_ist = event_time.astimezone(IST)
            record_date = event_time_ist.date()
        else:
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
    
    for day_record in report_data:
        day_str = day_record.get('day')
        if day_str and day_str in records_by_date:
            day_records = records_by_date[day_str]
            check_in_rec = next((r for r in day_records if r.get('action') == 'check-in'), None)
            check_out_rec = next((r for r in day_records if r.get('action') == 'check-out'), None)
            day_record['check_in_id'] = check_in_rec.get('id') if check_in_rec and 'id' in check_in_rec else None
            day_record['check_out_id'] = check_out_rec.get('id') if check_out_rec and 'id' in check_out_rec else None
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

@router.post("/attendance/{attendance_id}/delete", summary="Delete attendance record")
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
        cursor.execute("SELECT user_email, action FROM attendance WHERE id = %s", (attendance_id,))
        record = cursor.fetchone()
        
        if not record:
            cursor.close()
            return {"success": False, "message": "Attendance record not found"}
        
        user_email_emp, action = record
        
        cursor.execute("DELETE FROM attendance WHERE id = %s", (attendance_id,))
        
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
        import logging
        logging.error(f"Error deleting attendance record: {str(e)}", exc_info=True)
        return {"success": False, "message": f"Failed to delete attendance record: {str(e)}"}

@router.post("/attendance/{attendance_id}/update", summary="Update attendance record")
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
        
        cursor.execute(
            "UPDATE attendance SET event_time = %s, action = %s WHERE id = %s",
            (event_datetime, action, attendance_id)
        )
        
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
        import logging
        logging.error(f"Error updating attendance record: {str(e)}", exc_info=True)
        return RedirectResponse(
            url=f"/hr-management?error=Failed to update attendance: {str(e)}",
            status_code=status.HTTP_303_SEE_OTHER
        )
