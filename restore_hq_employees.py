"""
Restore HQ Employee Details with Working Days and Leave Data
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

# HQ Employees with their current working days and leave data
HQ_EMPLOYEES = {
    "afrinzugopvt@gmail.com": {
        "total_working": 9,
        "total_leave": 4
    },
    "arunzugopvt@gmail.com": {
        "total_working": 12,
        "total_leave": 2
    },
    "bharathzugopvt@gmail.com": {
        "total_working": 9,
        "total_leave": 5
    },
    "logeshzugopvt@gmail.com": {
        "total_working": 12,
        "total_leave": 3
    },
    "nandhakumarzugopvt@gmail.com": {
        "total_working": 11,
        "total_leave": 6
    },
    "nanthuzugopvt@gmail.com": {
        "total_working": 8,
        "total_leave": 3
    },
    "ravizugopvt@gmail.com": {
        "total_working": 12,
        "total_leave": 3
    },
    "sarathzugopvt@gmail.com": {
        "total_working": 11,
        "total_leave": 4
    },
    "zugoprivatelimited.hr@gmail.com": {
        "total_working": 13,
        "total_leave": 1
    },
    "someshzugopvt@gmail.com": {
        "total_working": 10,
        "total_leave": 3
    },
    "sornakumarzugopvt@gmail.com": {
        "total_working": 9,
        "total_leave": 3
    },
    "sugunazugopvt@gmail.com": {
        "total_working": 10,
        "total_leave": 2
    },
    "zugopvtnetwork@gmail.com": {  # HR Admin
        "total_working": 0,
        "total_leave": 0
    }
}

def restore_hq_employees():
    """Restore HQ employees with their working days and leave data"""
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
        print("RESTORE HQ EMPLOYEES WITH WORKING DAYS & LEAVE DATA")
        print("=" * 80)
        print()
        
        # Step 1: Update HQ employees with their data
        print("[STEP 1] Updating HQ employees...")
        print("-" * 80)
        
        updated = 0
        for email, data in HQ_EMPLOYEES.items():
            try:
                cursor.execute("""
                    SELECT id, name, email, office_id, total_working, total_leave 
                    FROM employee_details 
                    WHERE email = %s
                """, (email,))
                
                emp = cursor.fetchone()
                
                if emp:
                    cursor.execute("""
                        UPDATE employee_details 
                        SET office_id = 1, 
                            total_working = %s, 
                            total_leave = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE email = %s
                    """, (data['total_working'], data['total_leave'], email))
                    
                    print(f"  ✓ {emp['name']:30} - Working: {data['total_working']}, Leave: {data['total_leave']}")
                    updated += 1
                else:
                    print(f"  ✗ Employee not found: {email}")
                    
            except psycopg2.Error as e:
                print(f"  ✗ Error updating {email}: {e}")
        
        conn.commit()
        print(f"\n✓ Updated {updated} HQ employees")
        
        # Step 2: Verify HQ employees are in office_id 1
        print("\n[STEP 2] Verifying HQ employees...")
        print("-" * 80)
        
        cursor.execute("""
            SELECT id, name, email, office_id, total_working, total_leave
            FROM employee_details 
            WHERE office_id = 1
            ORDER BY name
        """)
        
        hq_employees = cursor.fetchall()
        
        if not hq_employees:
            print("✗ No HQ employees found in office_id 1!")
            cursor.close()
            conn.close()
            return False
        
        print(f"✓ Found {len(hq_employees)} HQ employees in office_id 1:\n")
        
        for emp in hq_employees:
            print(f"  • {emp['name']:30} ({emp['email']:35})")
            print(f"    → Working: {emp['total_working']}, Leave: {emp['total_leave']}")
        
        # Step 3: Check for upload issues
        print("\n[STEP 3] Checking for potential display issues...")
        print("-" * 80)
        
        # Check if required fields are populated
        cursor.execute("""
            SELECT COUNT(*) as count FROM employee_details 
            WHERE office_id = 1 AND (name = '' OR name IS NULL)
        """)
        
        missing_names = cursor.fetchone()['count']
        if missing_names > 0:
            print(f"⚠️  Warning: {missing_names} HQ employees missing names")
        else:
            print("✓ All HQ employees have names")
        
        cursor.execute("""
            SELECT COUNT(*) as count FROM employee_details 
            WHERE office_id = 1 AND (email = '' OR email IS NULL)
        """)
        
        missing_emails = cursor.fetchone()['count']
        if missing_emails > 0:
            print(f"⚠️  Warning: {missing_emails} HQ employees missing emails")
        else:
            print("✓ All HQ employees have emails")
        
        # Step 4: Show summary
        print("\n" + "=" * 80)
        print("✓ HQ EMPLOYEE RESTORATION COMPLETED")
        print("=" * 80)
        
        print(f"\n✓ Total HQ Employees: {len(hq_employees)}")
        print("✓ All employees moved to office_id 1 (HQ)")
        print("✓ Working days and leave data restored")
        print("\n📝 NEXT STEPS TO FIX WEB DISPLAY:")
        print("   1. Check that your web app is filtering by office_id correctly")
        print("   2. Verify HR_EMAIL is 'zugopvtnetwork@gmail.com' in config.py")
        print("   3. Check the database query in your employee routes")
        print("   4. Refresh the Render live website to see the updated data")
        
        cursor.close()
        conn.close()
        
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
    restore_hq_employees()
