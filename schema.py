import psycopg2
import psycopg2.extras
import os
import config
from employees import users as static_users 

def initialize_database_schema():
    """Initializes the database schema for Attendance Only."""
    try:
        # Connect to postgres default database to create our database
        conn = psycopg2.connect(
            host=config.DB_HOST, 
            user=config.DB_USER, 
            password=config.DB_PASSWORD, 
            port=config.DB_PORT,
            database="postgres"
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{config.DB_NAME}'")
        db_exists = cursor.fetchone()
        
        if not db_exists:
            cursor.execute(f"CREATE DATABASE {config.DB_NAME}")
            print(f"Created database: {config.DB_NAME}")
        else:
            print(f"Database {config.DB_NAME} already exists")
        
        cursor.close()
        conn.close()
        
        # Now connect to the created database
        conn = psycopg2.connect(
            host=config.DB_HOST, 
            user=config.DB_USER, 
            password=config.DB_PASSWORD, 
            port=config.DB_PORT,
            database=config.DB_NAME
                   )
        cursor = conn.cursor()
        
        # 0. OFFICES TABLE - NEW (for multi-office support)
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS offices (
                    id SERIAL PRIMARY KEY,
                    office_name VARCHAR(255) NOT NULL,
                    admin_email VARCHAR(255) NOT NULL,
                    office_latitude NUMERIC(10,7) DEFAULT NULL,
                    office_longitude NUMERIC(10,7) DEFAULT NULL,
                    office_radius_meters INT DEFAULT 500,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("Created/verified offices table")
        except psycopg2.Error as e:
            if "already exists" not in str(e):
                print(f"Error creating offices table: {e}")
        
        # 1. Attendance Table - SEPARATE execute calls
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS attendance (
                    id BIGSERIAL PRIMARY KEY,
                    user_email VARCHAR(255) NOT NULL,
                    office_id INT DEFAULT 1,
                    action VARCHAR(50) NOT NULL,
                    event_time TIMESTAMP NOT NULL,
                    latitude NUMERIC(10,7) NULL,
                    longitude NUMERIC(10,7) NULL,
                    location_text VARCHAR(255) NULL,
                    comment TEXT NULL
                )
            """)
            print("Created/verified attendance table")
        except psycopg2.Error as e:
            if "already exists" not in str(e):
                print(f"Error creating attendance table: {e}")
        
        # Add comment column if it doesn't exist (for existing databases)
        try:
            cursor.execute("""
                ALTER TABLE attendance 
                ADD COLUMN IF NOT EXISTS comment TEXT NULL
            """)
            print("Verified comment column in attendance table")
        except psycopg2.Error as e:
            if "already exists" not in str(e):
                print(f"Info: {e}")
        
        # Add office_id column to attendance if it doesn't exist
        try:
            cursor.execute("""
                ALTER TABLE attendance 
                ADD COLUMN IF NOT EXISTS office_id INT DEFAULT 1
            """)
            print("Verified office_id column in attendance table")
        except psycopg2.Error as e:
            if "already exists" not in str(e):
                print(f"Info: {e}")
        
        # Create index separately
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_time 
                ON attendance (user_email, event_time)
            """)
            print("Created/verified attendance index")
        except psycopg2.Error as e:
            if "already exists" not in str(e):
                print(f"Error creating index: {e}")

        # 2. Employee Details Table
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS employee_details (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    office_id INT DEFAULT 1,
                    photo VARCHAR(255) DEFAULT 'profile.jpg',
                    job_role VARCHAR(255) DEFAULT 'Employee',
                    phone VARCHAR(20),
                    parent_phone VARCHAR(20),
                    dob VARCHAR(50),
                    gender VARCHAR(50),
                    employee_number VARCHAR(50) UNIQUE,
                    aadhar VARCHAR(50),
                    joining_date VARCHAR(50),
                    native VARCHAR(255),
                    address TEXT,
                    pan_card VARCHAR(50),
                    bank_details VARCHAR(255),
                    salary VARCHAR(50),
                    total_leave INT DEFAULT 0,
                    total_working INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("Created/verified employee_details table")
        except psycopg2.Error as e:
            if "already exists" not in str(e):
                print(f"Error creating employee_details table: {e}")

        # Add missing columns if they don't exist (for existing databases)
        try:
            cursor.execute("""
                ALTER TABLE employee_details 
                ADD COLUMN IF NOT EXISTS pan_card VARCHAR(50)
            """)
            print("Verified pan_card column in employee_details table")
        except psycopg2.Error as e:
            if "already exists" not in str(e):
                print(f"Info: {e}")

        try:
            cursor.execute("""
                ALTER TABLE employee_details 
                ADD COLUMN IF NOT EXISTS bank_details VARCHAR(255)
            """)
            print("Verified bank_details column in employee_details table")
        except psycopg2.Error as e:
            if "already exists" not in str(e):
                print(f"Info: {e}")

        try:
            cursor.execute("""
                ALTER TABLE employee_details 
                ADD COLUMN IF NOT EXISTS salary VARCHAR(50)
            """)
            print("Verified salary column in employee_details table")
        except psycopg2.Error as e:
            if "already exists" not in str(e):
                print(f"Info: {e}")

        # Add office_id column for multi-office support
        try:
            cursor.execute("""
                ALTER TABLE employee_details 
                ADD COLUMN IF NOT EXISTS office_id INT DEFAULT 1
            """)
            print("Verified office_id column in employee_details table")
        except psycopg2.Error as e:
            if "already exists" not in str(e):
                print(f"Info: {e}")

        # 3. Employee Comments/Messages Table (for employee-to-HR communication)
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS employee_comments (
                    id SERIAL PRIMARY KEY,
                    employee_email VARCHAR(255) NOT NULL,
                    comment_text TEXT NOT NULL,
                    attendance_date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_read BOOLEAN DEFAULT FALSE,
                    read_by_hr_at TIMESTAMP NULL,
                    FOREIGN KEY (employee_email) REFERENCES employee_details(email) ON DELETE CASCADE
                )
            """)
            print("Created/verified employee_comments table")
        except psycopg2.Error as e:
            if "already exists" not in str(e):
                print(f"Error creating employee_comments table: {e}")

        # Create index on employee_comments
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_comments_employee_date 
                ON employee_comments (employee_email, attendance_date)
            """)
            print("Created/verified comments index")
        except psycopg2.Error as e:
            if "already exists" not in str(e):
                print(f"Error creating comments index: {e}")

        conn.commit()

        # Seed Offices - Create Main/HQ office first with id=1
        hq_office_id = 1
        try:
            cursor_offices = conn.cursor()
            
            # Ensure Main HQ office exists with id=1
            cursor_offices.execute(
                "SELECT id FROM offices WHERE id = 1 LIMIT 1"
            )
            hq_row = cursor_offices.fetchone()
            if not hq_row:
                cursor_offices.execute(
                    """INSERT INTO offices (id, office_name, admin_email, office_latitude, office_longitude, office_radius_meters)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (1, "Main HQ", config.HR_EMAIL, config.OFFICE_LAT, config.OFFICE_LON, 500)
                )
                conn.commit()
                print(f"Inserted Main HQ office with id=1")
            else:
                print(f"✓ Main HQ office already exists with id=1")
            
            # Now seed custom offices (they will get auto-incremented IDs starting from 2)
            offices_data = config.OFFICES
            for office_info in offices_data:
                cursor_offices.execute(
                    "SELECT 1 FROM offices WHERE office_name = %s LIMIT 1",
                    (office_info["name"],)
                )
                if not cursor_offices.fetchone():
                    cursor_offices.execute(
                        """INSERT INTO offices (office_name, admin_email, office_latitude, office_longitude, office_radius_meters)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (office_info["name"], office_info["admin_email"], 
                         office_info.get("lat"), office_info.get("lon"), 
                         office_info.get("radius", 500))
                    )
                    conn.commit()
                    print(f"Inserted office: {office_info['name']}")
            
            cursor_offices.close()
        except Exception as _e:
            print(f"Info: Office seeding: {_e}")

        # Seed HR Account (HQ Admin - assign to Main HQ office id=1)
        try:
            cursor2 = conn.cursor()
            cursor2.execute("SELECT 1 FROM employee_details WHERE email = %s LIMIT 1", (config.HR_EMAIL,))
            hr_row = cursor2.fetchone()
            if not hr_row:
                default_hr_password = os.getenv("HR_PASSWORD", "zugo@123")
                cursor2.execute(
                    "INSERT INTO employee_details (name, email, password, job_role, office_id) VALUES (%s, %s, %s, %s, %s)",
                    ("HR", config.HR_EMAIL, default_hr_password, "HQ Admin", hq_office_id)
                )
                conn.commit()
                print(f"Inserted default HR account: {config.HR_EMAIL} with office_id={hq_office_id}")
            else:
                # Update existing HR account to ensure office_id=1 instead of NULL
                cursor2.execute(
                    "UPDATE employee_details SET office_id = %s WHERE email = %s",
                    (hq_office_id, config.HR_EMAIL)
                )
                if cursor2.rowcount > 0:
                    conn.commit()
                    print(f"✓ Updated HR account office_id to {hq_office_id}: {config.HR_EMAIL}")
                else:
                    print(f"✓ HR account already exists: {config.HR_EMAIL}")
            cursor2.close()
        except psycopg2.IntegrityError as _e:
            conn.rollback()
            print(f"✓ HR account already exists (duplicate): {config.HR_EMAIL}")
            cursor2.close()
        except Exception as _e:
            print(f"Warning: could not ensure HR account exists: {_e}")

        # Seed Office Admin Accounts - Use actual office IDs from offices table
        try:
            cursor_admins = conn.cursor()
            offices_data = config.OFFICES
            
            for office_info in offices_data:
                admin_email = office_info["admin_email"]
                office_name = office_info["name"]
                
                # Get the actual office_id from the offices table
                cursor_admins.execute(
                    "SELECT id FROM offices WHERE office_name = %s LIMIT 1",
                    (office_name,)
                )
                office_row = cursor_admins.fetchone()
                if not office_row:
                    print(f"Warning: Office '{office_name}' not found in offices table, skipping admin creation")
                    continue
                
                office_id = office_row[0]
                
                cursor_admins.execute(
                    "SELECT 1 FROM employee_details WHERE email = %s LIMIT 1",
                    (admin_email,)
                )
                if not cursor_admins.fetchone():
                    default_admin_password = os.getenv("ADMIN_PASSWORD", "admin@123")
                    cursor_admins.execute(
                        """INSERT INTO employee_details (name, email, password, job_role, office_id)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (f"Admin - {office_name}", admin_email, default_admin_password, "Office Admin", office_id)
                    )
                    conn.commit()
                    print(f"Inserted office admin: {admin_email} for {office_name} (office_id={office_id})")
                else:
                    # Update existing admin to ensure office_id is correct
                    cursor_admins.execute(
                        "UPDATE employee_details SET office_id = %s WHERE email = %s AND job_role = 'Office Admin'",
                        (office_id, admin_email)
                    )
                    if cursor_admins.rowcount > 0:
                        conn.commit()
                        print(f"✓ Updated office admin office_id to {office_id}: {admin_email}")
            
            cursor_admins.close()
        except Exception as _e:
            print(f"Info: Office admin seeding: {_e}")

        # Seed Static Employees
        try:
            cursor3 = conn.cursor()
            for email, user_data in static_users.items():
                if email == config.HR_EMAIL: 
                    continue
                    
                cursor3.execute("SELECT email FROM employee_details WHERE email = %s", (email,))
                if cursor3.fetchone(): 
                    continue 
                
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
                office_id = user_data.get("office_id", 1)  # Default to office 1
                
                try:
                    cursor3.execute(
                        """INSERT INTO employee_details 
                           (name, email, password, office_id, photo, phone, parent_phone, dob, gender, 
                            employee_number, aadhar, joining_date, native, address, job_role, salary, bank_details, pan_card)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (name, email, password, office_id, photo, phone, parent_phone, dob, gender,
                         employee_number, aadhar, joining_date, native, address, job_role,
                         user_data.get("salary"), user_data.get("bank_details"), user_data.get("pan_card"))
                    )
                    conn.commit()
                except psycopg2.IntegrityError as ie:
                    conn.rollback()
                    # Check if it's a duplicate email or employee_number
                    if "email" in str(ie):
                        pass  # Email already exists, skip
                    elif "employee_number" in str(ie):
                        # Update existing employee if only employee_number conflicts
                        pass  # Skip this one
                    else:
                        print(f"  Warning: Could not insert {email}: {ie}")
            cursor3.close()
            print("✓ Employee data seeding complete.")
        except Exception as _e:
            print(f"Warning: could not seed employee data: {_e}")

        cursor.close()
        conn.close()
        print("Database schema initialization complete.")
        
    except psycopg2.Error as err:
        print(f"Error during DB initialization: {err}")