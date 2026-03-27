# services.py
import math
import io
import csv
import config
import psycopg2
import psycopg2.extras
from math import radians, cos, sin, asin, sqrt
from typing import Optional, List, Dict
import pytz

import smtplib
from email.message import EmailMessage
from datetime import datetime, date, timedelta

from config import (
    OFFICE_LAT, OFFICE_LON, OFFICE_RADIUS_METERS,
    CHECKIN_MORNING_START, CHECKIN_MORNING_END, CHECKIN_AFTERNOON_START, CHECKIN_AFTERNOON_END,
    CHECKOUT_MIN_TIME,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, HR_EMAIL, MD_EMAIL,
    ATTENDANCE_PERIOD_START_DAY, ATTENDANCE_PERIOD_END_DAY
)
from data import (
    fetch_all_employees, update_employee_leave, fetch_attendance_for_period, fetch_monthly_attendance_all
)
import psycopg2

# ===========================================================================
# TIMEZONE CONFIGURATION
# ===========================================================================
IST = pytz.timezone('Asia/Kolkata')

# ===========================================================================
# SERVICE FUNCTIONS (Business Logic)
# ===========================================================================

def is_at_office(lat: float, lon: float, office_id: int = None, db = None) -> bool:
    """
    Check if a location is within the office radius.
    
    Args:
        lat: Employee's latitude
        lon: Employee's longitude
        office_id: The office to validate against (optional, defaults to Main HQ)
        db: Database connection to fetch office-specific coordinates
    
    Returns:
        bool: True if location is within office radius OR if office doesn't require location check
    """
    from data import get_office_by_id
    
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371000  # Earth radius in meters
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
        c = 2 * asin(sqrt(a))
        return R * c
    
    # If no office_id provided or is not Main HQ, branch offices don't need location check
    if office_id is None:
        office_id = 1  # Default to Main HQ
    
    # Main HQ (office_id = 1) requires location check
    if office_id == 1:
        return haversine(lat, lon, config.OFFICE_LAT, config.OFFICE_LON) <= config.OFFICE_RADIUS_METERS
    
    # Branch offices (office_id > 1) can check in from anywhere
    # They don't require location validation
    return True


def is_checkout_allowed(current_time: datetime.time, office_id: int = None) -> bool:
    """
    Checks if the current time is after the minimum allowed check-out time.
    
    Args:
        current_time: The current time to check
        office_id: The office to validate against (optional)
    
    Returns:
        bool: True if checkout is allowed, False if restricted to specific time
    """
    # If no office_id provided or is Main HQ, enforce checkout time
    if office_id is None:
        office_id = 1  # Default to Main HQ
    
    # Main HQ (office_id = 1) has time restrictions
    if office_id == 1:
        return current_time >= CHECKOUT_MIN_TIME
    
    # Branch offices (office_id > 1) can checkout anytime
    return True

def get_attendance_period_dates(ref_date: date, office_id: int = None) -> tuple[date, date]:
    """
    Calculates the start and end dates for the attendance period.
    
    For Main HQ (office_id=1):
        - Period: 21st of current/previous month to 20th of next/current month
        - Example: 21 Mar - 20 Apr (if ref_date is between 21/Mar and 20/Apr)
    
    For Branch Offices (office_id > 1):
        - Period: 1st to last day of the calendar month
        - Example: 1 Apr - 30 Apr
    
    Args:
        ref_date: Reference date to calculate period for
        office_id: The office type (1=HQ with 21-20 period, >1=Branch with calendar period)
    
    Returns:
        tuple: (start_date, end_date)
    """
    if office_id is None:
        office_id = 1  # Default to Main HQ (21-20 period)
    
    # ===== MAIN HQ: 21st to 20th Period =====
    if office_id == 1:
        if ref_date.day > ATTENDANCE_PERIOD_END_DAY:  # e.g., if day > 20
            # Example: if today is Oct 25, period is Oct 21 to Nov 20
            start_month = ref_date.month
            start_year = ref_date.year
            end_month = (ref_date.month % 12) + 1
            end_year = ref_date.year if end_month != 1 else ref_date.year + 1
        else:
            # Example: if today is Oct 15, period is Sep 21 to Oct 20
            end_month = ref_date.month
            end_year = ref_date.year
            start_month = (ref_date.month - 2 + 12) % 12 + 1
            start_year = ref_date.year if start_month != 12 else ref_date.year - 1

        start_date = date(start_year, start_month, ATTENDANCE_PERIOD_START_DAY)
        end_date = date(end_year, end_month, ATTENDANCE_PERIOD_END_DAY)

        # Adjust start_date if it falls in the current month but should be previous
        if ref_date.day <= ATTENDANCE_PERIOD_END_DAY:
            if start_date.month == ref_date.month:
                # This means start_date was calculated for current year/month but should be previous year/month
                start_date = date(start_date.year, start_date.month - 1, ATTENDANCE_PERIOD_START_DAY)
                if start_date.month == 0:  # Handle December case
                    start_date = date(start_date.year - 1, 12, ATTENDANCE_PERIOD_START_DAY)

        return start_date, end_date
    
    # ===== BRANCH OFFICES: Calendar Month Period =====
    else:
        # Start: 1st of the month
        start_date = date(ref_date.year, ref_date.month, 1)
        
        # End: Last day of the month
        if ref_date.month == 12:
            end_date = date(ref_date.year, 12, 31)
        else:
            end_date = date(ref_date.year, ref_date.month + 1, 1) - timedelta(days=1)
        
        return start_date, end_date


