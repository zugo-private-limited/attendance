"""
Script to safely remove old data from PostgreSQL attendance database.
Supports archiving and selective deletion.
"""

import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
import config
import csv
import os

def get_connection():
    """Get database connection"""
    return psycopg2.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME
    )

def archive_old_attendance(days_old: int = 365, output_file: str = "archived_attendance.csv"):
    """
    Archive old attendance records to CSV before deletion.
    
    Args:
        days_old: Delete records older than this many days (default: 1 year)
        output_file: CSV file to save archived data
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        print(f"\n📅 Archiving attendance records older than {days_old} days ({cutoff_date.date()})")
        
        # Fetch old records
        cursor.execute(
            "SELECT * FROM attendance WHERE event_time < %s ORDER BY event_time DESC",
            (cutoff_date,)
        )
        old_records = cursor.fetchall()
        
        if not old_records:
            print("❌ No old records found to archive.")
            cursor.close()
            conn.close()
            return 0
        
        # Save to CSV
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=old_records[0].keys())
            writer.writeheader()
            writer.writerows(old_records)
        
        record_count = len(old_records)
        print(f"✅ Archived {record_count} records to {output_file}")
        
        cursor.close()
        conn.close()
        
        return record_count
        
    except psycopg2.Error as e:
        print(f"❌ Error archiving data: {e}")
        return 0

def delete_old_attendance(days_old: int = 365, archive_first: bool = True):
    """
    Delete old attendance records from database.
    
    Args:
        days_old: Delete records older than this many days
        archive_first: Archive to CSV before deleting (recommended)
    """
    try:
        # Archive first if requested
        if archive_first:
            archive_old_attendance(days_old, f"archived_attendance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        
        conn = get_connection()
        cursor = conn.cursor()
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        print(f"\n🗑️  Deleting attendance records older than {days_old} days ({cutoff_date.date()})")
        
        # Get count before deletion
        cursor.execute(
            "SELECT COUNT(*) FROM attendance WHERE event_time < %s",
            (cutoff_date,)
        )
        count_before = cursor.fetchone()[0]
        
        if count_before == 0:
            print("❌ No old records found to delete.")
            cursor.close()
            conn.close()
            return 0
        
        # Delete old records
        cursor.execute(
            "DELETE FROM attendance WHERE event_time < %s",
            (cutoff_date,)
        )
        conn.commit()
        
        print(f"✅ Deleted {cursor.rowcount} attendance records")
        
        cursor.close()
        conn.close()
        
        return cursor.rowcount
        
    except psycopg2.Error as e:
        print(f"❌ Error deleting data: {e}")
        return 0

def delete_all_attendance():
    """
    Delete ALL attendance records (careful!).
    Archive is created automatically.
    """
    try:
        print("\n⚠️  WARNING: This will delete ALL attendance records!")
        confirm = input("Type 'YES, DELETE ALL' to confirm: ").strip()
        
        if confirm != "YES, DELETE ALL":
            print("❌ Deletion cancelled.")
            return 0
        
        # Archive everything first
        archive_file = f"archived_all_attendance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        count = archive_old_attendance(days_old=10000, output_file=archive_file)  # Very old cutoff
        
        if count == 0:
            print("❌ No records to delete.")
            return 0
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Delete all
        cursor.execute("DELETE FROM attendance")
        conn.commit()
        
        print(f"✅ Deleted all {cursor.rowcount} attendance records (backed up to {archive_file})")
        
        cursor.close()
        conn.close()
        
        return cursor.rowcount
        
    except psycopg2.Error as e:
        print(f"❌ Error: {e}")
        return 0

def get_database_stats():
    """Get statistics about database"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Attendance stats
        cursor.execute("SELECT COUNT(*) FROM attendance")
        attendance_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT MIN(event_time), MAX(event_time) FROM attendance")
        date_range = cursor.fetchone()
        
        # Employee stats
        cursor.execute("SELECT COUNT(*) FROM employee_details")
        employee_count = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        print("\n📊 DATABASE STATISTICS")
        print(f"  Total Attendance Records: {attendance_count:,}")
        if date_range[0]:
            print(f"  Date Range: {date_range[0]} to {date_range[1]}")
        print(f"  Total Employees: {employee_count}")
        
    except psycopg2.Error as e:
        print(f"❌ Error getting stats: {e}")

if __name__ == "__main__":
    import sys
    
    print("\n" + "="*50)
    print("ATTENDANCE DATA CLEANUP TOOL")
    print("="*50)
    
    get_database_stats()
    
    print("\nOptions:")
    print("1. Delete records older than 6 months (archive first)")
    print("2. Delete records older than 1 year (archive first)")
    print("3. Delete records older than 2 years (archive first)")
    print("4. Delete ALL records (archive first)")
    print("5. Exit")
    
    choice = input("\nSelect option (1-5): ").strip()
    
    if choice == "1":
        delete_old_attendance(days_old=180, archive_first=True)
    elif choice == "2":
        delete_old_attendance(days_old=365, archive_first=True)
    elif choice == "3":
        delete_old_attendance(days_old=730, archive_first=True)
    elif choice == "4":
        delete_all_attendance()
    else:
        print("Exiting...")
    
    get_database_stats()
