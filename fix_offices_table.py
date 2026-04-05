#!/usr/bin/env python3
"""
Fix Offices Table Script
Corrects the offices table to have proper office assignments:
- Office ID 1: HQ with admin zugopvtnetwork@gmail.com
- Office ID 2: wpsstore with admin Wholesalepriceshopping27@gmail.com
"""

import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(DATABASE_URL)

def fix_offices_table():
    """Fix the offices table assignments."""
    db = get_db_connection()
    cursor = db.cursor()

    try:
        print("Fixing offices table...")

        # Update office ID 1 to HQ
        cursor.execute("""
            UPDATE offices
            SET office_name = 'HQ', admin_email = 'zugopvtnetwork@gmail.com'
            WHERE id = 1
        """)

        # Update office ID 2 to wpsstore
        cursor.execute("""
            UPDATE offices
            SET office_name = 'wpsstore', admin_email = 'Wholesalepriceshopping27@gmail.com'
            WHERE id = 2
        """)

        db.commit()
        print("✓ Offices table fixed successfully")

        # Verify the changes
        cursor.execute("SELECT id, office_name, admin_email FROM offices ORDER BY id")
        offices = cursor.fetchall()

        print("\nUpdated offices table:")
        for office in offices:
            print(f"  ID: {office[0]} | Name: {office[1]} | Admin: {office[2]}")

    except Exception as e:
        print(f"Error fixing offices table: {e}")
        db.rollback()
    finally:
        cursor.close()
        db.close()

if __name__ == "__main__":
    fix_offices_table()