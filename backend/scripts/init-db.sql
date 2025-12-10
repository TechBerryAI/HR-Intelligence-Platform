-- =============================================================================
-- HR Job Portal - Database Initialization Script
-- =============================================================================
-- 
-- This script creates the JobPortal database for new installations.
-- Tables are created automatically by the Flask application on startup.
--
-- USAGE:
--   SQL Server Management Studio:
--     Open this file and execute it
--   
--   Command line (sqlcmd):
--     sqlcmd -S localhost -U sa -P YourPassword -i init-db.sql
--
--   Docker:
--     This runs automatically when the SQL Server container starts
--
-- =============================================================================

-- Create the database if it doesn't exist
IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'JobPortal')
BEGIN
    CREATE DATABASE JobPortal;
    PRINT 'Database JobPortal created successfully.';
END
ELSE
BEGIN
    PRINT 'Database JobPortal already exists.';
END
GO

-- Switch to the new database
USE JobPortal;
GO

-- Create a login for the application (optional - only if not using sa)
-- Uncomment and modify if you want a separate application user
/*
IF NOT EXISTS (SELECT * FROM sys.server_principals WHERE name = 'JobPortalApp')
BEGIN
    CREATE LOGIN JobPortalApp WITH PASSWORD = 'YourAppPassword123!';
    PRINT 'Login JobPortalApp created.';
END
GO

USE JobPortal;
GO

IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = 'JobPortalApp')
BEGIN
    CREATE USER JobPortalApp FOR LOGIN JobPortalApp;
    ALTER ROLE db_owner ADD MEMBER JobPortalApp;
    PRINT 'User JobPortalApp created and granted db_owner role.';
END
GO
*/

PRINT '';
PRINT '=============================================================================';
PRINT 'Database initialization complete!';
PRINT '';
PRINT 'The Flask application will create all required tables on first startup.';
PRINT '=============================================================================';
GO

