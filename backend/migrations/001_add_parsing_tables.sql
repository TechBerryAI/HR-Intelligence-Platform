-- Migration: Add tables for Resume/JD Parsing workflow
-- raw_files: stores original uploaded files
-- parsed_resumes: stores parsed resume data in TOON format
-- parsed_jds: stores parsed job description data in TOON format

-- Create raw_files table
IF OBJECT_ID('dbo.raw_files', 'U') IS NULL
BEGIN
  CREATE TABLE dbo.raw_files (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    uploader_id NVARCHAR(50) NOT NULL,
    uploader_role NVARCHAR(20) NOT NULL CHECK (uploader_role IN ('candidate', 'admin')),
    original_filename NVARCHAR(255) NOT NULL,
    storage_url NVARCHAR(1000) NOT NULL,
    mime_type NVARCHAR(100) NOT NULL,
    file_hash NVARCHAR(64) NOT NULL,
    size_bytes BIGINT NOT NULL,
    created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_raw_files_hash_uploader UNIQUE (file_hash, uploader_id)
  );
  
  CREATE INDEX IX_raw_files_uploader ON dbo.raw_files(uploader_id, uploader_role);
  CREATE INDEX IX_raw_files_hash ON dbo.raw_files(file_hash);
END;
GO

-- Create parsed_resumes table
IF OBJECT_ID('dbo.parsed_resumes', 'U') IS NULL
BEGIN
  CREATE TABLE dbo.parsed_resumes (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    raw_file_id UNIQUEIDENTIFIER NOT NULL,
    candidate_id NVARCHAR(20) NULL,
    toon NVARCHAR(MAX) NOT NULL,  -- JSON data
    full_text NVARCHAR(MAX) NOT NULL,
    confidence FLOAT NOT NULL,
    model_version NVARCHAR(100) NOT NULL,
    created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_parsed_resumes_raw_file FOREIGN KEY (raw_file_id) 
      REFERENCES dbo.raw_files(id) ON DELETE CASCADE,
    CONSTRAINT FK_parsed_resumes_candidate FOREIGN KEY (candidate_id) 
      REFERENCES dbo.candidate_signup(cid) ON DELETE SET NULL
  );
  
  CREATE INDEX IX_parsed_resumes_raw_file ON dbo.parsed_resumes(raw_file_id);
  CREATE INDEX IX_parsed_resumes_candidate ON dbo.parsed_resumes(candidate_id);
  CREATE INDEX IX_parsed_resumes_confidence ON dbo.parsed_resumes(confidence);
END;
GO

-- Create parsed_jds table
IF OBJECT_ID('dbo.parsed_jds', 'U') IS NULL
BEGIN
  CREATE TABLE dbo.parsed_jds (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    raw_file_id UNIQUEIDENTIFIER NOT NULL,
    job_id NVARCHAR(20) NULL,
    toon NVARCHAR(MAX) NOT NULL,  -- JSON data
    full_text NVARCHAR(MAX) NOT NULL,
    confidence FLOAT NOT NULL,
    model_version NVARCHAR(100) NOT NULL,
    created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_parsed_jds_raw_file FOREIGN KEY (raw_file_id) 
      REFERENCES dbo.raw_files(id) ON DELETE CASCADE,
    CONSTRAINT FK_parsed_jds_job FOREIGN KEY (job_id) 
      REFERENCES dbo.jobs(jdid) ON DELETE SET NULL
  );
  
  CREATE INDEX IX_parsed_jds_raw_file ON dbo.parsed_jds(raw_file_id);
  CREATE INDEX IX_parsed_jds_job ON dbo.parsed_jds(job_id);
  CREATE INDEX IX_parsed_jds_confidence ON dbo.parsed_jds(confidence);
END;
GO

-- Add indexes for performance
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_raw_files_created_at' AND object_id = OBJECT_ID('dbo.raw_files'))
BEGIN
  CREATE INDEX IX_raw_files_created_at ON dbo.raw_files(created_at DESC);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_parsed_resumes_created_at' AND object_id = OBJECT_ID('dbo.parsed_resumes'))
BEGIN
  CREATE INDEX IX_parsed_resumes_created_at ON dbo.parsed_resumes(created_at DESC);
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_parsed_jds_created_at' AND object_id = OBJECT_ID('dbo.parsed_jds'))
BEGIN
  CREATE INDEX IX_parsed_jds_created_at ON dbo.parsed_jds(created_at DESC);
END;
GO

PRINT 'Parsing tables migration completed successfully';

