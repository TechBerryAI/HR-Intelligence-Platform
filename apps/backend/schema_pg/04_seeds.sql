-- =============================================================================
-- 04_seeds.sql — consolidated from: 06_seed_admin_accounts.sql, 07_seed_ceo_account.sql
-- =============================================================================


-- >>> BEGIN 06_seed_admin_accounts.sql
-- Seed Head of HR account. Edit DECLARE block before deploy.
DO $$
DECLARE
  head_email   text := 'chetan.gore@techberryinfotech.com';
  head_pass    text := 'P@ssw0rd';
  head_name    text := 'Chetan Gore';
  head_company text := 'Techberry Infotech Pvt. Ltd.';
  next_hrid    text;
BEGIN
  IF EXISTS (SELECT 1 FROM hr_signup WHERE LOWER(TRIM(email)) = LOWER(TRIM(head_email))) THEN
    UPDATE hr_signup SET role = 'HEAD_HR', password = crypt(head_pass, gen_salt('bf'))
    WHERE LOWER(TRIM(email)) = LOWER(TRIM(head_email));
  ELSE
    SELECT 'HRID' || LPAD((COALESCE(MAX(CAST(SUBSTRING(hrid FROM 5) AS INTEGER)), 0) + 1)::text, 3, '0')
    INTO next_hrid FROM hr_signup WHERE hrid ~ '^HRID[0-9]+$';
    INSERT INTO hr_signup (hrid, full_name, email, company, password, role)
    VALUES (next_hrid, head_name, head_email, head_company, crypt(head_pass, gen_salt('bf')), 'HEAD_HR');
  END IF;
END $$;
-- <<< END 06_seed_admin_accounts.sql

-- >>> BEGIN 07_seed_ceo_account.sql
-- Seed CEO executive account (read-only analytics). Edit DECLARE block before deploy.
DO $$
DECLARE
  ceo_email   text := 'unmesh.tari@techberryinfotech.com';
  ceo_pass    text := 'P@ssw0rd';
  ceo_name    text := 'Unmesh Tari';
  ceo_company text := 'Techberry Infotech Pvt. Ltd.';
  next_hrid   text;
BEGIN
  IF EXISTS (SELECT 1 FROM hr_signup WHERE LOWER(TRIM(email)) = LOWER(TRIM(ceo_email))) THEN
    UPDATE hr_signup
    SET role = 'CEO', password = crypt(ceo_pass, gen_salt('bf'))
    WHERE LOWER(TRIM(email)) = LOWER(TRIM(ceo_email));
  ELSE
    SELECT 'HRID' || LPAD((COALESCE(MAX(CAST(SUBSTRING(hrid FROM 5) AS INTEGER)), 0) + 1)::text, 3, '0')
    INTO next_hrid FROM hr_signup WHERE hrid ~ '^HRID[0-9]+$';
    INSERT INTO hr_signup (hrid, full_name, email, company, password, role)
    VALUES (next_hrid, ceo_name, ceo_email, ceo_company, crypt(ceo_pass, gen_salt('bf')), 'CEO');
  END IF;
END $$;
-- <<< END 07_seed_ceo_account.sql
