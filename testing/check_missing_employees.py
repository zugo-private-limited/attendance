from employees import users as static_users
import psycopg2
import os
from dotenv import load_dotenv

print('='*70)
print('COMPARING STATIC USERS WITH DATABASE')
print('='*70)

print(f'\nSTATIC USERS (employees.py): {len(static_users)}')
print('Employees:')
for email, user in static_users.items():
    print(f'  {email}: {user.get("name")} - {user.get("employee_number")}')

load_dotenv()
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    port=int(os.getenv('DB_PORT', '5432')),
    database=os.getenv('DB_NAME', 'attendance_db'),
    user=os.getenv('DB_USER', 'zugo_attendance'),
    password=os.getenv('DB_PASSWORD', '')
)
cursor = conn.cursor()

cursor.execute('SELECT COUNT(*) FROM employee_details')
total = cursor.fetchone()[0]
print(f'\nDATABASE EMPLOYEES: {total}')

cursor.execute('SELECT email, name, employee_number FROM employee_details ORDER BY name')
print('In Database:')
db_emails = set()
for email, name, emp_num in cursor.fetchall():
    db_emails.add(email)
    print(f'  {email}: {name} - {emp_num}')

print('\n' + '='*70)
print('MISSING FROM DATABASE:')
print('='*70)
missing = []
for email in static_users:
    if email not in db_emails:
        user = static_users[email]
        missing.append(email)
        print(f'  {email}: {user.get("name")} - {user.get("employee_number")}')

if not missing:
    print('  None - All employees are in the database!')

cursor.close()
conn.close()
