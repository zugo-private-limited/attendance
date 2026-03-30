"""Timezone utilities for IST (India Standard Time) handling."""
from datetime import datetime
import pytz

IST = pytz.timezone('Asia/Kolkata')  # India Standard Time

def get_ist_now():
    """Get current time in IST (Asia/Kolkata)."""
    return datetime.now(IST)

def get_ist_date():
    """Get current date in IST."""
    return get_ist_now().date()
