-- Migration: Add ATS workflow fields to applications table
-- This supports the n8n ATS matching workflow integration

-- Add match_score column
IF OBJECT_ID('dbo.applications', 'U') IS NOT NULL
BEGIN
  IF COL_LENGTH('dbo.applications', 'match_score') IS NULL
  BEGIN
    ALTER TABLE dbo.applications ADD match_score FLOAT NULL;
  END
END;
GO

-- Add shortlisted column
IF OBJECT_ID('dbo.applications', 'U') IS NOT NULL
BEGIN
  IF COL_LENGTH('dbo.applications', 'shortlisted') IS NULL
  BEGIN
    ALTER TABLE dbo.applications ADD shortlisted BIT NULL DEFAULT 0;
  END
END;
GO

-- Add ats_reasoning column
IF OBJECT_ID('dbo.applications', 'U') IS NOT NULL
BEGIN
  IF COL_LENGTH('dbo.applications', 'ats_reasoning') IS NULL
  BEGIN
    ALTER TABLE dbo.applications ADD ats_reasoning NVARCHAR(MAX) NULL;
  END
END;
GO

-- Update status column to support new statuses
-- Existing values: 'pending', new values: 'applied', 'shortlisted', 'rejected', 'interview_scheduled'
-- No constraint changes needed as status is already NVARCHAR(50)

-- Add index for ATS queries
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_applications_shortlisted' AND object_id = OBJECT_ID('dbo.applications'))
BEGIN
  CREATE INDEX IX_applications_shortlisted ON dbo.applications(shortlisted, match_score DESC);
END;
GO

-- Add index for status-based queries
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_applications_status' AND object_id = OBJECT_ID('dbo.applications'))
BEGIN
  CREATE INDEX IX_applications_status ON dbo.applications(status, applied_at DESC);
END;
GO

PRINT 'ATS fields migration completed successfully';

