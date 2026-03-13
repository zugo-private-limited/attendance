#!/usr/bin/env python3
"""
Fix total_working counts in LIVE Render database
Excludes Sundays and counts only weekdays with check-ins
"""

import psycopg2
import psycopg2.extras

# Render credentials
DB_HOST = "dpg-d5b0dv4hg0os73d60l4g-a.singapore-postgres.render.com"
DB_PORT = 5432
DB_USER = "zugoweb"
DB_PASSWORD = "BtGjE2SkIO5ISJgVtpyXXPR1RXBWKWVQ"
DB_NAME = "zugo_attendance_c3pn"

def fix_database():
    """Connect to Render and fix all total_working counts."""
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
        cursor.execute("SELECT email, name FROM employee_details ORDER BY name")
        employees = cursor.fetchall()
        print(f"✓ Found {len(employees)} employees")
        
        # Step 2: Fix each employee's total_working
        fixed_count = 0
        for emp in employees:
            email = emp['email']
            name = emp['name']
            
            # Get attendance records for this employee
            cursor.execute(
                """
                SELECT DISTINCT DATE(event_time AT TIME ZONE 'Asia/Kolkata') as work_date, 
                       COUNT(CASE WHEN action = 'check-in' THEN 1 END) as check_in_count
                FROM attendance
                WHERE user_email = %s
                GROUP BY DATE(event_time AT TIME ZONE 'Asia/Kolkata')
                """,
                (email,)
            )
            
            records = cursor.fetchall()
            
            # Count only weekdays (Mon-Sat) with at least one check-in
            working_days = 0
            sunday_days = 0
            for record in records:
                work_date = record['work_date']
                check_in_count = record['check_in_count']
                
                # Skip if no check-in
                if check_in_count == 0:
                    continue
                
                # Check if Sunday (weekday() returns 6 for Sunday)
                if work_date.weekday() == 6:
                    sunday_days += 1
                    continue
                
                working_days += 1
            
            # Update the employee record
            cursor.execute(
                "UPDATE employee_details SET total_working = %s WHERE email = %s",
                (working_days, email)
            )
            
            if sunday_days > 0:
                print(f"✓ {name:30} | Working Days: {working_days:2} | Sundays: {sunday_days} (excluded)")
            else:
                print(f"✓ {name:30} | Working Days: {working_days:2}")
            
            fixed_count += 1
            conn.commit()
        
        cursor.close()
        conn.close()
        
        print(f"\n{'='*70}")
        print(f"✓ SUCCESS! Fixed {fixed_count} employees")
        print(f"{'='*70}")
        print("\nChanges:")
        print("- All Sundays excluded from working days count")
        print("- Only weekdays (Mon-Sat) with check-ins counted")
        print("- Database synced with new report logic")
        print("\nYour live Render site is now updated!")
        
    except psycopg2.Error as err:
        print(f"\n✗ DATABASE ERROR: {err}")
        print("Please check your credentials and try again")
    except Exception as err:
        print(f"\n✗ ERROR: {err}")

if __name__ == "__main__":
    print("="*70)
    print("LIVE RENDER DATABASE - ATTENDANCE COUNT FIX")
    print("="*70)
    print("\nThis will fix total_working for all employees:")
    print("- Excludes Sundays from working days")
    print("- Only counts days with at least one check-in")
    print("- Updates LIVE production database\n")
    
    confirm = input("Continue? (yes/no): ").strip().lower()
    if confirm == 'yes':
        fix_database()
    else:
        print("Cancelled.")
