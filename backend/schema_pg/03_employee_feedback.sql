-- -----------------------------------------------------------------------------
-- employee_feedback: Internal HRMS testing feedback (bugs, features, general)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS employee_feedback (
    id SERIAL PRIMARY KEY,
    employee_name VARCHAR(255) NOT NULL,
    employee_id VARCHAR(50) NULL,
    department VARCHAR(255) NULL,
    feedback_type VARCHAR(50) NOT NULL CHECK (feedback_type IN ('Bug Report', 'Feature Request', 'General Feedback', 'Appreciation')),
    module VARCHAR(255) NULL,
    severity VARCHAR(20) NULL CHECK (severity IN ('Low', 'Medium', 'High', 'Critical') OR severity IS NULL),
    description TEXT NOT NULL,
    screenshot_path VARCHAR(1000) NULL,
    status VARCHAR(20) DEFAULT 'open' CHECK (status IN ('open', 'reviewed', 'resolved')),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS IX_employee_feedback_created_at ON employee_feedback(created_at DESC);
CREATE INDEX IF NOT EXISTS IX_employee_feedback_feedback_type ON employee_feedback(feedback_type);
CREATE INDEX IF NOT EXISTS IX_employee_feedback_module ON employee_feedback(module);
CREATE INDEX IF NOT EXISTS IX_employee_feedback_status ON employee_feedback(status);
CREATE INDEX IF NOT EXISTS IX_employee_feedback_severity ON employee_feedback(severity);
