"""
Migration script to reset all employee working days based on actual attendance check-ins
for the current salary period (21st to 20th).

Run this once after deploying the fix to sync all employees' working day counts.

Usage:
  - Local: python reset_working_days.py
  - Render: python reset_working_days.py <DATABASE_URL>
"""

import psycopg2
import psycopg2.extras
from datetime import datetime, date
import sys
import pytz
from urllib.parse import urlparse

IST = pytz.timezone('Asia/Kolkata')

def get_ist_date():
    """Get current date in IST."""
    return datetime.now(IST).date()

def get_attendance_period_dates(ref_date: date):
    """
    Calculates the start and end dates for the attendance period (21st to 20th).
    """
    ATTENDANCE_PERIOD_START_DAY = 21
    ATTENDANCE_PERIOD_END_DAY = 20
    
    if ref_date.day > ATTENDANCE_PERIOD_END_DAY:
        # Example: if today is Jan 25, period is Jan 21 to Feb 20
        start_month = ref_date.month
        start_year = ref_date.year
        end_month = (ref_date.month % 12) + 1
        end_year = ref_date.year if end_month != 1 else ref_date.year + 1
    else:
        # Example: if today is Jan 15, period is Dec 21 to Jan 20
        end_month = ref_date.month
        end_year = ref_date.year
        start_month = (ref_date.month - 2 + 12) % 12 + 1
        start_year = ref_date.year if start_month != 12 else ref_date.year - 1

    start_date = date(start_year, start_month, ATTENDANCE_PERIOD_START_DAY)
    end_date = date(end_year, end_month, ATTENDANCE_PERIOD_END_DAY)

    # Adjust start_date if it falls in the current month but should be previous
    if ref_date.day <= ATTENDANCE_PERIOD_END_DAY:
        if start_date.month == ref_date.month:
            start_date = date(start_date.year, start_date.month - 1, ATTENDANCE_PERIOD_START_DAY)
            if start_date.month == 0:  # Handle December case
                start_date = date(start_date.year - 1, 12, ATTENDANCE_PERIOD_START_DAY)

    return start_date, end_date

def fetch_attendance_for_period(user_email: str, start_date: date, end_date: date, db_connection):
    """Fetch attendance records for a user within a date range."""
    cursor = db_connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        SELECT id, user_email, action, event_time, latitude, longitude, location_text, comment
        FROM attendance
        WHERE user_email = %s
        AND DATE(event_time AT TIME ZONE 'Asia/Kolkata') >= %s
        AND DATE(event_time AT TIME ZONE 'Asia/Kolkata') <= %s
        ORDER BY event_time ASC
    """, (user_email, start_date, end_date))
    records = cursor.fetchall()
    cursor.close()
    return records

def reset_employee_working_days(database_url=None):
    """Recalculate and reset all employee working days based on attendance records."""
    try:
        # Connect to database
        if database_url:
            # Using Render database URL
            print(f"🌐 Connecting to Render database...")
            # Ensure sslmode is set in URL
            from urllib.parse import urlparse
            if "sslmode" not in database_url:
                connector = '&' if urlparse(database_url).query else '?'
                database_url = database_url + connector + 'sslmode=require'
            conn = psycopg2.connect(database_url)
        else:
            # Using local config
            import config
            print(f"💻 Connecting to local database...")
            conn = psycopg2.connect(
                host=config.DB_HOST,
                port=config.DB_PORT,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                database=config.DB_NAME,
                sslmode=config.DB_SSLMODE
            )
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        today = get_ist_date()
        start_period, end_period = get_attendance_period_dates(today)
        
        # Get HR email from config or use default
        try:
            import config
            hr_email = config.HR_EMAIL
        except:
            hr_email = "zugopvtnetwork@gmail.com"
        
        print(f"📅 Current Salary Period: {start_period} to {end_period}")
        print(f"📍 Today's Date (IST): {today}\n")
        
        # Fetch all employees except HR
        cursor.execute("SELECT email, name FROM employee_details WHERE email != %s ORDER BY name ASC", (hr_email,))
        employees = cursor.fetchall()
        
        print(f"🔄 Resetting working days for {len(employees)} employees...\n")
        
        reset_count = 0
        for emp in employees:
            email = emp["email"]
            name = emp["name"]
            
            # Get attendance records for current period
            attendance_records = fetch_attendance_for_period(email, start_period, end_period, conn)
            
            # Count unique check-in dates
            checked_in_dates = set()
            for record in attendance_records:
                if record["action"] == "check-in":
                    checked_in_dates.add(record["event_time"].date())
            
            total_working_days = len(checked_in_dates)
            
            # Update database
            cursor.execute(
                "UPDATE employee_details SET total_working = %s WHERE email = %s",
                (total_working_days, email)
            )
            
            reset_count += 1
            print(f"✓ {name:30} ({email:35}) → {total_working_days} days")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"\n✅ Successfully reset {reset_count} employees!")
        print("All working day counts have been synced to the current salary period.")
        
    except Exception as e:
        print(f"❌ Error resetting working days: {e}")
        raise

if __name__ == "__main__":
    # Check if DATABASE_URL is provided as argument
    if len(sys.argv) > 1:
        database_url = sys.argv[1]
        print(f"Using provided DATABASE_URL: {database_url[:50]}...\n")
        reset_employee_working_days(database_url)
    else:
        reset_employee_working_days()
