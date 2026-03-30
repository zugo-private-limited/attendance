"""
Final fix: Properly separate Main Account from Tiruppur branch office
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

def final_fix():
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
        )
        cursor = conn.cursor()
        
        print("\n" + "="*70)
        print("FINAL FIX: Separating Main Account from Branch Offices")
        print("="*70)
        
        # Step 1: Create Tiruppur branch office (if not exists)
        print("\n[1/3] Creating Tiruppur branch office...")
        cursor.execute("SELECT id FROM offices WHERE office_name = 'Tiruppur' AND id != 1")
        if not cursor.fetchone():
            # Find next available ID
            cursor.execute("SELECT MAX(id) FROM offices")
            max_id = cursor.fetchone()[0] or 0
            tiruppur_id = max_id + 1
            
            cursor.execute("""
                INSERT INTO offices (office_name, admin_email, office_latitude, office_longitude, office_radius_meters)
                VALUES (%s, %s, %s, %s, %s)
            """, ('Tiruppur', 'zugoadmin1@gmail.com', 11.2588, 77.3412, 500))
            conn.commit()
            
            cursor.execute("SELECT id FROM offices WHERE office_name = 'Tiruppur' AND admin_email = 'zugoadmin1@gmail.com' ORDER BY id DESC LIMIT 1")
            tiruppur_id = cursor.fetchone()[0]
            print(f"✓ Created Tiruppur branch office (id={tiruppur_id})")
        else:
            cursor.execute("SELECT id FROM offices WHERE office_name = 'Tiruppur' AND id != 1")
            tiruppur_id = cursor.fetchone()[0]
            print(f"✓ Tiruppur branch office already exists (id={tiruppur_id})")
        
        # Step 2: Move Admin - Tiruppur to Tiruppur office
        print("\n[2/3] Moving Admin - Tiruppur to Tiruppur office...")
        cursor.execute(
            "SELECT id FROM employee_details WHERE name = 'Admin - Tiruppur' AND office_id = 1"
        )
        admin_row = cursor.fetchone()
        if admin_row:
            admin_id = admin_row[0]
            cursor.execute(
                "UPDATE employee_details SET office_id = %s WHERE id = %s",
                (tiruppur_id, admin_id)
            )
            conn.commit()
            print(f"✓ Moved Admin - Tiruppur to office_id={tiruppur_id}")
        else:
            print("⚠ Admin - Tiruppur not found in Main Account")
        
        # Step 3: Summary
        print("\n[3/3] Final office structure:")
        print("-"*70)
        cursor.execute("SELECT id, office_name FROM offices ORDER BY id")
        for office_id, office_name in cursor.fetchall():
            cursor.execute(
                "SELECT COUNT(*) FROM employee_details WHERE office_id = %s",
                (office_id,)
            )
            count = cursor.fetchone()[0]
            cursor.execute(
                "SELECT GROUP_CONCAT(name, ', ') FROM employee_details WHERE office_id = %s LIMIT 5",
                (office_id,)
            )
            names_result = cursor.fetchone()
            names = names_result[0] if names_result[0] else "None"
            if count > 5:
                names += f"... and {count-5} more"
            print(f"\nOffice {office_id}: '{office_name}'")
            print(f"  Employees: {count}")
            print(f"  Sample: {names}")
        
        print("\n✅ Done! Main Account and Branch Offices are now properly separated.\n")
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    final_fix()
