#!/usr/bin/env python
"""Verify invoices table schema"""

import psycopg2

try:
    conn = psycopg2.connect(
        host='localhost', 
        database='attendance_db', 
        user='postgres', 
        password='zugo'
    )
    cursor = conn.cursor()
    
    # Check if office_id column exists
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='invoices' AND column_name='office_id'
    """)
    result = cursor.fetchone()
    
    if result:
        print("✅ office_id column exists in invoices table!")
    else:
        print("❌ office_id column NOT found in invoices table")
    
    # Show all columns in invoices table
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name='invoices'
        ORDER BY ordinal_position
    """)
    columns = cursor.fetchall()
    
    print("\n📋 Invoices Table Schema:")
    for col_name, col_type in columns:
        print(f"  • {col_name}: {col_type}")
    
    conn.close()
    print("\n✅ Schema verification complete!")
    
except Exception as e:
    print(f"❌ Error: {e}")
