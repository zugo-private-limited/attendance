-- Step 1: DELETE all records from employee_comments (no transactions needed)
DELETE FROM employee_comments;

-- Step 2: DELETE all records from attendance
DELETE FROM attendance;

-- Step 3: DELETE all records from employee_details (except we'll rebuild them)
DELETE FROM employee_details;

-- Step 4: RESET sequences to start from 1 again (optional but recommended)
ALTER SEQUENCE employee_comments_id_seq RESTART WITH 1;
ALTER SEQUENCE attendance_id_seq RESTART WITH 1;
ALTER SEQUENCE employee_details_id_seq RESTART WITH 1;

