"""
Script to sync employee credentials from employees.py to the database on Render.
Run this once to update all employee passwords in the database.
"""

import psycopg2
import psycopg2.extras
import config
from employees import users as static_users

def sync_employee_credentials():
    """Syncs email and password from employees.py to the database."""
    try:
        conn = psycopg2.connect(
            host=config.DB_HOST,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            port=config.DB_PORT,
            database=config.DB_NAME,
            sslmode=config.DB_SSLMODE
        )
        cursor = conn.cursor()
        
        print(f"Connecting to database at {config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}")
        print(f"Starting credential sync...\n")
        
        updated_count = 0
        for email, user_data in static_users.items():
            password = user_data.get("password", "")
            
            # Update existing employee or insert if not exists
            cursor.execute("""
                INSERT INTO employee_details (
                    name, email, password, job_role, phone, parent_phone, 
                    dob, gender, employee_number, aadhar, joining_date, 
                    native, address, pan_card, bank_details, salary, photo
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET
                    password = EXCLUDED.password,
                    name = EXCLUDED.name,
                    phone = EXCLUDED.phone,
                    parent_phone = EXCLUDED.parent_phone,
                    dob = EXCLUDED.dob,
                    gender = EXCLUDED.gender,
                    employee_number = EXCLUDED.employee_number,
                    aadhar = EXCLUDED.aadhar,
                    joining_date = EXCLUDED.joining_date,
                    native = EXCLUDED.native,
                    address = EXCLUDED.address,
                    pan_card = EXCLUDED.pan_card,
                    bank_details = EXCLUDED.bank_details,
                    salary = EXCLUDED.salary,
                    photo = EXCLUDED.photo,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                user_data.get("name", ""),
                email,
                password,
                user_data.get("job_role", ""),
                user_data.get("phone", ""),
                user_data.get("parent_phone", ""),
                user_data.get("dob", ""),
                user_data.get("gender", ""),
                user_data.get("employee_number", ""),
                user_data.get("aadhar", ""),
                user_data.get("joining_date", ""),
                user_data.get("native", ""),
                user_data.get("address", ""),
                user_data.get("pan_card", ""),
                user_data.get("bank_details", ""),
                user_data.get("salary", ""),
                user_data.get("photo", "profile.jpg")
            ))
            
            updated_count += 1
            print(f"✓ Synced: {email}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"\n✓ Successfully synced {updated_count} employees!")
        print("All employee credentials have been updated in the database.")
        
    except Exception as e:
        print(f"❌ Error syncing credentials: {e}")
        raise

if __name__ == "__main__":
    sync_employee_credentials()
