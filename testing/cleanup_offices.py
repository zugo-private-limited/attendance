"""
Clean up duplicate offices and ensure proper structure:
- Main account employees → office_id = 1
- Tiruppur branch → office_id = 2  
- CBE branch → office_id = 3
- CBE Main branch → office_id = 4
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

def cleanup_offices():
    """Clean up office structure."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
        )
        cursor = conn.cursor()
        
        print("\n" + "="*70)
        print("CLEANING UP OFFICE STRUCTURE")
        print("="*70)
        
        # Step 1: Delete duplicate Tiruppur (id=4)
        print("\n[1/4] Removing duplicate Tiruppur office...")
        cursor.execute("SELECT COUNT(*) FROM employee_details WHERE office_id = 4")
        count_4 = cursor.fetchone()[0]
        if count_4 > 0:
            # Move Admin - Tiruppur from office 4 to the actual Tiruppur office
            # First find which office is the real Tiruppur - it should be where zugoadmin1 manages
            cursor.execute("SELECT id FROM offices WHERE office_name = 'Tiruppur' AND id != 4 LIMIT 1")
            tiruppur_id = cursor.fetchone()
            if tiruppur_id:
                cursor.execute(
                    "UPDATE employee_details SET office_id = %s WHERE office_id = 4",
                    (tiruppur_id[0],)
                )
                conn.commit()
                print(f"✓ Moved {count_4} employee(s) from office_id 4 to office_id {tiruppur_id[0]}")
        
        cursor.execute("DELETE FROM offices WHERE id = 4")
        conn.commit()
        print("✓ Deleted duplicate Tiruppur office (id=4)")
        
        # Step 2: Rename office id=1 to "Main Account" if it contains main employees
        print("\n[2/4] Verifying Main Account office...")
        cursor.execute("""
            SELECT COUNT(*) FROM employee_details 
            WHERE office_id = 1 AND job_role NOT IN ('Office Admin', 'HQ Admin')
        """)
        main_account_count = cursor.fetchone()[0]
        
        if main_account_count > 0:
            cursor.execute("UPDATE offices SET office_name = 'Main Account' WHERE id = 1")
            conn.commit()
            print(f"✓ Office id=1 renamed to 'Main Account' ({main_account_count} employees)")
        else:
            print("⚠ Office id=1 has no regular employees")
        
        # Step 3: Verify HR admin is in office 1
        print("\n[3/4] Verifying HR admin location...")
        cursor.execute("SELECT office_id FROM employee_details WHERE email = %s", (HR_EMAIL,))
        hr_office = cursor.fetchone()
        if hr_office and hr_office[0] == 1:
            print(f"✓ HR admin is in office_id=1 (Main Account)")
        else:
            print(f"⚠ HR admin office_id: {hr_office[0] if hr_office else 'NOT FOUND'}")
        
        # Step 4: Summary
        print("\n[4/4] Summary of office structure:")
        cursor.execute("SELECT id, office_name FROM offices ORDER BY id")
        for office_id, office_name in cursor.fetchall():
            cursor.execute(
                "SELECT COUNT(*) FROM employee_details WHERE office_id = %s",
                (office_id,)
            )
            count = cursor.fetchone()[0]
            print(f"  Office {office_id}: '{office_name}' - {count} employees")
        
        print("\n✅ Office cleanup complete!\n")
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    cleanup_offices()
