#!/usr/bin/env python3
"""
Quick test to verify pytz is working and imports are correct
"""

import sys
sys.path.insert(0, '/c/Users/Hey! Zugo/project/Attendance/attendance')

print("Testing imports...")

try:
    import pytz
    print("✅ pytz imported successfully")
except ImportError as e:
    print(f"❌ Failed to import pytz: {e}")
    sys.exit(1)

try:
    from datetime import datetime, date, timedelta
    print("✅ datetime imports successful")
except ImportError as e:
    print(f"❌ Failed to import datetime: {e}")
    sys.exit(1)

try:
    # Test IST timezone
    IST = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(IST)
    print(f"✅ IST timezone working: {now_ist}")
except Exception as e:
    print(f"❌ IST timezone error: {e}")
    sys.exit(1)

try:
    # Test UTC timezone
    now_utc = datetime.now(pytz.UTC)
    print(f"✅ UTC timezone working: {now_utc}")
except Exception as e:
    print(f"❌ UTC timezone error: {e}")
    sys.exit(1)

print("\n✅ All imports and timezone functions working correctly!")
print("\nTo restart the application, run:")
print("  uvicorn app:app --reload")
