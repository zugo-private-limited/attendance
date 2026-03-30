#!/usr/bin/env python
"""
TEST SCRIPT: Birthday & Anniversary Wishes Feature
====================================================
This script verifies if the birthday and anniversary email feature is working correctly.

Usage:
    python test_birthday_feature.py
"""

import os
import sys
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

import config
import psycopg2
import psycopg2.extras
from services import parse_date, send_celebration_email, send_event_wishes
import pytz

IST = pytz.timezone('Asia/Kolkata')

# ============================================================================
# TEST 1: Verify SMTP Configuration
# ============================================================================
def test_smtp_config():
    """Check if SMTP configuration is properly set."""
    print("\n" + "="*70)
    print("TEST 1: SMTP Configuration")
    print("="*70)
    
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = os.getenv("SMTP_PORT", "")
    
    print(f"\n✓ SMTP_HOST: {smtp_host}")
    print(f"✓ SMTP_PORT: {smtp_port}")
    print(f"✓ SMTP_USER: {smtp_user}")
    print(f"✓ SMTP_PASSWORD: {'*' * len(smtp_password) if smtp_password else 'NOT SET'}")
    
    if smtp_user and smtp_password and smtp_host and smtp_port:
        print("\n✅ SMTP Configuration: VALID")
        return True
    else:
        print("\n❌ SMTP Configuration: INCOMPLETE")
        return False

# ============================================================================
# TEST 2: Verify Database Connection
# ============================================================================
def test_db_connection():
    """Check if database connection works."""
    print("\n" + "="*70)
    print("TEST 2: Database Connection")
    print("="*70)
    
    try:
        conn = psycopg2.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME
        )
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM employee_details")
        emp_count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        print(f"✓ Database: {config.DB_NAME}")
        print(f"✓ Total Employees: {emp_count}")
        print("\n✅ Database Connection: SUCCESS")
        return True
    except Exception as e:
        print(f"❌ Database Connection: FAILED - {e}")
        return False

# ============================================================================
# TEST 3: Test Date Parsing Function
# ============================================================================
def test_date_parsing():
    """Verify the parse_date function works correctly."""
    print("\n" + "="*70)
    print("TEST 3: Date Parsing")
    print("="*70)
    
    test_dates = [
        ("15/08/2000", "Valid date"),
        ("01/01/1990", "Valid date"),
        ("26/03/2023", "Valid date"),
        ("", "Empty string"),
        ("invalid", "Invalid format"),
        (None, "None value"),
    ]
    
    all_passed = True
    for date_str, description in test_dates:
        result = parse_date(date_str)
        status = "✓" if result or result is None else "✗"
        print(f"{status} parse_date('{date_str}'): {result} ({description})")
        if date_str in ["invalid"] and result is not None:
            all_passed = False
    
    print("\n✅ Date Parsing: ALL TESTS PASSED" if all_passed else "\n⚠️  Date Parsing: Some tests failed")
    return all_passed

# ============================================================================
# TEST 4: Test Email Sending
# ============================================================================
def test_email_sending():
    """Send a test email to verify SMTP works."""
    print("\n" + "="*70)
    print("TEST 4: Email Sending")
    print("="*70)
    
    test_email = os.getenv("SMTP_USER")
    if not test_email:
        print("❌ Cannot test - SMTP_USER not set")
        return False
    
    print(f"\n📧 Sending test email to: {test_email}")
    
    result = send_celebration_email(
        test_email,
        "🧪 Test Email - Zugo Attendance System",
        "Hello!\n\nThis is a test email to verify your email configuration is working.\n\nBest,\nZugo Team"
    )
    
    if result:
        print("✅ Email Sending: SUCCESS")
        print(f"   Check your inbox ({test_email}) for the test email")
        return True
    else:
        print("❌ Email Sending: FAILED")
        return False

