
import mysql.connector
import os
import config
from employees import users as static_users 

def initialize_database_schema():
    """Initializes the database schema for Attendance Only."""
    try:
        conn = mysql.connector.connect(
            host=config.DB_HOST, user=config.DB_USER, password=config.DB_PASSWORD, port=config.DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{config.DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.execute(f"USE `{config.DB_NAME}`")
        
        # 1. Attendance Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id BIGINT PRIMARY KEY AUTO_INCREMENT, 
                user_email VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
                action ENUM('check-in','check-out') NOT NULL, 
                event_time DATETIME NOT NULL,
                latitude DECIMAL(10,7) NULL, 
                longitude DECIMAL(10,7) NULL,
                location_text VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL, 
                INDEX idx_user_time (user_email, event_time)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

        # 2. Employee Details Table (Removed Salary/Bank/Task fields)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employee_details (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
                email VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci UNIQUE NOT NULL,
                password VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL, 
                photo VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'profile.jpg',
                job_role VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'Employee',
                phone VARCHAR(20),
                parent_phone VARCHAR(20),
                dob VARCHAR(50),
                gender VARCHAR(50),
                employee_number VARCHAR(50) UNIQUE,
                aadhar VARCHAR(50),
                joining_date VARCHAR(50),
                native VARCHAR(255),
                address TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                total_leave INT DEFAULT 0,
                total_working INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

        conn.commit()

        # Seed HR Account
        try:
            cursor2 = conn.cursor()
            cursor2.execute("SELECT 1 FROM employee_details WHERE email = %s LIMIT 1", (config.HR_EMAIL,))
            hr_row = cursor2.fetchone()
            if not hr_row:
                default_hr_password = os.getenv("HR_PASSWORD", "zugo@123")
                cursor2.execute(
                    "INSERT INTO employee_details (name, email, password, job_role) VALUES (%s, %s, %s, %s)",
                    ("HR", config.HR_EMAIL, default_hr_password, "HR Manager")
                )
                conn.commit()
                print(f"Inserted default HR account: {config.HR_EMAIL}")
            cursor2.close()
        except Exception as _e:
            print(f"Warning: could not ensure HR account exists: {_e}")

        # Seed Static Employees
        try:
            cursor3 = conn.cursor()
            for email, user_data in static_users.items():
                if email == config.HR_EMAIL: continue
                    
                cursor3.execute("SELECT email FROM employee_details WHERE email = %s", (email,))
                if cursor3.fetchone(): continue 
                
                # Extract data (Safe dict.get)
                name = user_data.get("name", "")
                password = user_data.get("password", "zugo@123")
                photo = user_data.get("photo", "profile.jpg")
                phone = user_data.get("phone")
                parent_phone = user_data.get("parent_phone")
                dob = user_data.get("dob")
                gender = user_data.get("gender")
                employee_number = user_data.get("employee_number")
                aadhar = user_data.get("aadhar")
                joining_date = user_data.get("joining_date")
                native = user_data.get("native")
                address = user_data.get("address")
                job_role = user_data.get("job_role", "Employee")
                
                cursor3.execute(
                    """INSERT INTO employee_details 
                       (name, email, password, photo, phone, parent_phone, dob, gender, 
                        employee_number, aadhar, joining_date, native, address, job_role)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (name, email, password, photo, phone, parent_phone, dob, gender,
                     employee_number, aadhar, joining_date, native, address, job_role)
                )
            conn.commit()
            cursor3.close()
            print("Employee data seeding complete.")
        except Exception as _e:
            print(f"Warning: could not seed employee data: {_e}")

        cursor.close()
        conn.close()
        print("Database schema initialization complete.")
    except mysql.connector.Error as err:
        print(f"Error during DB initialization: {err}")