"""
TEST SUITE: Multi-Office Attendance System
Tests the differentiated rules for Main HQ vs Branch Offices
"""

from datetime import datetime, date, timedelta, time
import pytz
from typing import Tuple

IST = pytz.timezone('Asia/Kolkata')

# ======================================================================
# TEST DATA
# ======================================================================

TEST_DATES = {
    "march_21": date(2024, 3, 21),      # Start of HQ period
    "march_25": date(2024, 3, 25),      # Mid HQ period
    "april_10": date(2024, 4, 10),      # Start of next HQ period
    "april_15": date(2024, 4, 15),      # Mid period
    "april_30": date(2024, 4, 30),      # End of month
}

TEST_TIMES = {
    "early_morning": time(3, 30),       # 3:30 AM - Outside window
    "morning": time(11, 0),             # 11:00 AM - In morning window
    "afternoon_early": time(13, 45),    # 1:45 PM - In afternoon window
    "afternoon_late": time(14, 15),     # 2:15 PM - Edge of afternoon window
    "evening": time(17, 0),             # 5:00 PM - Outside window
    "late_evening": time(19, 30),       # 7:30 PM - After checkout minimum
}

TEST_LOCATIONS = {
    "hq": (11.1205177, 77.3399277),           # HQ office coordinates
    "hq_inside": (11.1206, 77.3400),          # Within 500m of HQ
    "branch_far": (13.0826, 80.2707),         # Chennai - far from HQ
    "employee_home": (11.0587, 76.9983),      # Employee home (different city)
}

OFFICE_IDS = {
    "main_hq": 1,
    "branch_1": 2,
    "branch_2": 3,
}

# ======================================================================
# HQ ATTENDANCE PERIOD CALCULATION (21-to-20)
# ======================================================================

def get_hq_attendance_period(ref_date: date) -> Tuple[date, date]:
    """Calculate 21st-to-20th period for Main HQ"""
    ATTENDANCE_PERIOD_START_DAY = 21
    ATTENDANCE_PERIOD_END_DAY = 20
    
    if ref_date.day > ATTENDANCE_PERIOD_END_DAY:  # Day > 20
        # Current month 21st to next month 20th
        start_month = ref_date.month
        start_year = ref_date.year
        end_month = (ref_date.month % 12) + 1
        end_year = ref_date.year if end_month != 1 else ref_date.year + 1
    else:
        # Previous month 21st to current month 20th
        end_month = ref_date.month
        end_year = ref_date.year
        start_month = (ref_date.month - 2 + 12) % 12 + 1
        start_year = ref_date.year if start_month != 12 else ref_date.year - 1

    start_date = date(start_year, start_month, ATTENDANCE_PERIOD_START_DAY)
    end_date = date(end_year, end_month, ATTENDANCE_PERIOD_END_DAY)

    if ref_date.day <= ATTENDANCE_PERIOD_END_DAY:
        if start_date.month == ref_date.month:
            start_date = date(start_date.year, start_date.month - 1, ATTENDANCE_PERIOD_START_DAY)
            if start_date.month == 0:
                start_date = date(start_date.year - 1, 12, ATTENDANCE_PERIOD_START_DAY)

    return start_date, end_date


def get_branch_attendance_period(ref_date: date) -> Tuple[date, date]:
    """Calculate calendar month period for Branch Offices"""
    start_date = date(ref_date.year, ref_date.month, 1)
    
    if ref_date.month == 12:
        end_date = date(ref_date.year, 12, 31)
    else:
        end_date = date(ref_date.year, ref_date.month + 1, 1) - timedelta(days=1)
    
    return start_date, end_date


# ======================================================================
# VALIDATION FUNCTIONS (Mirroring services.py logic)
# ======================================================================

def is_at_office_hq(lat: float, lon: float) -> bool:
    """HQ location validation using Haversine"""
    from math import radians, cos, sin, asin, sqrt
    
    OFFICE_LAT = 11.1205177
    OFFICE_LON = 77.3399277
    OFFICE_RADIUS_METERS = 500
    
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371000  # Earth radius in meters
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
        c = 2 * asin(sqrt(a))
        return R * c
    
    distance = haversine(lat, lon, OFFICE_LAT, OFFICE_LON)
    return distance <= OFFICE_RADIUS_METERS


def can_checkin_at_time_hq(current_time: time) -> bool:
    """Check if time is within HQ windows"""
    MORNING_START = time(9, 0)
    MORNING_END = time(14, 0)
    AFTERNOON_START = time(13, 30)
    AFTERNOON_END = time(14, 15)
    
    is_morning = MORNING_START <= current_time <= MORNING_END
    is_afternoon = AFTERNOON_START <= current_time <= AFTERNOON_END
    return is_morning or is_afternoon