def calculate_working_days_and_leaves_for_employee(user_email: str, ref_date: date = None, office_id: int = None):
    """
    Calculates working days and leaves for a user based on the attendance period.
    - Main HQ (office_id=1): 21st to 20th period
    - Branch Offices (office_id>1): Calendar month (1st to last day)
    
    If ref_date is not provided, uses today's date to determine the current period.
    
    Args:
        user_email: Employee email address
        ref_date: Reference date for period calculation (defaults to today)
        office_id: Office ID to determine period type (defaults to 1/HQ)
    
    Returns:
        tuple: (total_working_days, start_period, end_period)
    """
    if ref_date is None:
        ref_date = datetime.now(IST).date()  # ✅ Uses IST

    if office_id is None:
        office_id = 1  # Default to Main HQ

    start_period, end_period = get_attendance_period_dates(ref_date, office_id)
    
    attendance_records = fetch_attendance_for_period(user_email, start_period, end_period)

    # Calculate actual working days based on unique check-ins within the period
    checked_in_dates = set()
    for record in attendance_records:
        if record["action"] == "check-in":
            checked_in_dates.add(record["event_time"].date())
    
    total_working_days = len(checked_in_dates)

    # Note: This function ALWAYS recalculates from attendance records
    # It ignores the stored total_working in DB and computes fresh from actual check-ins
    return total_working_days, start_period, end_period


def mark_leaves_for_absent_employees():
    """
    Marks employees as absent after 3 consecutive days without check-in.
    Runs daily.
    """
    import config
    from data import fetch_all_employees, update_employee_leave, fetch_attendance_for_period
    
    # Use IST date
    today = datetime.now(IST).date()
    
    # Create DB connection for fetch_all_employees
    conn = psycopg2.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME
    )
    
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT * FROM employee_details WHERE email != %s", (HR_EMAIL,))
        employees = cursor.fetchall()
        cursor.close()
        
        for employee in employees:
            user_email = employee["email"]
            if user_email == HR_EMAIL: # Skip HR account
                continue

            # Check last 3 days for any check-in
            three_days_ago = today - timedelta(days=3)
            last_three_days_attendance = fetch_attendance_for_period(user_email, three_days_ago, today)
            has_checked_in_last_three_days = any(r["action"] == "check-in" for r in last_three_days_attendance)

            if not has_checked_in_last_three_days:
                # Employee hasn't checked in for 3+ days - mark as absent
                current_leave = employee.get("total_leave", 0)
                update_employee_leave(user_email, current_leave + 1)
                print(f"⚠️ Marked ABSENT for {user_email} - No check-in for 3+ days")
            else:
                checked_in_today = any(
                    r["action"] == "check-in" and (
                        (r["event_time"].astimezone(IST).date() if getattr(r["event_time"], 'tzinfo', None) else r["event_time"].replace(tzinfo=pytz.UTC).astimezone(IST).date())
                    ) == today
                    for r in last_three_days_attendance
                )
                if checked_in_today:
                    print(f"✓ {user_email} checked in today - Status: Present")
                else:
                    print(f"→ {user_email} has no check-in today, but checked in within last 3 days")
    finally:
        conn.close()


def send_monthly_report_email_task() -> None:
    """
    Generate a CSV for the PREVIOUS calendar month's attendance and email it to HR and MD.
    This is a scheduled task that runs on a specific day (e.g., 20th) of the CURRENT month.
    """
    # 1. Calculate the year and month for the PREVIOUS calendar month
    today = datetime.now(IST).date()
    first_of_current_month = today.replace(day=1)
    last_day_of_previous_month = first_of_current_month - timedelta(days=1)
    year = last_day_of_previous_month.year
    month = last_day_of_previous_month.month

    print(f"Generating report for: {year}-{month:02d}")

    # 2. Fetch data using the calculated previous month
    rows = fetch_monthly_attendance_all(year, month)
    if not rows:
        print(f"No attendance data for {year}-{month:02d}. Skipping report.")
        return

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["user_email", "action", "event_time", "latitude", "longitude", "location_text"])
    for r in rows:
        writer.writerow([
            r.get("user_email"),
            r.get("action"),
            r.get("event_time").strftime("%Y-%m-%d %H:%M:%S") if r.get("event_time") else "",
            r.get("latitude"),
            r.get("longitude"),
            r.get("location_text"),
        ])
    csv_data = output.getvalue().encode("utf-8")

    msg = EmailMessage()
    msg["Subject"] = f"Monthly Attendance Report {year}-{month:02d}"
    from_email = SMTP_USER
    msg["From"] = from_email
    msg["To"] = HR_EMAIL
    msg["Cc"] = MD_EMAIL
    msg.set_content(f"Attached is the attendance report for {year}-{month:02d}.")
    msg.add_attachment(
        csv_data,
        maintype="text",
        subtype="csv",
        filename=f"attendance_{year}_{month:02d}.csv",
    )

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"Monthly report for {year}-{month:02d} emailed successfully.")
    except Exception as e:
        print(f"Failed to send monthly report email: {e}")

