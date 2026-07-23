"""
Migration script to fix timezone issues in attendance table.
This converts all existing TIMESTAMP values to TIMESTAMP WITH TIME ZONE
and ensures all times are stored as UTC.
"""

import psycopg2
from datetime import datetime
import pytz
import config

IST = pytz.timezone('Asia/Kolkata')
UTC = pytz.UTC

def migrate_timezone():
    """Migrate attendance table to use TIMESTAMP WITH TIME ZONE."""
    try:
        conn = psycopg2.connect(
            host=config.DB_HOST,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            port=config.DB_PORT,
            database=config.DB_NAME
        )
        cursor = conn.cursor()
        
        print("Starting timezone migration...")
        
        # Step 1: Check if column exists and its type
        cursor.execute("""
            SELECT data_type 
            FROM information_schema.columns 
            WHERE table_name = 'attendance' AND column_name = 'event_time'
        """)
        result = cursor.fetchone()
        if not result:
            print("❌ attendance table or event_time column not found")
            cursor.close()
            conn.close()
            return
        
        current_type = result[0]
        print(f"Current event_time type: {current_type}")
        
        # Step 2: If it's already TIMESTAMP WITH TIME ZONE, we're done
        if 'timestamp with time zone' in current_type.lower():
            print("✅ Column already uses TIMESTAMP WITH TIME ZONE")
            cursor.close()
            conn.close()
            return
        
        # Step 3: Create a new temporary column with the correct type
        print("Creating temporary column with correct timezone...")
        cursor.execute("""
            ALTER TABLE attendance 
            ADD COLUMN event_time_new TIMESTAMP WITH TIME ZONE
        """)
        conn.commit()
        
        # Step 4: Copy data from old column to new column, treating old times as IST
        print("Converting existing times from IST to UTC...")
        cursor.execute("""
            UPDATE attendance 
            SET event_time_new = 
                CASE 
                    WHEN event_time IS NOT NULL THEN
                        -- Treat the timestamp as IST time and convert to UTC
                        (event_time AT TIME ZONE 'UTC') AT TIME ZONE 'Asia/Kolkata' 
                ELSE NULL
                END
        """)
        migrated = cursor.rowcount
        print(f"✅ Migrated {migrated} records")
        conn.commit()
        
        # Step 5: Drop the old column
        print("Dropping old column...")
        cursor.execute("""
            ALTER TABLE attendance 
            DROP COLUMN event_time
        """)
        conn.commit()
        
        # Step 6: Rename the new column
        print("Renaming new column...")
        cursor.execute("""
            ALTER TABLE attendance 
            RENAME COLUMN event_time_new TO event_time
        """)
        conn.commit()
        
        # Step 7: Add NOT NULL constraint back
        print("Adding NOT NULL constraint...")
        cursor.execute("""
            ALTER TABLE attendance 
            ALTER COLUMN event_time SET NOT NULL
        """)
        conn.commit()
        
        print("✅ Timezone migration completed successfully!")
        print(f"   - Converted {migrated} records to UTC with timezone info")
        print("   - All times are now stored as TIMESTAMP WITH TIME ZONE")
        
        cursor.close()
        conn.close()
        
    except psycopg2.Error as e:
        print(f"❌ Migration error: {e}")
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Attendance Table Timezone Migration")
    print("=" * 60)
    migrate_timezone()
    print("=" * 60)