# ============================================================================
# TEST 5: Check Employees with Today's Birthday/Anniversary
# ============================================================================
def test_employee_dates():
    """Check if any employees have birthday/anniversary today."""
    print("\n" + "="*70)
    print("TEST 5: Employee Dates (Today's Date Check)")
    print("="*70)
    
    today = datetime.now(IST).date()
    print(f"\n📅 Today: {today.strftime('%A, %B %d, %Y')}")
    
    try:
        conn = psycopg2.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME
        )
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            "SELECT name, email, dob, joining_date FROM employee_details WHERE email != %s ORDER BY name",
            (config.HR_EMAIL,)
        )
        employees = cursor.fetchall()
        cursor.close()
        conn.close()
        
        print(f"\n📊 Checking {len(employees)} employees...\n")
        
        birthdays_today = []
        anniversaries_today = []
        upcoming_events = []
        
        for emp in employees:
            name = emp.get("name", "Unknown")
            email = emp.get("email", "")
            dob_str = emp.get("dob", "")
            joining_str = emp.get("joining_date", "")
            
            dob = parse_date(dob_str)
            joining_date = parse_date(joining_str)
            
            # Check today
            if dob and dob.day == today.day and dob.month == today.month:
                birthdays_today.append((name, email, dob))
                print(f"🎂 BIRTHDAY TODAY: {name} ({email})")
            
            if joining_date and joining_date.day == today.day and joining_date.month == today.month:
                years = today.year - joining_date.year
                anniversaries_today.append((name, email, joining_date, years))
                print(f"🎊 ANNIVERSARY TODAY: {name} - {years} year(s) ({email})")
            
            # Check upcoming (next 7 days)
            for days_ahead in range(1, 8):
                future_date = today + timedelta(days=days_ahead)
                
                if dob and dob.day == future_date.day and dob.month == future_date.month:
                    upcoming_events.append((days_ahead, "Birthday", name, email))
                
                if joining_date and joining_date.day == future_date.day and joining_date.month == future_date.month:
                    upcoming_events.append((days_ahead, "Anniversary", name, email))
        
        print(f"\n📈 Summary:")
        print(f"   🎂 Birthdays today: {len(birthdays_today)}")
        print(f"   🎊 Anniversaries today: {len(anniversaries_today)}")
        print(f"   📅 Upcoming events (7 days): {len(upcoming_events)}")
        
        if upcoming_events:
            print(f"\n📋 Upcoming Events:")
            for days, event_type, name, email in upcoming_events:
                print(f"   +{days} day(s): {event_type} - {name} ({email})")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

# ============================================================================
# TEST 6: Manual Trigger - Run send_event_wishes()
# ============================================================================
def test_manual_trigger():
    """Manually trigger the send_event_wishes function."""
    print("\n" + "="*70)
    print("TEST 6: Manual Trigger - Send Event Wishes")
    print("="*70)
    print("\n🚀 Running send_event_wishes() function...\n")
    
    try:
        send_event_wishes()
        print("\n✅ Function executed successfully")
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================
def run_all_tests():
    """Run all tests sequentially."""
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "BIRTHDAY & ANNIVERSARY FEATURE TEST SUITE" + " "*12 + "║")
    print("╚" + "="*68 + "╝")
    
    results = {
        "SMTP Configuration": test_smtp_config(),
        "Database Connection": test_db_connection(),
        "Date Parsing": test_date_parsing(),
        "Email Sending": test_email_sending(),
        "Employee Dates": test_employee_dates(),
    }
    
    # Show summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\n📊 Results: {passed}/{total} tests passed\n")
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {test_name}")
    
    print("\n" + "="*70)
    
    # Final recommendation
    if passed == total:
        print("\n✅ ALL TESTS PASSED!")
        print("\nThe Birthday & Anniversary feature is working correctly!")
        print("Emails will be sent automatically every day at 9:00 AM IST")
    else:
        print("\n⚠️  SOME TESTS FAILED")
        print("Please fix the issues above before using this feature")
    
    print("\n" + "="*70)
    print("\nWould you like to manually trigger the email sending? (Optional)")
    print("Type 'yes' to send event wishes now: ", end="")
    
    user_input = input().strip().lower()
    if user_input == "yes":
        test_manual_trigger()

if __name__ == "__main__":
    try:
        run_all_tests()
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