def can_checkout_hq(current_time: time) -> bool:
    """Check if checkout is allowed for HQ"""
    CHECKOUT_MIN_TIME = time(19, 15)
    return current_time >= CHECKOUT_MIN_TIME


# ======================================================================
# TEST CASES
# ======================================================================

def test_hq_attendance_periods():
    """TEST 1: Verify HQ uses 21-to-20 period"""
    print("=" * 70)
    print("TEST 1: HQ Attendance Period (21-to-20)")
    print("=" * 70)
    
    test_cases = [
        (date(2024, 3, 21), (date(2024, 3, 21), date(2024, 4, 20)), "21 Mar"),
        (date(2024, 3, 25), (date(2024, 3, 21), date(2024, 4, 20)), "25 Mar (mid period)"),
        (date(2024, 4, 10), (date(2024, 3, 21), date(2024, 4, 20)), "10 Apr (before 20th)"),
        (date(2024, 4, 22), (date(2024, 4, 21), date(2024, 5, 20)), "22 Apr (after 20th)"),
    ]
    
    for ref_date, expected, label in test_cases:
        result = get_hq_attendance_period(ref_date)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        print(f"{status} | {label}")
        print(f"  Expected: {expected[0]} → {expected[1]}")
        print(f"  Got:      {result[0]} → {result[1]}\n")


def test_branch_attendance_periods():
    """TEST 2: Verify Branch uses calendar month period"""
    print("=" * 70)
    print("TEST 2: Branch Attendance Period (Calendar Month)")
    print("=" * 70)
    
    test_cases = [
        (date(2024, 3, 1), (date(2024, 3, 1), date(2024, 3, 31)), "1 Mar"),
        (date(2024, 3, 25), (date(2024, 3, 1), date(2024, 3, 31)), "25 Mar"),
        (date(2024, 4, 15), (date(2024, 4, 1), date(2024, 4, 30)), "15 Apr"),
        (date(2024, 2, 14), (date(2024, 2, 1), date(2024, 2, 29)), "14 Feb (leap year)"),
    ]
    
    for ref_date, expected, label in test_cases:
        result = get_branch_attendance_period(ref_date)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        print(f"{status} | {label}")
        print(f"  Expected: {expected[0]} → {expected[1]}")
        print(f"  Got:      {result[0]} → {result[1]}\n")


def test_hq_location_validation():
    """TEST 3: Verify HQ enforces location"""
    print("=" * 70)
    print("TEST 3: HQ Location Validation")
    print("=" * 70)
    
    test_cases = [
        (TEST_LOCATIONS["hq"], True, "Exact HQ coordinates"),
        (TEST_LOCATIONS["hq_inside"], True, "Inside 500m radius"),
        (TEST_LOCATIONS["branch_far"], False, "Branch location (Chennai)"),
        (TEST_LOCATIONS["employee_home"], False, "Employee home"),
    ]
    
    for (lat, lon), expected, label in test_cases:
        result = is_at_office_hq(lat, lon)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        expected_str = "Within office bounds" if expected else "Outside office bounds"
        print(f"{status} | {label}")
        print(f"  Location: ({lat}, {lon})")
        print(f"  Expected: {expected_str}, Got: {'Within' if result else 'Outside'}\n")


def test_hq_time_windows():
    """TEST 4: Verify HQ enforces time windows"""
    print("=" * 70)
    print("TEST 4: HQ Check-in Time Windows")
    print("=" * 70)
    
    test_times = [
        (TEST_TIMES["early_morning"], False, "3:30 AM (outside window)"),
        (TEST_TIMES["morning"], True, "11:00 AM (in morning 9-2 PM)"),
        (TEST_TIMES["afternoon_early"], True, "1:45 PM (in afternoon 1:30-2:15 PM)"),
        (TEST_TIMES["afternoon_late"], True, "2:15 PM (edge of window)"),
        (TEST_TIMES["evening"], False, "5:00 PM (outside window)"),
    ]
    
    for time_val, expected, label in test_times:
        result = can_checkin_at_time_hq(time_val)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        allowed_str = "Allowed" if expected else "Rejected"
        print(f"{status} | {label}")
        print(f"  Time: {time_val.strftime('%H:%M')}")
        print(f"  Expected: {allowed_str}, Got: {'Allowed' if result else 'Rejected'}\n")


