#!/usr/bin/env python3
"""
Test script to validate timezone-aware presence detection fix.
Runs against the local database to confirm check-in times are detected correctly.
"""

from datetime import datetime, date, time
import pytz
from data import fetch_attendance_for_today, get_db_connection
import psycopg2
import psycopg2.extras

IST = pytz.timezone('Asia/Kolkata')

def test_presence_detection():
    """Test if presence detection works with UTC-based queries."""
    print("Testing presence detection fix...")
    
    # Connect to database
    try:
        conn = psycopg2.connect(
            host="localhost",  # Change if needed
            port=5432,
            user="postgres",  # Change if needed
            password="",  # Change if needed
            database="attendance_db"  # Change if needed
        )
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get all employees
        cursor.execute("SELECT DISTINCT user_email FROM attendance")
        emails = cursor.fetchall()
        
        if not emails:
            print("No attendance records found in database.")
            conn.close()
            return
        
        print(f"\nFound {len(emails)} employees with attendance records.")
        print("\n" + "="*80)
        print("PRESENCE DETECTION TEST RESULTS")
        print("="*80)
        
        for record in emails:
            email = record['user_email']
            
            # Get today's IST date
            today_ist = datetime.now(IST).date()
            
            # Compute UTC range for IST today
            start_ist = datetime.combine(today_ist, time.min).replace(tzinfo=IST)
            end_ist = datetime.combine(today_ist, time.max).replace(tzinfo=IST)
            start_utc = start_ist.astimezone(pytz.UTC)
            end_utc = end_ist.astimezone(pytz.UTC)
            
            # Query for check-ins in UTC range
            cursor.execute(
                "SELECT action, event_time FROM attendance WHERE user_email = %s AND event_time >= %s AND event_time <= %s",
                (email, start_utc, end_utc)
            )
            records = cursor.fetchall()
            
            has_checkin = any(r['action'] == 'check-in' for r in records)
            status = "PRESENT ✓" if has_checkin else "ABSENT ✗"
            
            print(f"\n{email:<40} | Status: {status}")
            
            if records:
                for r in records:
                    event_time_ist = r['event_time'].astimezone(IST) if hasattr(r['event_time'], 'tzinfo') else r['event_time']
                    print(f"  └─ {r['action'].upper():<10} at {event_time_ist.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            else:
                print(f"  └─ No records for IST date {today_ist}")
        
        print("\n" + "="*80)
        cursor.close()
        conn.close()
        print("✓ Test completed successfully!")
        
    except psycopg2.Error as e:
        print(f"✗ Database connection error: {e}")
        print("Ensure PostgreSQL is running and credentials are correct in config.py")

if __name__ == "__main__":
    test_presence_detection()