def reset_monthly_totals():
    import config
    conn = psycopg2.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME
    )
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE employee_details SET total_working = 0, total_leave = 0")
        conn.commit()
    finally:
        cursor.close()
        conn.close()


# ===========================================================================
# DATE PARSING & EVENT WISHES (BIRTHDAYS & ANNIVERSARIES)
# ===========================================================================

def parse_date(date_str: str) -> Optional[date]:
    """
    Parse date string in DD/MM/YYYY format to date object.
    
    Args:
        date_str: Date string in format "DD/MM/YYYY"
        
    Returns:
        date object or None if parsing fails
    """
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%d/%m/%Y").date()
    except (ValueError, TypeError):
        return None


def send_celebration_email(recipient_email: str, subject: str, message: str) -> bool:
    """
    Send celebration email (birthday/anniversary) to an employee.
    
    Args:
        recipient_email: Employee's email
        subject: Email subject
        message: Email body/message
        
    Returns:
        True if sent successfully, False otherwise
    """
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = recipient_email
        msg.set_content(message)
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        
        return True
    except Exception as e:
        print(f"Failed to send email to {recipient_email}: {e}")
        return False


def send_event_wishes() -> None:
    """
    Send birthday and work anniversary wishes to employees.
    Checks employee DOB and joining date against today's date.
    Runs daily as a scheduled task.
    """
    try:
        today = datetime.now(IST).date()
        
        # Get DB connection
        conn = psycopg2.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME
        )
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            "SELECT * FROM employee_details WHERE email != %s",
            (HR_EMAIL,)
        )
        employees = cursor.fetchall()
        cursor.close()
        conn.close()
        
        print(f"\n{'='*70}")
        print(f"🎉 Event Wishes Check - {today}")
        print(f"{'='*70}")
        
        birthday_count = 0
        anniversary_count = 0
        
        for emp in employees:
            try:
                emp_name = emp.get("name", "Unknown")
                emp_email = emp.get("email", "")
                
                # Parse DOB and Joining Date
                dob = parse_date(emp.get("dob"))
                joining_date = parse_date(emp.get("joining_date"))
                
                # 🎂 BIRTHDAY CHECK
                if dob and dob.day == today.day and dob.month == today.month:
                    subject = f"🎂 Happy Birthday, {emp_name}!"
                    message = (
                        f"Dear {emp_name},\n\n"
                        f"🎉 Wishing you a wonderful birthday!\n"
                        f"Hope your day is filled with joy and celebrations.\n\n"
                        f"Best wishes,\n"
                        f"Zugo Attendance Team"
                    )
                    if send_celebration_email(emp_email, subject, message):
                        print(f"✅ Birthday wish sent to {emp_name} ({emp_email})")
                        birthday_count += 1
                    else:
                        print(f"❌ Failed to send birthday wish to {emp_name}")
                
                # 🎉 WORK ANNIVERSARY CHECK
                if joining_date and joining_date.day == today.day and joining_date.month == today.month:
                    years = today.year - joining_date.year
                    subject = f"🎊 Happy Work Anniversary, {emp_name}!"
                    message = (
                        f"Dear {emp_name},\n\n"
                        f"🎉 Congratulations on completing {years} year(s) with Zugo!\n"
                        f"Thank you for your dedication and hard work.\n"
                        f"Here's to many more successful years together!\n\n"
                        f"Best wishes,\n"
                        f"Zugo Attendance Team"
                    )
                    if send_celebration_email(emp_email, subject, message):
                        print(f"✅ Anniversary wish sent to {emp_name} ({emp_email})")
                        anniversary_count += 1
                    else:
                        print(f"❌ Failed to send anniversary wish to {emp_name}")
                        
            except Exception as e:
                print(f"⚠️  Error processing {emp.get('name', 'Unknown')}: {e}")
        
        print(f"\n📊 Summary: {birthday_count} birthdays, {anniversary_count} anniversaries")
        print(f"{'='*70}\n")
        
    except Exception as e:
        print(f"❌ Error in send_event_wishes: {e}")