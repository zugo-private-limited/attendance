"""
DATABASE MANAGER - CLEAR AND RESEED POSTGRESQL DATABASE
========================================================
This script provides options to:
1. Clear all data from the database
2. Reseed only employees (keep HR account)
3. Exit

WARNING: These actions are IRREVERSIBLE! Make sure you have a backup first!
"""

import psycopg2
import config

def clear_all_data():
    """Delete ALL data from all tables in the database"""
    try:
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
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        print("Make sure config.py has correct database credentials")

def reseed_employees():
    """Delete only employees (keep HR account), they will reseed on app restart"""
    try:
        conn = psycopg2.connect(
            host=config.DB_HOST,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            port=config.DB_PORT,
            database=config.DB_NAME
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
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        print("Make sure config.py has correct database credentials")

def show_menu():
    """Display menu and get user choice"""
    print("\n" + "=" * 70)
    print("DATABASE MANAGER")
    print("=" * 70)
    print()
    print("Choose an option:")
    print()
    print("  1️⃣  CLEAR ALL DATA (attendance, comments, AND employees)")
    print("       Use this when you want a complete fresh start")
    print()
    print("  2️⃣  RESEED EMPLOYEES ONLY (keep HR account)")
    print("       Use this to add new employees from employees.py")
    print()
    print("  3️⃣  EXIT")
    print()
    
    choice = input("Enter your choice (1, 2, or 3): ").strip()
    return choice

if __name__ == "__main__":
    while True:
        choice = show_menu()
        
        if choice == "1":
            response = input("\n⚠️  WARNING: This will DELETE ALL DATA! Are you sure? (type 'YES' to continue): ")
            if response.strip().upper() == "YES":
                clear_all_data()
            else:
                print("Cancelled.")
            
        elif choice == "2":
            response = input("\n⚠️  WARNING: This will DELETE EMPLOYEE DATA! Are you sure? (type 'YES' to continue): ")
            if response.strip().upper() == "YES":
                reseed_employees()
            else:
                print("Cancelled.")
                
        elif choice == "3":
            print("\nGoodbye! 👋")
            break
            
        else:
            print("\n❌ Invalid choice. Please enter 1, 2, or 3.")
        
        # Ask if user wants to do another operation
        again = input("\n\nDo you want to perform another operation? (yes/no): ").strip().lower()
        if again not in ["yes", "y"]:
            print("\nGoodbye! 👋")
            break
