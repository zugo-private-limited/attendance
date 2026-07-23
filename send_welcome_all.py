"""One-off script: send a welcome email to all employees.

Usage: python send_welcome_all.py

This uses the project's `config`, `data`, and `services` modules and the
existing SMTP settings. Run from the project root or the `attendance` folder
where the package imports resolve.
"""
import sys
from datetime import datetime
import config
from data import get_db_conn, fetch_all_employees
import services


def main():
    print("Connecting to database...")
    try:
        conn = get_db_conn()
    except Exception as e:
        print(f"Failed to get DB connection: {e}")
        sys.exit(1)

    try:
        employees = fetch_all_employees(conn)
    except Exception as e:
        print(f"Failed to fetch employees: {e}")
        conn.close()
        sys.exit(1)

    print(f"Found {len(employees)} employees. Sending welcome emails...")

    subject = "Welcome to Zugo Private Limited"
    sent = 0
    failed = 0

    message_template = (
        "Dear {name},\n\n"
        "Welcome to Zugo Private Limited! We're glad to have you on board.\n\n"
        "This is a sample welcome message from the Zugo Attendance Team.\n\n"
        "Best regards,\n"
        "Zugo Attendance Team"
    )

    for emp in employees:
        email = emp.get("email")
        name = emp.get("name") or email
        if not email:
            print(f"Skipping employee with missing email: {name}")
            continue

        message = message_template.format(name=name)
        try:
            ok = services.send_celebration_email(email, subject, message)
            if ok:
                print(f"✅ Sent to {name} <{email}>")
                sent += 1
            else:
                print(f"❌ Failed to send to {name} <{email}>")
                failed += 1
        except Exception as e:
            print(f"❌ Exception sending to {name} <{email}>: {e}")
            failed += 1

    conn.close()
    print(f"\nSummary: Sent={sent}, Failed={failed}")


if __name__ == "__main__":
    main()
