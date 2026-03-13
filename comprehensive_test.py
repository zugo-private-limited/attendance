#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COMPREHENSIVE TEST & DATABASE MANAGEMENT SUITE
==============================================
Single unified script for:
- Testing all imports (including pytz, timezone support)
- Testing deployment configuration
- Testing database connection
- Managing database (clear/reseed)
- Executing SQL commands

Usage: python comprehensive_test.py
"""

import sys
import os
import psycopg2

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# ============================================================================
# PART 1: IMPORT TESTS
# ============================================================================

def test_imports():
    """Test if all required modules can be imported."""
    print("Testing imports...")
    try:
        import fastapi
        import uvicorn
        import psycopg2
        import jinja2
        import pytz
        from datetime import datetime, date, timedelta, timezone, time
        print("[OK] All imports successful")
        return True
    except ImportError as e:
        print(f"[FAIL] Import error: {e}")
        return False

def test_timezone_support():
    """Test timezone configuration and functions."""
    print("\nTesting timezone support...")
    try:
        import pytz
        from datetime import datetime
        
        # Test IST timezone
        IST = pytz.timezone('Asia/Kolkata')
        now_ist = datetime.now(IST)
        print(f"[OK] IST timezone working: {now_ist.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        # Test UTC timezone
        now_utc = datetime.now(pytz.UTC)
        print(f"[OK] UTC timezone working: {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        # Test timezone conversion
        time_diff = (now_ist.utcoffset() - now_utc.utcoffset()).total_seconds() / 3600
        print(f"[OK] Timezone offset: IST is UTC{time_diff:+.1f}")
        
        return True
    except Exception as e:
        print(f"[FAIL] Timezone error: {e}")
        return False

# ============================================================================
# PART 2: CONFIGURATION TESTS
# ============================================================================

def test_config(): 
    """Test configuration loading."""
    print("\nTesting configuration...")
    try:
        import config
        print(f"[OK] DB_HOST: {config.DB_HOST}")
        print(f"[OK] DB_PORT: {config.DB_PORT}")
        print(f"[OK] DB_NAME: {config.DB_NAME}")
        print(f"[OK] DB_USER: {config.DB_USER}")
        print(f"[OK] HR_EMAIL: {config.HR_EMAIL}")
        return True
    except Exception as e:
        print(f"[FAIL] Config error: {e}")
        return False

def test_database_connection():
    """Test database connection."""
    print("\nTesting database connection...")
    try:
        import config
        
        conn = psycopg2.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME,
            sslmode=config.DB_SSLMODE
        )
        conn.close()
        print("[OK] Database connection successful")
        return True
    except psycopg2.Error as e:
        print(f"[FAIL] Database connection failed: {e}")
        print("  Make sure PostgreSQL is running and credentials are correct in .env")
        return False
    except Exception as e:
        print(f"[FAIL] Unexpected error: {e}")
        return False

# ============================================================================
# PART 3: FILE TESTS
# ============================================================================

def test_static_files():
    """Test if static files directory exists."""
    print("\nTesting static files...")
    if os.path.exists("static"):
        print("[OK] Static directory exists")
        return True
    else:
        print("[FAIL] Static directory not found")
        return False

def test_templates():
    """Test if templates directory exists."""
    print("\nTesting templates...")
    if os.path.exists("templates"):
        print("[OK] Templates directory exists")
        return True
    else:
        print("[FAIL] Templates directory not found")
        return False

def test_env_file():
    """Check if .env file exists."""
    print("\nTesting environment file...")
    if os.path.exists(".env"):
        print("[OK] .env file exists")
        return True
    else:
        print("[WARN] .env file not found (copy .env.example to .env)")
        return False

# ============================================================================
# PART 4: DATABASE MANAGEMENT FUNCTIONS
# ============================================================================

def clear_all_data():
    """Delete ALL data from all tables in the database"""
    try:
        import config
        
        conn = psycopg2.connect(
            host=config.DB_HOST,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            port=config.DB_PORT,
            database=config.DB_NAME
        )
        cursor = conn.cursor()
        
        print("\n" + "=" * 70)
        print("CLEARING ALL DATA FROM DATABASE")
        print("=" * 70)
        print(f"Database: {config.DB_NAME}")
        print()
        
        # Delete from employee_comments first (has foreign key constraint)
        print("1️⃣  Clearing employee_comments table...")
        cursor.execute("TRUNCATE TABLE employee_comments CASCADE")
        print(f"   ✓ Deleted comment records")
        
        # Delete from attendance table
        print("2️⃣  Clearing attendance table...")
        cursor.execute("TRUNCATE TABLE attendance CASCADE")
        print(f"   ✓ Deleted attendance records")
        
        # Delete from employee_details table
        print("3️⃣  Clearing employee_details table...")
        cursor.execute("TRUNCATE TABLE employee_details CASCADE")
        print(f"   ✓ Deleted employee records")
        
        conn.commit()
        
        # Verify counts
        print()
        print("=" * 70)
        print("VERIFICATION")
        print("=" * 70)
        
        cursor.execute("SELECT COUNT(*) FROM attendance")
        attendance_count = cursor.fetchone()[0]
        print(f"Attendance records: {attendance_count}")
        
        cursor.execute("SELECT COUNT(*) FROM employee_details")
        employee_count = cursor.fetchone()[0]
        print(f"Employee records: {employee_count}")
        
        cursor.execute("SELECT COUNT(*) FROM employee_comments")
        comment_count = cursor.fetchone()[0]
        print(f"Comment records: {comment_count}")
        
        print()
        print("=" * 70)
        print("✅ DATABASE CLEARED SUCCESSFULLY!")
        print("=" * 70)
        print()
        print("📌 NEXT STEPS:")
        print("   1. Restart your application")
        print("   2. The app will auto-seed HR account + all employees from employees.py")
        print("   3. Users can then login normally")
        print()
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        print("Make sure config.py has correct database credentials")
        return False

def reseed_employees():
    """Delete only employees (keep HR account), they will reseed on app restart"""
    try:
        import config
        
        conn = psycopg2.connect(
            host=config.DB_HOST,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            port=config.DB_PORT,
            database=config.DB_NAME,
            sslmode=config.DB_SSLMODE
        )
        cursor = conn.cursor()
        
        print("\n" + "=" * 70)
        print("RESEEDING EMPLOYEES")
        print("=" * 70)
        print(f"Database: {config.DB_NAME}")
        print()
        
        # Delete all employees EXCEPT HR account
        print("🔄 Clearing employee records (keeping HR account)...")
        cursor.execute("DELETE FROM employee_details WHERE email != %s", (config.HR_EMAIL,))
        rows_deleted = cursor.rowcount
        conn.commit()
        
        print(f"   ✓ Deleted {rows_deleted} employee records")
        
        # Verify
        cursor.execute("SELECT COUNT(*) FROM employee_details")
        remaining_count = cursor.fetchone()[0]
        
        print()
        print("=" * 70)
        print("VERIFICATION")
        print("=" * 70)
        print(f"Employee records remaining: {remaining_count} (HR account only)")
        
        print()
        print("=" * 70)
        print("✅ EMPLOYEES CLEARED SUCCESSFULLY!")
        print("=" * 70)
        print()
        print("📌 NEXT STEPS:")
        print("   1. Restart your application")
        print("   2. The app will auto-seed all employees from employees.py")
        print("   3. HR account is preserved, users can then login normally")
        print()
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        print("Make sure config.py has correct database credentials")
        return False

def reset_database():
    """Drop the existing database and recreate it with fresh schema."""
    try:
        import config
        
        # Connect to default postgres database to drop the target database
        conn = psycopg2.connect(
            host=config.DB_HOST,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            port=config.DB_PORT,
            database="postgres",
            sslmode=config.DB_SSLMODE
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Drop database if exists
        print(f"\n⏳ Dropping database '{config.DB_NAME}'...")
        cursor.execute(f"DROP DATABASE IF EXISTS {config.DB_NAME}")
        print(f"✅ Database '{config.DB_NAME}' dropped successfully!")
        
        # Create new database
        print(f"⏳ Creating fresh database '{config.DB_NAME}'...")
        cursor.execute(f"CREATE DATABASE {config.DB_NAME}")
        print(f"✅ Database '{config.DB_NAME}' created successfully!")
        
        cursor.close()
        conn.close()
        
        print("\n✅ Database reset complete!")
        print("📝 Next step: Start the app server")
        print("   The app will automatically recreate the schema on startup")
        print()
        
        return True
        
    except psycopg2.Error as err:
        print(f"❌ Error: {err}")
        return False

# ============================================================================
# PART 5: SQL EXECUTION FUNCTIONS
# ============================================================================

def execute_sql_query(query, description=""):
    """Execute a raw SQL query"""
    try:
        import config
        
        conn = psycopg2.connect(
            host=config.DB_HOST,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            port=config.DB_PORT,
            database=config.DB_NAME,
            sslmode=config.DB_SSLMODE
        )
        cursor = conn.cursor()
        
        if description:
            print(f"\n📝 Executing: {description}")
        
        cursor.execute(query)
        conn.commit()
        
        # Get results if it's a SELECT query
        if query.strip().upper().startswith('SELECT'):
            results = cursor.fetchall()
            print(f"[OK] Query executed successfully. {len(results)} rows returned.")
            return results
        else:
            print(f"[OK] Query executed successfully.")
            return True
        
    except Exception as e:
        print(f"[FAIL] SQL Error: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def clear_database_sql():
    """Execute SQL commands to clear database"""
    try:
        import config
        
        conn = psycopg2.connect(
            host=config.DB_HOST,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            port=config.DB_PORT,
            database=config.DB_NAME,
            sslmode=config.DB_SSLMODE
        )
        cursor = conn.cursor()
        
        print("\n" + "=" * 70)
        print("EXECUTING SQL CLEAR COMMANDS")
        print("=" * 70)
        print()
        
        # SQL Commands from clear_database.sql
        sql_commands = [
            ("DELETE FROM employee_comments", "Clearing employee_comments table"),
            ("DELETE FROM attendance", "Clearing attendance table"),
            ("DELETE FROM employee_details", "Clearing employee_details table"),
            ("ALTER SEQUENCE employee_comments_id_seq RESTART WITH 1", "Resetting employee_comments ID sequence"),
            ("ALTER SEQUENCE attendance_id_seq RESTART WITH 1", "Resetting attendance ID sequence"),
            ("ALTER SEQUENCE employee_details_id_seq RESTART WITH 1", "Resetting employee_details ID sequence"),
        ]
        
        for idx, (sql, desc) in enumerate(sql_commands, 1):
            print(f"{idx}️⃣  {desc}...")
            try:
                cursor.execute(sql)
                print(f"   ✓ Success")
            except Exception as e:
                print(f"   ✗ Error: {e}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print()
        print("=" * 70)
        print("✅ SQL COMMANDS EXECUTED SUCCESSFULLY!")
        print("=" * 70)
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

# ============================================================================
# PART 6: MAIN MENU AND TEST SUITE
# ============================================================================

def run_all_tests():
    """Run all tests and return summary"""
    print("=" * 70)
    print("RUNNING ALL TESTS")
    print("=" * 70)
    
    results = []
    results.append(("Imports", test_imports()))
    results.append(("Timezone Support", test_timezone_support()))
    results.append(("Configuration", test_config()))
    results.append(("Database Connection", test_database_connection()))
    results.append(("Static Files", test_static_files()))
    results.append(("Templates", test_templates()))
    results.append(("Environment File", test_env_file()))
    
    print("\n" + "=" * 70)
    print("TEST RESULTS SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SUCCESS] All tests passed! Ready for deployment.")
        return True
    else:
        print("\n[ERROR] Some tests failed. Please fix issues before deploying.")
        return False

def show_main_menu():
    """Display main menu"""
    print("\n" + "=" * 70)
    print("COMPREHENSIVE TEST & DATABASE MANAGEMENT SUITE")
    print("=" * 70)
    print()
    print("Choose an option:")
    print()
    print("  1️⃣  RUN ALL TESTS")
    print("       Test imports, config, database, timezone, files")
    print()
    print("  2️⃣  CLEAR ALL DATA (Python method)")
    print("       Delete all attendance, comments, and employee data")
    print()
    print("  3️⃣  RESEED EMPLOYEES (keep HR account)")
    print("       Delete only employees, HR account remains")
    print()
    print("  4️⃣  RESET DATABASE (drop and recreate)")
    print("       Complete fresh database reset")
    print()
    print("  5️⃣  CLEAR DATABASE (SQL method)")
    print("       Execute SQL clear commands with sequence reset")
    print()
    print("  6️⃣  EXECUTE CUSTOM SQL QUERY")
    print("       Run your own SQL command")
    print()
    print("  7️⃣  EXIT")
    print()
    
    choice = input("Enter your choice (1-7): ").strip()
    return choice

def main():
    """Main program loop"""
    while True:
        choice = show_main_menu()
        
        if choice == "1":
            run_all_tests()
            
        elif choice == "2":
            response = input("\n⚠️  WARNING: This will DELETE ALL DATA! Are you sure? (type 'YES' to continue): ")
            if response.strip().upper() == "YES":
                clear_all_data()
            else:
                print("Cancelled.")
            
        elif choice == "3":
            response = input("\n⚠️  WARNING: This will DELETE EMPLOYEE DATA! Are you sure? (type 'YES' to continue): ")
            if response.strip().upper() == "YES":
                reseed_employees()
            else:
                print("Cancelled.")
        
        elif choice == "4":
            response = input("\n⚠️  WARNING: This will DELETE AND RECREATE DATABASE! Are you sure? (type 'YES' to continue): ")
            if response.strip().upper() == "YES":
                reset_database()
            else:
                print("Cancelled.")
        
        elif choice == "5":
            response = input("\n⚠️  WARNING: This will CLEAR and RESET SEQUENCES! Are you sure? (type 'YES' to continue): ")
            if response.strip().upper() == "YES":
                clear_database_sql()
            else:
                print("Cancelled.")
        
        elif choice == "6":
            print("\n" + "=" * 70)
            print("CUSTOM SQL QUERY EXECUTOR")
            print("=" * 70)
            print("\nExamples:")
            print("  SELECT COUNT(*) FROM attendance;")
            print("  SELECT email, total_working FROM employee_details;")
            print("  DELETE FROM attendance WHERE user_email='test@example.com';")
            print()
            query = input("Enter your SQL query: ").strip()
            if query:
                execute_sql_query(query, "Custom Query")
            else:
                print("No query entered.")
        
        elif choice == "7":
            print("\nGoodbye! 👋")
            break
            
        else:
            print("\n❌ Invalid choice. Please enter 1-7.")
        
        # Ask if user wants to do another operation
        again = input("\n\nDo you want to perform another operation? (yes/no): ").strip().lower()
        if again not in ["yes", "y"]:
            print("\nGoodbye! 👋")
            break
        
        
        
import psycopg2
import psycopg2.extras
from datetime import datetime
import pytz
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, DB_SSLMODE

IST = pytz.timezone('Asia/Kolkata')

def fix_attendance_counts():
    """Recalculate and fix total_working for all employees."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get all employees
        cursor.execute("SELECT email FROM employee_details")
        employees = cursor.fetchall()
        
        print(f"Found {len(employees)} employees to process...")
        
        for emp in employees:
            email = emp['email']
            
            # Get all attendance records for this employee
            cursor.execute(
                """
                SELECT DISTINCT DATE(event_time AT TIME ZONE 'Asia/Kolkata') as work_date, 
                       COUNT(CASE WHEN action = 'check-in' THEN 1 END) as check_in_count
                FROM attendance
                WHERE user_email = %s
                GROUP BY DATE(event_time AT TIME ZONE 'Asia/Kolkata')
                ORDER BY work_date DESC
                """,
                (email,)
            )
            
            records = cursor.fetchall()
            
            # Count only weekdays (Mon-Sat) with at least one check-in
            working_days = 0
            for record in records:
                work_date = record['work_date']
                check_in_count = record['check_in_count']
                
                # Skip if no check-in
                if check_in_count == 0:
                    continue
                
                # Skip if Sunday (weekday() returns 6 for Sunday)
                if work_date.weekday() == 6:
                    print(f"  {email}: Skipping Sunday {work_date} (Sunday work)")
                    continue
                
                working_days += 1
            
            # Update the employee record
            cursor.execute(
                "UPDATE employee_details SET total_working = %s WHERE email = %s",
                (working_days, email)
            )
            
            print(f"✓ {email}: Updated total_working to {working_days} days")
            conn.commit()
        
        cursor.close()
        conn.close()
        
        print("\n✓ Successfully fixed all attendance counts!")
        print("Note: Sundays are now excluded from working days count")
        print("      (even if employee has attendance on Sundays)")
        
    except psycopg2.Error as err:
        print(f"✗ Database error: {err}")
    except Exception as err:
        print(f"✗ Error: {err}")


if __name__ == "__main__":
    print("=" * 60)
    print("ATTENDANCE COUNT FIX SCRIPT")
    print("=" * 60)
    print("\nThis will recalculate total_working for all employees")
    print("- Excludes Sundays from working days")
    print("- Only counts days with at least one check-in\n")
    
    confirm = input("Continue? (yes/no): ").strip().lower()
    if confirm == 'yes':
        fix_attendance_counts()
    else:
        print("Cancelled.")
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
    