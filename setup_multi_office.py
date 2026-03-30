import psycopg2
import config

conn = psycopg2.connect(
    host=config.DB_HOST,
    port=config.DB_PORT,
    user=config.DB_USER,
    password=config.DB_PASSWORD,
    database=config.DB_NAME
)
cursor = conn.cursor()

print("=== SETTING UP MULTI-OFFICE ADMIN ACCESS ===\n")

# Add zugoadmin1 with office_id = 3 so they can manage CBE Main as well
try:
    cursor.execute("""
        INSERT INTO employee_details (name, email, password, job_role, office_id)
        VALUES (%s, %s, %s, %s, %s)
    """, ("Admin - CBE Main", "zugoadmin1@gmail.com", "admin@123", "Office Admin", 3))
    conn.commit()
    print("✓ Added zugoadmin1 as admin for CBE Main (office 3)")
except psycopg2.IntegrityError as e:
    conn.rollback()
    print(f"Info: zugoadmin1 perhaps already has multiple entries")

# Show final admin assignments
cursor.execute("""
    SELECT email, office_id, job_role 
    FROM employee_details 
    WHERE job_role LIKE '%Office Admin%' 
    ORDER BY email, office_id
""")
admins = cursor.fetchall()
print("\n=== FINAL OFFICE ADMIN ASSIGNMENTS ===")
for admin in admins:
    email, office_id, role = admin
    # Get office name
    cursor.execute("SELECT office_name FROM offices WHERE id = %s", (office_id,))
    office_result = cursor.fetchone()
    office_name = office_result[0] if office_result else "Unknown"
    print(f" {email} manages {office_name} (Office {office_id})")

print("\n=== LOGIN CREDENTIALS ===")
print("Headquarters Admin: zugopvtnetwork@gmail.com / zugo@123")
print("  → Can log in and select any office to manage")
print("\nTiruppur & CBE Main Admin: zugoadmin1@gmail.com / admin@123")
print("  → Can manage both Tiruppur (1) and CBE Main (3)")
print("  → When logging in, office dropdown will show available offices")
print("\nCBE Admin: zugoadmin2@gmail.com / admin@123")
print("  → Can manage CBE (2) only")

cursor.close()
conn.close()
