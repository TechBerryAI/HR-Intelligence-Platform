-- Add keywords column to jobs for JD-derived search/match terms
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'jobs' AND column_name = 'keywords'
    ) THEN
        ALTER TABLE jobs ADD COLUMN keywords TEXT NULL;
    END IF;
END $$;
