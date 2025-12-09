-- Migration: Add support_requests table for Help & Support feature
-- This table stores user support requests and issues

IF OBJECT_ID('dbo.support_requests', 'U') IS NULL
BEGIN
  CREATE TABLE dbo.support_requests (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(255) NOT NULL,
    email NVARCHAR(255) NOT NULL,
    user_id NVARCHAR(50) NULL,
    user_type NVARCHAR(20) NULL CHECK (user_type IN ('candidate', 'hr', 'guest') OR user_type IS NULL),
    subject NVARCHAR(500) NOT NULL,
    message NVARCHAR(MAX) NOT NULL,
    status NVARCHAR(50) DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved', 'closed')),
    priority NVARCHAR(20) DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    created_at DATETIME2 DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2 DEFAULT SYSUTCDATETIME(),
    resolved_at DATETIME2 NULL,
    admin_notes NVARCHAR(MAX) NULL
  );
  
  CREATE INDEX IX_support_requests_email ON dbo.support_requests(email);
  CREATE INDEX IX_support_requests_user_id ON dbo.support_requests(user_id);
  CREATE INDEX IX_support_requests_status ON dbo.support_requests(status);
  CREATE INDEX IX_support_requests_created_at ON dbo.support_requests(created_at DESC);
END;
GO

