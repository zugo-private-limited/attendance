-- PostgreSQL Setup Script for Attendance System
-- Run this as the postgres superuser

-- Create the user with LOGIN permission
CREATE ROLE zugo_attendance WITH LOGIN PASSWORD 'Zugo@123';

-- Create the database
CREATE DATABASE attendance_db OWNER zugo_attendance;

-- Grant all privileges on the database to the user
GRANT ALL PRIVILEGES ON DATABASE attendance_db TO zugo_attendance;

-- Connect to the database and grant schema permissions
\c attendance_db

-- Grant schema permissions
GRANT ALL PRIVILEGES ON SCHEMA public TO zugo_attendance;

-- Grant default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO zugo_attendance;