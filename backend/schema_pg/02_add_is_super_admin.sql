-- Add is_super_admin to hr_signup (for existing databases that ran 01_schema before this column existed).
-- To grant super admin access to an HR user, run: UPDATE hr_signup SET is_super_admin = true WHERE email = 'their@email.com';
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = current_schema() AND table_name = 'hr_signup' AND column_name = 'is_super_admin'
  ) THEN
    ALTER TABLE hr_signup ADD COLUMN is_super_admin BOOLEAN DEFAULT false;
  END IF;
END $$;
