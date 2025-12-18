-- MySQL User Setup Script
-- This script creates or updates the 'zugo' user with full database privileges

-- Drop existing user if exists (for reset)
DROP USER IF EXISTS 'zugo'@'localhost';

-- Create new user with password
CREATE USER 'zugo'@'localhost' IDENTIFIED BY 'Zugo@123';

-- Grant all privileges on attendance database
GRANT ALL PRIVILEGES ON attendance.* TO 'zugo'@'localhost';

-- Grant privileges to create databases
GRANT CREATE ON *.* TO 'zugo'@'localhost';

-- Apply changes
FLUSH PRIVILEGES;

-- Verify user was created
SELECT User, Host FROM mysql.user WHERE User='zugo';

SHOW GRANTS FOR 'zugo'@'localhost';
