"""
Fix the office structure properly:
- Office 1: Main Account (HQ)
- Office 2: Tiruppur branch
- Office 3: CBE branch
- Office 4: CBE Main branch
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

def fix_office_structure():
    """Properly organize offices."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
        )
        cursor = conn.cursor()
        
        print("\n" + "="*70)
        print("FIXING OFFICE STRUCTURE")
        print("="*70)
        
        # Step 1: Remove Admin - Tiruppur from Main Account (office_id=1)
        print("\n[1/3] Moving 'Admin - Tiruppur' from Main Account...")
        cursor.execute(
            "SELECT id FROM employee_details WHERE name = 'Admin - Tiruppur'"
        )
        admin_tiruppur = cursor.fetchone()
        if admin_tiruppur:
            admin_id = admin_tiruppur[0]
            # First, create proper Tiruppur office if it doesn't exist
            cursor.execute(
                "SELECT id FROM offices WHERE office_name = 'Tiruppur' AND id != 1"
            )
            tiruppur_office = cursor.fetchone()
            
            # Delete old incorrect Tiruppur entries and recreate
            cursor.execute("""
                DELETE FROM offices 
                WHERE office_name = 'Tiruppur' AND id != 1 
            """)
            conn.commit()
            
            # Create Tiruppur as office_id = 2
            cursor.execute("""
                INSERT INTO offices (id, office_name, admin_email, office_latitude, office_longitude, office_radius_meters)
                VALUES (2, 'Tiruppur', 'zugoadmin1@gmail.com', 11.2588, 77.3412, 500)
                ON CONFLICT (id) DO UPDATE 
                SET office_name = 'Tiruppur', admin_email = 'zugoadmin1@gmail.com'
            """)
            conn.commit()
            
            # Move Admin - Tiruppur to office_id = 2
            cursor.execute(
                "UPDATE employee_details SET office_id = 2 WHERE id = %s",
                (admin_id,)
            )
            conn.commit()
            print("✓ Moved 'Admin - Tiruppur' to office_id=2 (Tiruppur branch)")
        
        # Step 2: Fix other branch offices to have correct IDs
        print("\n[2/3] Organizing branch offices...")
        cursor.execute("""
            UPDATE offices 
            SET id = 3, office_name = 'CBE'
            WHERE office_name = 'CBE' AND id = 2
        """)
        if cursor.rowcount > 0:
            conn.commit()
            print("✓ CBE office moved to id=3")
            # Also move its employees
            cursor.execute("UPDATE employee_details SET office_id = 3 WHERE office_id = 2")
            conn.commit()
        
        cursor.execute("""
            UPDATE offices 
            SET id = 4, office_name = 'CBE Main'
            WHERE office_name = 'CBE Main' AND id = 3
        """)
        if cursor.rowcount > 0:
            conn.commit()
            print("✓ CBE Main office moved to id=4")
            # Also move its employees
            cursor.execute("UPDATE employee_details SET office_id = 4 WHERE office_id = 3")
            conn.commit()
        
        # Step 3: Summary
        print("\n[3/3] Final office structure:")
        cursor.execute("SELECT id, office_name FROM offices ORDER BY id")
        for office_id, office_name in cursor.fetchall():
            cursor.execute(
                """SELECT COUNT(*) FROM employee_details WHERE office_id = %s""",
                (office_id,)
            )
            count = cursor.fetchone()[0]
            cursor.execute(
                """SELECT GROUP_CONCAT(DISTINCT job_role, ', ') FROM employee_details WHERE office_id = %s""",
                (office_id,)
            )
            print(f"  Office {office_id}: '{office_name}' - {count} employees")
        
        print("\n✅ Office structure fixed!\n")
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    fix_office_structure()
