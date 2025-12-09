-- Migration: Add detailed ATS analysis JSON field
-- This stores structured matching data from n8n (skills, education, experience, etc.)

-- Add ats_analysis column to store detailed structured matching data
IF OBJECT_ID('dbo.applications', 'U') IS NOT NULL
BEGIN
  IF COL_LENGTH('dbo.applications', 'ats_analysis') IS NULL
  BEGIN
    ALTER TABLE dbo.applications ADD ats_analysis NVARCHAR(MAX) NULL;
    PRINT 'Added ats_analysis column to applications table';
  END
END;
GO

-- Add index for JSON queries (SQL Server 2016+)
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_applications_ats_analysis' AND object_id = OBJECT_ID('dbo.applications'))
BEGIN
  CREATE INDEX IX_applications_ats_analysis ON dbo.applications(ats_analysis);
  PRINT 'Created index on ats_analysis column';
END;
GO

PRINT 'Detailed ATS analysis migration completed successfully';

