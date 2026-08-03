-- Interview scheduling + AI interviewer support (extends interviews scaffold)

ALTER TABLE interviews ALTER COLUMN assigned_to DROP NOT NULL;

ALTER TABLE interviews DROP CONSTRAINT IF EXISTS interviews_status_check;
ALTER TABLE interviews ADD CONSTRAINT interviews_status_check
    CHECK (status IN ('Scheduled', 'InProgress', 'Completed', 'Cancelled', 'Rescheduled'));

ALTER TABLE interviews ADD COLUMN IF NOT EXISTS interviewer_type VARCHAR(20) NOT NULL DEFAULT 'ai';
ALTER TABLE interviews ADD COLUMN IF NOT EXISTS duration_minutes INTEGER DEFAULT 30;
ALTER TABLE interviews ADD COLUMN IF NOT EXISTS invite_token VARCHAR(64);
ALTER TABLE interviews ADD COLUMN IF NOT EXISTS meeting_link TEXT;
ALTER TABLE interviews ADD COLUMN IF NOT EXISTS questions_json JSONB;
ALTER TABLE interviews ADD COLUMN IF NOT EXISTS answers_json JSONB;
ALTER TABLE interviews ADD COLUMN IF NOT EXISTS overall_score NUMERIC(5,2);
ALTER TABLE interviews ADD COLUMN IF NOT EXISTS score_summary TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'interviews_interviewer_type_check'
    ) THEN
        ALTER TABLE interviews
            ADD CONSTRAINT interviews_interviewer_type_check
            CHECK (interviewer_type IN ('human', 'ai'));
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS UX_interviews_invite_token
    ON interviews(invite_token)
    WHERE invite_token IS NOT NULL;
