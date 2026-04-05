"""
Debug HQ Employee Display Issue
Check session, office assignment, and database queries
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

def debug_hq_employees():
    """Debug why HQ employees are not showing"""
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
        print("DEBUG: HQ EMPLOYEE DISPLAY ISSUE")
        print("=" * 80)
        
        # Check 1: Offices table
        print("\n[CHECK 1] Offices Table")
        print("-" * 80)
        cursor.execute("SELECT * FROM offices")
        offices = cursor.fetchall()
        for office in offices:
            print(f"  ID: {office['id']:3} | Name: {office['office_name']:20} | Admin: {office['admin_email']}")
        
        # Check 2: HQ employees in database
        print("\n[CHECK 2] HQ Employees (office_id = 1)")
        print("-" * 80)
        cursor.execute("""
            SELECT id, name, email, office_id, total_working, total_leave, password
            FROM employee_details 
            WHERE office_id = 1
            ORDER BY name
        """)
        hq_emps = cursor.fetchall()
        print(f"Total HQ employees in office 1: {len(hq_emps)}")
        for emp in hq_emps:
            print(f"  • {emp['name']:30} ({emp['email']:35}) - Office: {emp['office_id']}, Work: {emp['total_working']}, Leave: {emp['total_leave']}")
        
        # Check 3: HR Admin account
        print("\n[CHECK 3] HR Admin Account (zugopvtnetwork@gmail.com)")
        print("-" * 80)
        cursor.execute("""
            SELECT id, name, email, office_id, total_working, total_leave, password 
            FROM employee_details 
            WHERE email = 'zugopvtnetwork@gmail.com'
        """)
        hr_admin = cursor.fetchone()
        if hr_admin:
            print(f"✓ Found: {hr_admin['name']}")
            print(f"  Email: {hr_admin['email']}")
            print(f"  Office ID: {hr_admin['office_id']}")
            print(f"  Working: {hr_admin['total_working']}, Leave: {hr_admin['total_leave']}")
            print(f"  Password: {hr_admin['password']}")
        else:
            print("✗ HR Admin account not found!")
        
        # Check 4: All employees count
        print("\n[CHECK 4] Employees by Office")
        print("-" * 80)
        cursor.execute("""
            SELECT office_id, COUNT(*) as count 
            FROM employee_details 
            GROUP BY office_id 
            ORDER BY office_id
        """)
        counts = cursor.fetchall()
        for row in counts:
            print(f"  Office {row['office_id']:2}: {row['count']:3} employees")
        
        # Check 5: Test query that web interface uses
        print("\n[CHECK 5] Testing Web Query (fetch_employees_by_office)")
        print("-" * 80)
        
        # This mimics what the web interface does
        office_id = 1
        hr_email = "zugopvtnetwork@gmail.com"
        
        print(f"Query: SELECT * FROM employee_details WHERE office_id = {office_id}")
        cursor.execute("""
            SELECT * FROM employee_details 
            WHERE office_id = %s
            ORDER BY name
        """, (office_id,))
        
        employees = cursor.fetchall()
        print(f"Result: {len(employees)} employees\n")
        
        for emp in employees[:5]:
            print(f"  • {emp['name']:30} ({emp['email']:35})")
        
        if len(employees) > 5:
            print(f"  ... and {len(employees) - 5} more")
        
        # After filtering HR_EMAIL
        print(f"\nAfter filtering HR_EMAIL ({hr_email}):")
        filtered = [e for e in employees if e.get("email") != hr_email]
        print(f"Result: {len(filtered)} employees")
        
        # Check 6: Potential issues
        print("\n[CHECK 6] Potential Issues")
        print("-" * 80)
        
        # Check for NULL office_id
        cursor.execute("""
            SELECT COUNT(*) as count FROM employee_details 
            WHERE office_id IS NULL
        """)
        null_office = cursor.fetchone()['count']
        if null_office > 0:
            print(f"⚠️  Warning: {null_office} employees have NULL office_id")
        else:
            print("✓ No employees with NULL office_id")
        
        # Check for employees with no name
        cursor.execute("""
            SELECT COUNT(*) as count FROM employee_details 
            WHERE name IS NULL OR name = ''
        """)
        no_name = cursor.fetchone()['count']
        if no_name > 0:
            print(f"⚠️  Warning: {no_name} employees have no name")
        else:
            print("✓ All employees have names")
        
        # Check for employees with no email
        cursor.execute("""
            SELECT COUNT(*) as count FROM employee_details 
            WHERE email IS NULL OR email = ''
        """)
        no_email = cursor.fetchone()['count']
        if no_email > 0:
            print(f"⚠️  Warning: {no_email} employees have no email")
        else:
            print("✓ All employees have emails")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 80)
        print("DEBUG SUMMARY")
        print("=" * 80)
        
        if len(hq_emps) == 0:
            print("\n✗ PROBLEM: No HQ employees found in office_id 1!")
            print("\nSOLUTION:")
            print("  1. Run: python restore_hq_employees.py")
            print("  2. Verify with: python debug_hq_employees.py")
        else:
            print(f"\n✓ Found {len(hq_emps)} HQ employees")
            print("\nIf they're not showing in web interface:")
            print("  1. Click 'Employees' tab in your Render app")
            print("  2. Check browser console for errors (F12)")
            print("  3. Try logging out and back in")
            print("  4. Check if office_id is being set in session")
        
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
    debug_hq_employees()
