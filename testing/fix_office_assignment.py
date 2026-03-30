"""
Script to fix incorrect office_id assignments and ensure proper office hierarchy.
Run this once to fix existing data issues.
"""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "attendance_db")
DB_USER = os.getenv("DB_USER", "zugo_attendance")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
HR_EMAIL = os.getenv("HR_EMAIL", "zugopvtnetwork@gmail.com")

def fix_office_assignments():
    """Fix office assignments in the database."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        
        print("\n" + "="*60)
        print("FIXING OFFICE ASSIGNMENTS")
        print("="*60)
        
        # Step 1: Ensure Main HQ office exists with id=1
        print("\n[1/3] Creating/Verifying Main HQ office (id=1)...")
        cursor.execute("SELECT id FROM offices WHERE id = 1")
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO offices (id, office_name, admin_email, office_latitude, office_longitude, office_radius_meters)
                VALUES (1, 'Main HQ', %s, 11.1205177, 77.3399277, 500)
            """, (HR_EMAIL,))
            conn.commit()
            print("✓ Created Main HQ office (id=1)")
        else:
            print("✓ Main HQ office already exists (id=1)")
        
        # Step 2: Fix HR admin office_id
        print("\n[2/3] Fixing HR admin office assignment...")
        cursor.execute(
            "UPDATE employee_details SET office_id = 1 WHERE email = %s",
            (HR_EMAIL,)
        )
        if cursor.rowcount > 0:
            conn.commit()
            print(f"✓ Fixed HR admin ({HR_EMAIL}) → office_id=1")
        else:
            print(f"⚠ HR admin not found: {HR_EMAIL}")
        
        # Step 3: Fix Office Admin office_ids to match offices table
        print("\n[3/3] Fixing Office Admin office assignments...")
        cursor.execute("""
            SELECT e.email, e.name, o.id, o.office_name
            FROM employee_details e
            JOIN offices o ON o.office_name = SUBSTRING(e.name, 9)
            WHERE e.job_role = 'Office Admin'
            AND e.office_id != o.id
        """)
        mismatched = cursor.fetchall()
        
        if mismatched:
            for email, name, correct_office_id, office_name in mismatched:
                cursor.execute(
                    "UPDATE employee_details SET office_id = %s WHERE email = %s",
                    (correct_office_id, email)
                )
                conn.commit()
                print(f"✓ Fixed {name} ({email}) → office_id={correct_office_id}")
        else:
            print("✓ All Office Admins have correct office assignments")
        
        # Summary
        print("\n" + "-"*60)
        cursor.execute("SELECT office_name, id FROM offices ORDER BY id")
        print("\nCurrent Offices:")
        for office_name, office_id in cursor.fetchall():
            cursor.execute(
                "SELECT COUNT(*) FROM employee_details WHERE office_id = %s AND job_role != 'HQ Admin'",
                (office_id,)
            )
            count = cursor.fetchone()[0]
            print(f"  • {office_name} (id={office_id}): {count} employees")
        
        print("\n✅ Office assignments fixed successfully!\n")
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    fix_office_assignments()