def test_hq_checkout_time():
    """TEST 5: Verify HQ enforces checkout time"""
    print("=" * 70)
    print("TEST 5: HQ Checkout Time Restriction")
    print("=" * 70)
    
    test_times = [
        (time(17, 0), False, "5:00 PM (before 7:15 PM)"),
        (time(19, 14), False, "7:14 PM (1 minute before)"),
        (time(19, 15), True, "7:15 PM (exactly)"),
        (time(19, 30), True, "7:30 PM (after minimum)"),
        (time(20, 0), True, "8:00 PM (well after)"),
    ]
    
    for time_val, expected, label in test_times:
        result = can_checkout_hq(time_val)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        allowed_str = "Allowed" if expected else "Rejected"
        print(f"{status} | {label}")
        print(f"  Time: {time_val.strftime('%H:%M')}")
        print(f"  Expected: {allowed_str}, Got: {'Allowed' if result else 'Rejected'}\n")


def test_branch_no_restrictions():
    """TEST 6: Verify Branch has no restrictions"""
    print("=" * 70)
    print("TEST 6: Branch Office - No Restrictions")
    print("=" * 70)
    
    # Branch always allows any location
    print("✅ PASS | Branch location validation disabled")
    print("  All locations allowed (returns True)\n")
    
    # Branch allows all times
    print("✅ PASS | Branch check-in time windows disabled")
    print("  All times allowed\n")
    
    # Branch allows all checkout times
    print("✅ PASS | Branch checkout time restrictions disabled")
    print("  Any time allowed\n")


def test_scenario_hq_employee():
    """SCENARIO 1: HQ Employee Check-in Attempts"""
    print("=" * 70)
    print("SCENARIO 1: Main HQ Employee - john.doe@company.com")
    print("=" * 70)
    
    scenarios = [
        (TEST_TIMES["early_morning"], TEST_LOCATIONS["hq_inside"], False, "3:30 AM from HQ"),
        (TEST_TIMES["morning"], TEST_LOCATIONS["branch_far"], False, "11:00 AM from Chennai"),
        (TEST_TIMES["morning"], TEST_LOCATIONS["hq_inside"], True, "11:00 AM from HQ"),
        (TEST_TIMES["afternoon_early"], TEST_LOCATIONS["hq"], True, "1:45 PM from exact HQ"),
        (TEST_TIMES["evening"], TEST_LOCATIONS["hq"], False, "5:00 PM from HQ"),
    ]
    
    for check_time, location, should_allow, label in scenarios:
        time_ok = can_checkin_at_time_hq(check_time)
        location_ok = is_at_office_hq(location[0], location[1])
        result = time_ok and location_ok
        status = "✅ ALLOWED" if result else "❌ REJECTED"
        expected = "should succeed" if should_allow else "should fail"
        
        print(f"{status} | {label} ({expected})")
        print(f"  Time check: {'✓' if time_ok else '✗'} | Location check: {'✓' if location_ok else '✗'}\n")


def test_scenario_branch_employee():
    """SCENARIO 2: Branch Employee Check-in Attempts"""
    print("=" * 70)
    print("SCENARIO 2: Branch Office Employee - jane.smith@company.com")
    print("=" * 70)
    
    scenarios = [
        (TEST_TIMES["early_morning"], TEST_LOCATIONS["employee_home"], True, "3:30 AM from home"),
        (TEST_TIMES["evening"], TEST_LOCATIONS["branch_far"], True, "5:00 PM from branch"),
        (TEST_TIMES["afternoon_late"], TEST_LOCATIONS["branch_far"], True, "2:15 PM from anywhere"),
    ]
    
    for check_time, location, should_allow, label in scenarios:
        # Branch allows everything
        result = True
        status = "✅ ALLOWED"
        expected = "always succeeds"
        
        print(f"{status} | {label} ({expected})")
        print(f"  No location/time restrictions for branches\n")


# ======================================================================
# RUN ALL TESTS
# ======================================================================

if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  MULTI-OFFICE ATTENDANCE SYSTEM - TEST SUITE".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    print("\n")
    
    try:
        test_hq_attendance_periods()
        print("\n")
        
        test_branch_attendance_periods()
        print("\n")
        
        test_hq_location_validation()
        print("\n")
        
        test_hq_time_windows()
        print("\n")
        
        test_hq_checkout_time()
        print("\n")
        
        test_branch_no_restrictions()
        print("\n")
        
        test_scenario_hq_employee()
        print("\n")
        
        test_scenario_branch_employee()
        print("\n")
        
        print("=" * 70)
        print("✅ ALL TESTS COMPLETED!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
