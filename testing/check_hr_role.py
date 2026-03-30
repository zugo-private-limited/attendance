import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    port=int(os.getenv('DB_PORT', '5432')),
    database=os.getenv('DB_NAME', 'attendance_db'),
    user=os.getenv('DB_USER', 'zugo_attendance'),
    password=os.getenv('DB_PASSWORD', '')
)
cursor = conn.cursor()

hr_email = 'zugopvtnetwork@gmail.com'
cursor.execute('SELECT name, job_role FROM employee_details WHERE email = %s', (hr_email,))
result = cursor.fetchone()
if result:
    print(f'HR Account: {result[0]}')
    print(f'Job Role: "{result[1]}"')
    is_hq_admin = 'HQ Admin' in str(result[1])
    print(f'Contains HQ Admin: {is_hq_admin}')
else:
    print('HR account not found')

cursor.close()
conn.close()
