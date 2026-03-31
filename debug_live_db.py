import psycopg2
import psycopg2.extras

DB_HOST = "dpg-d5b0dv4hg0os73d60l4g-a.singapore-postgres.render.com"
DB_PORT = 5432
DB_USER = "zugoweb"
DB_PASSWORD = "BtGjE2SkIO5ISJgVtpyXXPR1RXBWKWVQ"
DB_NAME = "zugo_attendance_c3pn"

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME,
    sslmode='require'
)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

cur.execute('select email,name,office_id,total_working,total_leave from employee_details order by name')
rows = cur.fetchall()
print('EMPLOYEES', len(rows))
for r in rows:
    print(r)

print('\nSAMPLE CHECKIN DATES FOR NANTHAKUMAR T')
cur.execute("select email from employee_details where name = %s", ('NANDHAKUMAR T',))
email_row = cur.fetchone()
if email_row:
    email = email_row['email']
    print('Employee email:', email)
    cur.execute("select count(*) as cnt from attendance where user_email = %s", (email,))
    print('Total attendance rows:', cur.fetchone()['cnt'])
    cur.execute("""
    select action, event_time at time zone 'Asia/Kolkata' as ist_time, date(event_time at time zone 'Asia/Kolkata') as ist_date
    from attendance
    where user_email = %s
    order by event_time
    """, (email,))
    rows = cur.fetchall()
    print(len(rows), 'rows')
    for r in rows:
        print(r)
    print('\nGROUP BY DATE for 2026-03-21 to 2026-03-30')
    cur.execute("""
    select date(event_time at time zone 'Asia/Kolkata') as ist_date,
           count(*) as row_count,
           sum(case when action='check-in' then 1 else 0 end) as checkins
    from attendance
    where user_email = %s
      and date(event_time at time zone 'Asia/Kolkata') between '2026-03-21' and '2026-03-30'
    group by date(event_time at time zone 'Asia/Kolkata')
    order by ist_date
    """, (email,))
    for r in cur.fetchall():
        print(r)
    cur.execute("""
    select count(distinct date(event_time at time zone 'Asia/Kolkata')) as distinct_checkin_count
    from attendance
    where user_email = %s
      and action = 'check-in'
      and date(event_time at time zone 'Asia/Kolkata') between '2026-03-21' and '2026-03-30'
    """, (email,))
    print('distinct check-in count', cur.fetchone()['distinct_checkin_count'])
else:
    print('NANDHAKUMAR T not found in employee_details')

conn.close()
