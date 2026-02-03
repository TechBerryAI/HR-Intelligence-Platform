-- Migration: Add detailed ATS analysis JSON field
-- This stores structured matching data from n8n (skills, education, experience, etc.)

-- Add ats_analysis column to store detailed structured matching data
-- Note: NVARCHAR(MAX) cannot be used in a normal index in SQL Server, so no index is created.
IF OBJECT_ID('dbo.applications', 'U') IS NOT NULL
BEGIN
  IF COL_LENGTH('dbo.applications', 'ats_analysis') IS NULL
  BEGIN
    ALTER TABLE dbo.applications ADD ats_analysis NVARCHAR(MAX) NULL;
    PRINT 'Added ats_analysis column to applications table';
  END
END;
GO

PRINT 'Detailed ATS analysis migration completed successfully';

