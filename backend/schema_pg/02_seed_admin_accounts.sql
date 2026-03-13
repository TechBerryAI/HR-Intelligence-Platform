-- Add is_super_admin / is_head_hr columns if missing, then seed Super Admin and Head of HR.
-- Edit the DECLARE block below. Passwords are hashed with bcrypt (pgcrypto).
-- Re-run this script anytime to sync passwords from the script to the DB (updates existing users too).
DO $$
DECLARE
  -- Super Admin (full system access; login at /login/super-admin)
  super_email   text := 'unmesh.tari@techberryinfotech.com';
  super_pass    text := 'P@ssw0rd';
  super_name    text := 'Unmesh Tari';
  super_company text := 'Techberry Infotech Pvt. Ltd.';
  -- Head of HR (create/manage admins + HR features; login at /login/admin)
  head_email   text := 'chetan.gore@techberryinfotech.com';
  head_pass    text := 'P@ssw0rd';
  head_name    text := 'Chetan Gore';
  head_company text := 'Techberry Infotech Pvt. Ltd.';
  --
  next_hrid text;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = 'hr_signup' AND column_name = 'is_super_admin') THEN
    ALTER TABLE hr_signup ADD COLUMN is_super_admin BOOLEAN DEFAULT false;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = 'hr_signup' AND column_name = 'is_head_hr') THEN
    ALTER TABLE hr_signup ADD COLUMN is_head_hr BOOLEAN DEFAULT false;
  END IF;

  IF EXISTS (SELECT 1 FROM hr_signup WHERE LOWER(TRIM(email)) = LOWER(TRIM(super_email))) THEN
    UPDATE hr_signup SET is_super_admin = true, password = crypt(super_pass, gen_salt('bf')) WHERE LOWER(TRIM(email)) = LOWER(TRIM(super_email));
  ELSE
    SELECT 'HRID' || LPAD((COALESCE(MAX(CAST(SUBSTRING(hrid FROM 5) AS INTEGER)), 0) + 1)::text, 3, '0') INTO next_hrid FROM hr_signup WHERE hrid ~ '^HRID[0-9]+$';
    INSERT INTO hr_signup (hrid, full_name, email, company, password, is_super_admin)
    VALUES (next_hrid, super_name, super_email, super_company, crypt(super_pass, gen_salt('bf')), true);
  END IF;

  IF EXISTS (SELECT 1 FROM hr_signup WHERE LOWER(TRIM(email)) = LOWER(TRIM(head_email))) THEN
    UPDATE hr_signup SET is_head_hr = true, password = crypt(head_pass, gen_salt('bf')) WHERE LOWER(TRIM(email)) = LOWER(TRIM(head_email));
  ELSE
    SELECT 'HRID' || LPAD((COALESCE(MAX(CAST(SUBSTRING(hrid FROM 5) AS INTEGER)), 0) + 1)::text, 3, '0') INTO next_hrid FROM hr_signup WHERE hrid ~ '^HRID[0-9]+$';
    INSERT INTO hr_signup (hrid, full_name, email, company, password, is_head_hr)
    VALUES (next_hrid, head_name, head_email, head_company, crypt(head_pass, gen_salt('bf')), true);
  END IF;
END $$;
