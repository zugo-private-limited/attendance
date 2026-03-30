import psycopg2
import config

# Connect to database
conn = psycopg2.connect(
    host=config.DB_HOST,
    port=config.DB_PORT,
    user=config.DB_USER,
    password=config.DB_PASSWORD,
    database=config.DB_NAME
)
cursor = conn.cursor()

print("=== FIXING OFFICE ADMIN ASSIGNMENTS ===\n")

# The issue: zugoadmin3 was created but should not exist
# zugoadmin1 should manage both office 1 (Tiruppur) and office 3 (CBE Main)
# zugoadmin2 should manage office 2 (CBE)

# Step 1: Delete the incorrect zugoadmin3 record
print("Deleting incorrect zugoadmin3@gmail.com record...")
cursor.execute("DELETE FROM employee_details WHERE email = %s", ("zugoadmin3@gmail.com",))
deleted = cursor.rowcount
print(f"Deleted {deleted} record(s)")

# Step 2: Verify final state
cursor.execute("SELECT id, office_name, admin_email FROM offices ORDER BY id")
offices = cursor.fetchall()
print("\n=== OFFICES (Final) ===")
for office in offices:
    print(f"ID: {office[0]}, Name: {office[1]}, Admin should be: {office[2]}")

cursor.execute("SELECT email, office_id, job_role FROM employee_details WHERE job_role LIKE '%Office Admin%' ORDER BY email")
admins = cursor.fetchall()
print("\n=== OFFICE ADMINS (Final) ===")
for admin in admins:
    print(f"Email: {admin[0]}, Office ID: {admin[1]}, Role: {admin[2]}")

print("\n=== NOTE ===")
print("zugoadmin1@gmail.com manages BOTH Tiruppur (office 1) and CBE Main (office 3)")
print("When zugoadmin1 logs in, they will see office selection and can choose which office to manage")
print("zugoadmin2@gmail.com manages CBE (office 2)")

conn.commit()
cursor.close()
conn.close()
