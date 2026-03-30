#!/usr/bin/env python3
"""
Fix total_working AND total_leave counts in LIVE Render database
- total_working: Weekdays with check-ins (Sundays excluded)
- total_leave: Weekdays without check-ins (Sundays excluded, up to TODAY)
"""

import psycopg2
import psycopg2.extras
from datetime import datetime, date, timedelta
import pytz

# Render credentials
DB_HOST = "dpg-d5b0dv4hg0os73d60l4g-a.singapore-postgres.render.com"
DB_PORT = 5432
DB_USER = "zugoweb"
DB_PASSWORD = "BtGjE2SkIO5ISJgVtpyXXPR1RXBWKWVQ"
DB_NAME = "zugo_attendance_c3pn"

IST = pytz.timezone('Asia/Kolkata')

def get_attendance_period_dates(ref_date, office_id=1):
    """
    Get the attendance period for HQ or branch office.
    - HQ (1): 21st to 20th of next month
    - Branch (>1): 1st to last day of month
    """
    ATTENDANCE_PERIOD_START_DAY = 21
    ATTENDANCE_PERIOD_END_DAY = 20
    
    # ===== MAIN HQ: 21st to 20th Period =====
    if office_id == 1:
        if ref_date.day > ATTENDANCE_PERIOD_END_DAY:  # e.g., if day > 20
            start_month = ref_date.month
            start_year = ref_date.year
            end_month = (ref_date.month % 12) + 1
            end_year = ref_date.year if end_month != 1 else ref_date.year + 1
        else:
            end_month = ref_date.month
            end_year = ref_date.year
            start_month = (ref_date.month - 2 + 12) % 12 + 1
            start_year = ref_date.year if start_month != 12 else ref_date.year - 1

        start_date = date(start_year, start_month, ATTENDANCE_PERIOD_START_DAY)
        end_date = date(end_year, end_month, ATTENDANCE_PERIOD_END_DAY)

        if ref_date.day <= ATTENDANCE_PERIOD_END_DAY:
            if start_date.month == ref_date.month:
                start_date = date(start_date.year, start_date.month - 1, ATTENDANCE_PERIOD_START_DAY)
                if start_date.month == 0:
                    start_date = date(start_date.year - 1, 12, ATTENDANCE_PERIOD_START_DAY)

        return start_date, end_date
    
    # ===== BRANCH OFFICES: Calendar Month Period =====
    else:
        start_date = date(ref_date.year, ref_date.month, 1)
        if ref_date.month == 12:
            end_date = date(ref_date.year, 12, 31)
        else:
            end_date = date(ref_date.year, ref_date.month + 1, 1) - timedelta(days=1)
        
        return start_date, end_date

def fix_database():
    """Connect to Render and fix total_working and total_leave counts."""
    try:
        print("Connecting to Render database...")
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            sslmode='require'
        )
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        print("✓ Connected successfully!")
        
        # Step 1: Get all employees
        print("\nFetching all employees...")
        cursor.execute("SELECT email, name, office_id FROM employee_details ORDER BY name")
        employees = cursor.fetchall()
        print(f"✓ Found {len(employees)} employees")
        
        # Get today's date
        today = datetime.now(IST).date()
        print(f"✓ Today's date: {today}")
        
        # Step 2: Fix each employee's total_working and total_leave
        fixed_count = 0
        for emp in employees:
            email = emp['email']
            name = emp['name']
            office_id = emp.get('office_id', 1)
            
            # Get attendance period for this employee
            start_period, end_period = get_attendance_period_dates(today, office_id)
            
            # Cap end_period at today (never count future dates)
            if end_period > today:
                end_period = today
            
            # Get attendance records for this employee
            cursor.execute(
                """
                SELECT DISTINCT DATE(event_time AT TIME ZONE 'Asia/Kolkata') as work_date, 
                       COUNT(CASE WHEN action = 'check-in' THEN 1 END) as check_in_count
                FROM attendance
                WHERE user_email = %s
                AND DATE(event_time AT TIME ZONE 'Asia/Kolkata') >= %s
                AND DATE(event_time AT TIME ZONE 'Asia/Kolkata') <= %s
                GROUP BY DATE(event_time AT TIME ZONE 'Asia/Kolkata')
                """,
                (email, start_period, end_period)
            )
            
            records = cursor.fetchall()
            
            # Build set of dates with check-ins within period
            checked_in_dates = set()
            sunday_count = 0
            for record in records:
                work_date = record['work_date']
                check_in_count = record['check_in_count']
                
                if check_in_count > 0:
                    # Check if Sunday
                    if work_date.weekday() == 6:
                        sunday_count += 1
                    else:
                        checked_in_dates.add(work_date)
            
            # Count working days (weekdays with check-in, excluding Sundays)
            working_days = len(checked_in_dates)
            
            # Count absences: weekdays WITHOUT check-in (up to today only)
            absence_count = 0
            current_date = start_period
            while current_date <= end_period:
                is_sunday = current_date.weekday() == 6
                has_check_in = current_date in checked_in_dates
                
                # Count as absence: weekday without check-in (not Sunday)
                if not is_sunday and not has_check_in:
                    absence_count += 1
                
                current_date += timedelta(days=1)
            
            # Update the employee record
            cursor.execute(
                """UPDATE employee_details 
                   SET total_working = %s, total_leave = %s 
                   WHERE email = %s""",
                (working_days, absence_count, email)
            )
            conn.commit()
            
            if sunday_count > 0:
                print(f"✓ {name:30} | Working: {working_days:2} | Absences: {absence_count:2} | Sundays: {sunday_count}")
            else:
                print(f"✓ {name:30} | Working: {working_days:2} | Absences: {absence_count:2}")
            
            fixed_count += 1
        
        cursor.close()
        conn.close()
        
        print(f"\n{'='*80}")
        print(f"✓ SUCCESS! Fixed {fixed_count} employees (total_working + total_leave)")
        print(f"{'='*80}")
        print("\nChanges Applied:")
        print("✓ total_working: Weekdays (Mon-Sat) with check-ins")
        print("✓ total_leave: Weekdays (Mon-Sat) without check-ins (only up to today)")
        print("✓ Sundays properly excluded from both counts")
        print(f"✓ Period: {start_period} to {today} (capped at today)")
        print("✓ HQ (21-20 period) and Branch (calendar) handled correctly")
        print("\n✅ Your live Render site is now fully updated!")
        
    except psycopg2.Error as err:
        print(f"\n✗ DATABASE ERROR: {err}")
        print("Please check your credentials and try again")
    except Exception as err:
        print(f"\n✗ ERROR: {err}")

if __name__ == "__main__":
    print("="*80)
    print("LIVE RENDER DATABASE - COMPLETE ATTENDANCE FIX")
    print("="*80)
    print("\nThis will fix BOTH for all employees:")
    print("✓ total_working: Weekdays (Mon-Sat) with check-ins")
    print("✓ total_leave: Weekdays (Mon-Sat) without check-ins (only up to today)")
    print("\nDetails:")
    print("- Sundays excluded from all counts (office closed)")
    print("- Absence only counts dates that have occurred (no future dates)")
    print("- Handles HQ (21-20 period) and Branch (calendar month) correctly")
    print("- Updates LIVE production database")
    print("\n" + "="*80 + "\n")
    
    confirm = input("⚠️  Continue and update LIVE database? (yes/no): ").strip().lower()
    if confirm == 'yes':
        fix_database()
    else:
        print("❌ Cancelled.")
