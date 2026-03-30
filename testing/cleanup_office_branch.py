"""
Script to completely delete an office and all associated data from the database.
Use this when you want to remove a branch office completely.

Usage:
    python cleanup_office_branch.py <office_id>
    
Example:
    python cleanup_office_branch.py 11  # Delete test branch office
"""

import sys
import psycopg2
from data import get_db_conn

def delete_office(office_id):
    """Delete an office and all its associated data."""
    
    # Prevent deletion of Main HQ
    if office_id == 1:
        print("❌ ERROR: Cannot delete Main HQ (office_id=1)")
        return False
    
    try:
        db = get_db_conn()
        cursor = db.cursor()
        
        # Get office info before deletion
        cursor.execute('SELECT office_name FROM offices WHERE id = %s', (office_id,))
        office = cursor.fetchone()
        
        if not office:
            print(f"❌ ERROR: office_id={office_id} does not exist")
            cursor.close()
            db.close()
            return False
        
        office_name = office[0]
        
        # Count employees in this office
        cursor.execute('SELECT COUNT(*) FROM employee_details WHERE office_id = %s', (office_id,))
        emp_count = cursor.fetchone()[0]
        
        # Count attendance records
        cursor.execute("""
            SELECT COUNT(*) FROM attendance 
            WHERE user_email IN (SELECT email FROM employee_details WHERE office_id = %s)
        """, (office_id,))
        att_count = cursor.fetchone()[0]
        
        print(f"\n{'='*70}")
        print(f"DELETING: {office_name} (office_id={office_id})")
        print(f"{'='*70}")
        print(f"⚠️  Will delete:")
        print(f"   • {emp_count} employees")
        print(f"   • {att_count} attendance records")
        print(f"   • All office data")
        
        # Ask for confirmation
        confirm = input(f"\nType 'YES' to confirm deletion: ").strip().upper()
        if confirm != 'YES':
            print("❌ Deletion cancelled")
            cursor.close()
            db.close()
            return False
        
        # Delete in order (respecting foreign keys):
        print("\n🗑️  Deleting data...")
        
        # 1. Delete attendance records
        cursor.execute("""
            DELETE FROM attendance 
            WHERE user_email IN (SELECT email FROM employee_details WHERE office_id = %s)
        """, (office_id,))
        print(f"   ✓ Deleted {cursor.rowcount} attendance records")
        
        # 2. Delete employees
        cursor.execute('DELETE FROM employee_details WHERE office_id = %s', (office_id,))
        print(f"   ✓ Deleted {cursor.rowcount} employees")
        
        # 3. Delete office
        cursor.execute('DELETE FROM offices WHERE id = %s', (office_id,))
        print(f"   ✓ Deleted office")
        
        db.commit()
        cursor.close()
        db.close()
        
        print(f"\n{'='*70}")
        print(f"✅ Successfully deleted {office_name} (office_id={office_id})")
        print(f"{'='*70}\n")
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    
    try:
        office_id = int(sys.argv[1])
    except ValueError:
        print(f"❌ Error: office_id must be a number")
        sys.exit(1)
    
    delete_office(office_id)
