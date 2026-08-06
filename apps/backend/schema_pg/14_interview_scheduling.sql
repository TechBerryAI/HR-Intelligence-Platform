-- Interview scheduling: extend interviews, add interview_slots, per-recruiter Google OAuth

-- -----------------------------------------------------------------------------
-- interviews extensions
-- -----------------------------------------------------------------------------
ALTER TABLE interviews ADD COLUMN IF NOT EXISTS calendar_event_id TEXT NULL;
ALTER TABLE interviews ADD COLUMN IF NOT EXISTS invite_expires_at TIMESTAMPTZ NULL;
ALTER TABLE interviews ADD COLUMN IF NOT EXISTS interviewer_hrid VARCHAR(20) NULL REFERENCES hr_signup(hrid);

ALTER TABLE interviews DROP CONSTRAINT IF EXISTS interviews_status_check;
ALTER TABLE interviews ADD CONSTRAINT interviews_status_check
    CHECK (status IN ('Invited', 'Scheduled', 'InProgress', 'Completed', 'Cancelled', 'Rescheduled'));

CREATE UNIQUE INDEX IF NOT EXISTS UX_interviews_open_application
    ON interviews(application_id)
    WHERE status IN ('Invited', 'Scheduled');

-- -----------------------------------------------------------------------------
-- interview_slots
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS interview_slots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    recruiter_hrid VARCHAR(20) NOT NULL REFERENCES hr_signup(hrid),
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    is_booked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS IX_interview_slots_interview_booked
    ON interview_slots(interview_id, is_booked);

CREATE INDEX IF NOT EXISTS IX_interview_slots_recruiter_start
    ON interview_slots(recruiter_hrid, start_time);

-- -----------------------------------------------------------------------------
-- oauth_tokens: per-recruiter Google Calendar
-- -----------------------------------------------------------------------------
ALTER TABLE oauth_tokens ADD COLUMN IF NOT EXISTS hrid VARCHAR(20) NULL REFERENCES hr_signup(hrid);

ALTER TABLE oauth_tokens DROP CONSTRAINT IF EXISTS uq_oauth_tokens_company_provider;

CREATE UNIQUE INDEX IF NOT EXISTS UX_oauth_tokens_provider_hrid
    ON oauth_tokens(provider, hrid)
    WHERE hrid IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS UX_oauth_tokens_company_provider_no_hrid
    ON oauth_tokens(company_key, provider)
    WHERE hrid IS NULL;
