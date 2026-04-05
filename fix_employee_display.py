"""
Fix HQ Employee Display - Comprehensive Solution
Ensures office_id is properly set and employees are fetched correctly
"""
import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from urllib.parse import urlparse

# Load environment variables
load_dotenv()

def parse_database_url(db_url):
    """Parse DATABASE_URL to connection parameters"""
    parsed = urlparse(db_url)
    return {
        'host': parsed.hostname,
        'port': parsed.port or 5432,
        'user': parsed.username,
        'password': parsed.password,
        'database': parsed.path.lstrip('/'),
    }

def fix_hq_employee_display():
    """Fix the HQ employee display issue"""
    try:
        # Get database URL
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            print("✗ ERROR: DATABASE_URL environment variable not set")
            return False
        
        # Parse connection parameters
        db_params = parse_database_url(db_url)
        print(f"Connecting to: {db_params['host']}:{db_params['port']}/{db_params['database']}\n")
        
        # Connect to database
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        print("=" * 80)
        print("FIX: HQ EMPLOYEE DISPLAY ISSUE")
        print("=" * 80)
        
        # Step 1: Ensure HQ employees have office_id = 1
        print("\n[STEP 1] Ensuring all HQ employees are in office_id = 1...")
        print("-" * 80)
        
        hq_emails = [
            "sugunazugopvt@gmail.com",
            "zugopvtnetwork@gmail.com",
            "nandhakumarzugopvt@gmail.com",
            "zugoprivatelimited.hr@gmail.com",
            "nanthuzugopvt@gmail.com",
            "arunzugopvt@gmail.com",
            "bharathzugopvt@gmail.com",
            "someshzugopvt@gmail.com",
            "sornakumarzugopvt@gmail.com",
            "logeshzugopvt@gmail.com",
            "afrinzugopvt@gmail.com",
            "sarathzugopvt@gmail.com",
            "ravizugopvt@gmail.com",
        ]
        
        fixed_count = 0
        for email in hq_emails:
            cursor.execute("""
                UPDATE employee_details 
                SET office_id = 1
                WHERE email = %s
            """, (email,))
            rows = cursor.rowcount
            if rows > 0:
                print(f"  ✓ Updated: {email}")
                fixed_count += 1
        
        conn.commit()
        print(f"\n✓ Fixed {fixed_count} HQ employees to office_id = 1")
        
        # Step 2: Verify HQ employees are correctly set
        print("\n[STEP 2] Verifying HQ employees...")
        print("-" * 80)
        
        cursor.execute("""
            SELECT name, email, office_id, total_working, total_leave
            FROM employee_details 
            WHERE office_id = 1
            ORDER BY name
        """)
        
        hq_employees = cursor.fetchall()
        print(f"Total HQ employees in office 1: {len(hq_employees)}\n")
        
        for emp in hq_employees:
            print(f"  • {emp['name']:30} ({emp['email']:35})")
            print(f"    → Office: {emp['office_id']}, Working: {emp['total_working']}, Leave: {emp['total_leave']}")
        
        # Step 3: Test the exact query used by the web interface
        print("\n[STEP 3] Testing Web Query...")
        print("-" * 80)
        
        # This is exactly what the web interface does
        office_id = 1
        hr_email = "zugopvtnetwork@gmail.com"
        
        print(f"\nQuery (from fetch_employees_by_office):")
        print(f"  SELECT * FROM employee_details")
        print(f"  WHERE office_id = {office_id} AND email != '{hr_email}'")
        
        cursor.execute("""
            SELECT id, name, email, office_id, total_working, total_leave, job_role, phone
            FROM employee_details 
            WHERE office_id = %s AND email != %s
            ORDER BY name
        """, (office_id, hr_email))
        
        result = cursor.fetchall()
        print(f"\nResult: {len(result)} employees\n")
        
        if len(result) == 0:
            print("✗ PROBLEM: Query returned 0 employees!")
            print("\nDiagnosing...")
            
            # Check how many are in office 1
            cursor.execute("SELECT COUNT(*) as cnt FROM employee_details WHERE office_id = 1")
            total_in_office_1 = cursor.fetchone()['cnt']
            print(f"  Total in office_id 1: {total_in_office_1}")
            
            # Check if HR_EMAIL is in office 1
            cursor.execute("""
                SELECT name FROM employee_details WHERE email = %s AND office_id = 1
            """, (hr_email,))
            hr_emp = cursor.fetchone()
            if hr_emp:
                print(f"  HR admin in office 1: {hr_emp['name']} (excluded from list)")
                actual_result = total_in_office_1 - 1
                print(f"  Expected employees: {actual_result}")
            
        else:
            for emp in result[:5]:
                print(f"  • {emp['name']:30} | Working: {emp['total_working']}, Leave: {emp['total_leave']}")
            if len(result) > 5:
                print(f"  ... and {len(result) - 5} more")
        
        # Step 4: Verify wpsstore employees are separate
        print("\n[STEP 4] Verifying wpsstore employees are in office 13...")
        print("-" * 80)
        
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM employee_details WHERE office_id = 13
        """)
        wps_count = cursor.fetchone()['cnt']
        print(f"✓ wpsstore employees in office 13: {wps_count}")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 80)
        print("✓ FIX COMPLETED")
        print("=" * 80)
        
        print("\nNEXT STEPS:")
        print("  1. Save these files to git:")
        print("     git add -A")
        print("     git commit -m 'Fix HQ employee display'")
        print("\n  2. Push to Render (auto-deploys):")
        print("     git push origin main")
        print("\n  3. After deployment, test in Render live:")
        print("     a) Login as: zugopvtnetwork@gmail.com / zugo@123")
        print("     b) Go to 'Employees' tab")
        print("     c) Should see ~11 HQ employees (excluding HR admin)")
        print("\n  4. If still not showing:")
        print("     - Check browser console (F12) for errors")
        print("     - Check Render logs: Dashboard → Logs")
        print("     - Clear browser cache and refresh")
        
        return True
        
    except psycopg2.Error as e:
        print(f"\n✗ Database Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    fix_hq_employee_display()
