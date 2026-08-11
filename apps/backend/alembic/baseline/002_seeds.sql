-- Seed accounts (env-gated passwords). Same semantics as former schema_pg/04_seeds.sql.
-- =============================================================================
-- 04_seeds.sql — seed HEAD_HR / CEO accounts (NO plaintext passwords in-repo)
-- =============================================================================
-- Passwords MUST be supplied via environment at apply time:
--   SEED_HEAD_HR_PASSWORD, SEED_CEO_PASSWORD
-- If unset, existing password hashes are preserved; new rows get a random
-- unusable bcrypt placeholder (force password reset / change via app).
-- Prefer creating staff accounts through the product UI in production.
-- =============================================================================

-- >>> BEGIN 06_seed_admin_accounts.sql
DO $$
DECLARE
  head_email   text := COALESCE(NULLIF(current_setting('app.seed_head_hr_email', true), ''),
                                'chetan.gore@techberryinfotech.com');
  head_pass    text := NULLIF(current_setting('app.seed_head_hr_password', true), '');
  head_name    text := 'Chetan Gore';
  head_company text := 'Techberry Infotech Pvt. Ltd.';
  next_hrid    text;
  pass_hash    text;
BEGIN
  IF head_pass IS NOT NULL AND length(head_pass) > 0 THEN
    pass_hash := crypt(head_pass, gen_salt('bf'));
  ELSE
    -- Unusable placeholder; rotate via /api/change-password or forgot-password
    pass_hash := crypt(gen_random_uuid()::text, gen_salt('bf'));
  END IF;

  IF EXISTS (SELECT 1 FROM hr_signup WHERE LOWER(TRIM(email)) = LOWER(TRIM(head_email))) THEN
    UPDATE hr_signup
    SET role = 'HEAD_HR',
        password = CASE
          WHEN head_pass IS NOT NULL AND length(head_pass) > 0 THEN pass_hash
          ELSE password
        END
    WHERE LOWER(TRIM(email)) = LOWER(TRIM(head_email));
  ELSE
    SELECT 'HRID' || LPAD((COALESCE(MAX(CAST(SUBSTRING(hrid FROM 5) AS INTEGER)), 0) + 1)::text, 3, '0')
    INTO next_hrid FROM hr_signup WHERE hrid ~ '^HRID[0-9]+$';
    INSERT INTO hr_signup (hrid, full_name, email, company, password, role)
    VALUES (next_hrid, head_name, head_email, head_company, pass_hash, 'HEAD_HR');
  END IF;
END $$;
-- <<< END 06_seed_admin_accounts.sql

-- >>> BEGIN 07_seed_ceo_account.sql
DO $$
DECLARE
  ceo_email   text := COALESCE(NULLIF(current_setting('app.seed_ceo_email', true), ''),
                               'unmesh.tari@techberryinfotech.com');
  ceo_pass    text := NULLIF(current_setting('app.seed_ceo_password', true), '');
  ceo_name    text := 'Unmesh Tari';
  ceo_company text := 'Techberry Infotech Pvt. Ltd.';
  next_hrid   text;
  pass_hash   text;
BEGIN
  IF ceo_pass IS NOT NULL AND length(ceo_pass) > 0 THEN
    pass_hash := crypt(ceo_pass, gen_salt('bf'));
  ELSE
    pass_hash := crypt(gen_random_uuid()::text, gen_salt('bf'));
  END IF;

  IF EXISTS (SELECT 1 FROM hr_signup WHERE LOWER(TRIM(email)) = LOWER(TRIM(ceo_email))) THEN
    UPDATE hr_signup
    SET role = 'CEO',
        password = CASE
          WHEN ceo_pass IS NOT NULL AND length(ceo_pass) > 0 THEN pass_hash
          ELSE password
        END
    WHERE LOWER(TRIM(email)) = LOWER(TRIM(ceo_email));
  ELSE
    SELECT 'HRID' || LPAD((COALESCE(MAX(CAST(SUBSTRING(hrid FROM 5) AS INTEGER)), 0) + 1)::text, 3, '0')
    INTO next_hrid FROM hr_signup WHERE hrid ~ '^HRID[0-9]+$';
    INSERT INTO hr_signup (hrid, full_name, email, company, password, role)
    VALUES (next_hrid, ceo_name, ceo_email, ceo_company, pass_hash, 'CEO');
  END IF;
END $$;
-- <<< END 07_seed_ceo_account.sql

-- Attach seed HEAD_HR / CEO to organizations from their company name (idempotent)
DO $$
DECLARE
  head_email   text := COALESCE(NULLIF(current_setting('app.seed_head_hr_email', true), ''),
                                'chetan.gore@techberryinfotech.com');
  ceo_email    text := COALESCE(NULLIF(current_setting('app.seed_ceo_email', true), ''),
                               'unmesh.tari@techberryinfotech.com');
  org_uuid     uuid;
  company_name text;
  company_slug text;
BEGIN
  -- Prefer company from HEAD_HR row
  SELECT company INTO company_name
  FROM hr_signup
  WHERE LOWER(TRIM(email)) = LOWER(TRIM(head_email))
  LIMIT 1;

  IF company_name IS NULL OR length(trim(company_name)) = 0 THEN
    SELECT company INTO company_name
    FROM hr_signup
    WHERE LOWER(TRIM(email)) = LOWER(TRIM(ceo_email))
    LIMIT 1;
  END IF;

  IF company_name IS NULL OR length(trim(company_name)) = 0 THEN
    company_name := 'Techberry Infotech Pvt. Ltd.';
  END IF;

  company_slug := trim(both '-' from lower(regexp_replace(
    regexp_replace(lower(company_name),
      '( private limited| pvt\. ltd\.| pvt ltd\.| pvt\. ltd| pvt ltd| ltd\.| ltd| inc\.| inc| llc)$',
      '', 'i'),
    '[^a-z0-9]+', '-', 'g')));
  IF company_slug IS NULL OR company_slug = '' THEN
    company_slug := 'org';
  END IF;

  INSERT INTO organizations (name, slug)
  VALUES (company_name, company_slug)
  ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
  RETURNING id INTO org_uuid;

  IF org_uuid IS NULL THEN
    SELECT id INTO org_uuid FROM organizations WHERE slug = company_slug;
  END IF;

  IF org_uuid IS NOT NULL THEN
    UPDATE hr_signup
    SET organization_id = org_uuid,
        company = COALESCE(NULLIF(trim(company), ''), company_name)
    WHERE LOWER(TRIM(email)) IN (LOWER(TRIM(head_email)), LOWER(TRIM(ceo_email)))
      AND (organization_id IS NULL OR organization_id = org_uuid);

    UPDATE jobs j
    SET organization_id = org_uuid
    FROM hr_signup h
    WHERE j.posted_by = h.hrid
      AND h.organization_id = org_uuid
      AND j.organization_id IS NULL;
  END IF;
END $$;
