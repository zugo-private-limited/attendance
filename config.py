import os
from datetime import time
import psycopg2
from dotenv import load_dotenv

# Load .env file only in local development (not on Render)
if not os.getenv("RENDER"):
    load_dotenv()

# Database Configuration
# On Render: Use environment variables set in dashboard
# Locally: Use .env file values
DB_NAME = os.getenv("DB_NAME", "attendance_db")
DB_USER = os.getenv("DB_USER", "zugo_attendance")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://...")

# Office Location for Attendance
OFFICE_LAT = 11.1205177
OFFICE_LON = 77.3399277
OFFICE_RADIUS_METERS = 500  # 0.5 km radius

# Attendance Time Constraints (HH:MM format)
CHECKIN_MORNING_START = time(9, 00)    # 9:00 AM
CHECKIN_MORNING_END = time(9, 45)     # 9.45 PM
CHECKIN_AFTERNOON_START = time(13, 30) # 1:30 PM
CHECKIN_AFTERNOON_END = time(14, 15)   # 2:15 PM
CHECKOUT_MIN_TIME = time(19, 15)       # 7:15 PM

# Email Configuration
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "zugopvtnetwork@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

HR_EMAIL = os.getenv("HR_EMAIL", "zugopvtnetwork@gmail.com")  # HR account
MD_EMAIL = os.getenv("MD_EMAIL", "zugoprivitelimited@gmail.com")


# --- LOCATION CONFIGURATION ---
# OFFICE_LAT = 11.120529  # your office's latitude
# OFFICE_LON = 77.3398681 # your office's longitude
# OFFICE_RADIUS_METERS = 100  # 100 meters radius for location validation

# Scheduler Settings
LEAVE_MARKING_HOUR = 20  # 8 PM UTC
MONTHLY_REPORT_DAY = 20  # Day of the month to send report

# Attendance Calculation Period (21st to 20th)
ATTENDANCE_PERIOD_START_DAY = 21  # Start calculation from the 21st
ATTENDANCE_PERIOD_END_DAY = 20    # End calculation on the 20th