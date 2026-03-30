"""Helper functions for building user data and reports."""
from datetime import datetime, timedelta
import pytz
from employees import users as static_users
from app.utils.timezone import IST, get_ist_now

def _build_user_from_static(email):
    """Return a dict user object from the static `static_users` if available."""
    u = static_users.get(email)
    if not u:
        return None
    return {
        "name": u.get("name"),
        "email": u.get("email", email),
        "photo": u.get("photo", "profile.jpg"),
        "phone": u.get("phone"),
        "employee_number": u.get("employee_number"),
        "aadhar": u.get("aadhar") or u.get("AADHAR"),
        "dob": u.get("dob"),
        "gender": u.get("gender"),
        "job_role": u.get("job_role", "Employee"),
        "native": u.get("native"),
        "address": u.get("address"),
        "joining_date": u.get("joining_date"),
        "parent_phone": u.get("parent_phone"),
        "total_working": u.get("total_working", 0),
        "total_leave": u.get("total_leave", 0),
        "pan_card": u.get("pan_card"),
        "salary": u.get("salary"),
        "bank_details": u.get("bank_details")
    }

def _build_report_for_user(db, user_email, days: int = 30):
    """Build report rows for the last `days` days for the given user."""
    import psycopg2.extras
    
    # Use IST for date calculations
    end_date = get_ist_now()
    start_date = end_date - timedelta(days=days)
    
    # Convert start_date to UTC for database comparison
    start_date_utc = start_date.astimezone(pytz.UTC)

    cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(
        """
        SELECT event_time, action FROM attendance
        WHERE user_email = %s AND event_time >= %s
        ORDER BY event_time ASC
        """,
        (user_email, start_date_utc)
    )
    rows = cursor.fetchall()
    cursor.close()

    by_date = {}
    for r in rows:
        # Convert UTC to IST for display
        event_time_ist = r["event_time"].astimezone(IST) if r["event_time"].tzinfo else IST.localize(r["event_time"])
        d = event_time_ist.date().isoformat()
        by_date.setdefault(d, []).append({"event_time": event_time_ist, "action": r["action"]})

    report = []
    total_working_seconds = 0
    leave_count = 0
    sunday_count = 0
    
    # Generate all dates in the range
    current_date = start_date.date()
    end_date_only = end_date.date()
    
    while current_date <= end_date_only:
        day_str = current_date.isoformat()
        is_sunday = current_date.weekday() == 6  # 6 = Sunday in Python
        
        if day_str in by_date:
            # Date has attendance records
            events = by_date[day_str]
            check_ins = [e["event_time"] for e in events if e["action"] == "check-in"]
            check_outs = [e["event_time"] for e in events if e["action"] == "check-out"]

            check_in = min(check_ins).strftime("%I:%M %p") if check_ins else "-"
            check_out = max(check_outs).strftime("%I:%M %p") if check_outs else "-"

            seconds = 0
            if check_ins and check_outs:
                seconds = int((max(check_outs) - min(check_ins)).total_seconds())
                total_working_seconds += seconds

            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            total_str = f"{hours}h {minutes}m" if seconds else "-"
            
            # Determine status
            if is_sunday:
                status = "Sunday Work" if check_ins else "Sunday (Off)"
                sunday_count += 1 if check_ins else 0
            else:
                status = "Present" if check_ins else "Partial"

            report.append({
                "day": day_str,
                "check_in": check_in,
                "check_out": check_out,
                "total_hours": total_str,
                "status": status,
                "is_sunday": is_sunday
            })
        else:
            # Date has no attendance records
            if is_sunday:
                # Sunday with no attendance = office closed (don't count as leave)
                report.append({
                    "day": day_str,
                    "check_in": "-",
                    "check_out": "-",
                    "total_hours": "-",
                    "status": "Sunday (Off)",
                    "is_sunday": True
                })
            else:
                # Weekday with no attendance = leave/absent
                leave_count += 1
                report.append({
                    "day": day_str,
                    "check_in": "-",
                    "check_out": "-",
                    "total_hours": "-",
                    "status": "Absent/Leave",
                    "is_sunday": False
                })
        
        current_date += timedelta(days=1)

    return report, total_working_seconds, leave_count, sunday_count
