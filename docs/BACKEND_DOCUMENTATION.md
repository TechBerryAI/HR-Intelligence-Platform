# Backend Structure & Code Documentation

This document describes the backend directory structure, the purpose of each file and folder, and how the code works.

---

## 1. Backend Directory Structure

```
backend/
├── app.py                    # Flask app entry: config, CORS, mail, init_db, blueprints
├── env_validator.py          # Validates required env vars at startup
├── extensions.py             # Flask-Mail extension instance
├── db.py                     # PostgreSQL connection pool and query helpers
├── utils.py                  # JWT, password validation, auth decorators
├── auth.py                   # HR auth blueprint: signup, OTP, forgot/reset, login, refresh, logout
├── jobs.py                   # Jobs blueprint: CRUD, applications list/resume/status, jdid
├── candidate.py              # Candidate blueprint: profile GET/POST, resume, logout, change-password
├── applications.py           # Applications blueprint: apply, my applications, ATS callback
├── sessions_routes.py        # Sessions blueprint: my-sessions, my-history, logout-session, logout-all
├── parsing_routes.py         # Parsing blueprint: parse resume/JD, get parsed by id
├── support.py                # Support blueprint: submit, my-requests, all, by id, status
├── feedback_routes.py        # Feedback blueprint: submit, list, status (HRMS testing feedback)
├── super_admin.py            # Super-admin blueprint: login, stats, admins, candidates, jobs, applications
├── toon.py                   # TOON schema load/dump (JSON) for parsed resume/JD
├── text_extraction.py        # Extract text from PDF/DOC/DOCX
├── parsing_utils.py          # File hash, store raw file, store parsed resume/JD, cache lookup
├── llm_service.py            # LLM calls (e.g. Grok/XAI) for parsing and classification
├── llm_key_manager.py        # API key rotation for LLM
├── matching.py               # Matching percentage logic (e.g. for applications)
├── sessions_service.py       # Session tracking, login history, logout
├── requirements.txt
├── gunicorn.conf.py          # Gunicorn config for production
├── .env.example
├── models/
│   ├── __init__.py           # init_models(), get_session() for SQLAlchemy
│   ├── hr_auth.py            # HRAuth model (OTP verification for HR)
│   └── candidate_auth.py     # CandidateAuth model (unused by routes; candidate uses raw SQL)
├── routes/
│   ├── __init__.py
│   └── simple_candidate_auth.py  # Candidate signup, verify-otp, resend-otp, login (no SQLAlchemy)
├── modules/
│   └── admin/
│       ├── __init__.py
│       └── routes.py         # Bulk-parse upload/progress/download, job-matches
├── helpers/
│   ├── __init__.py
│   ├── email_utils.py        # send_notification_email
│   ├── email_templates.py    # HTML templates for emails
│   ├── otp_utils.py          # generate_otp, send_email_otp, parse_otp_expiry, timezone helpers
│   └── mail_send.py          # Low-level mail send
├── services/
│   ├── __init__.py
│   ├── ats_service.py        # match_candidate_to_job (internal ATS or external API)
│   ├── candidate_notification_service.py  # Email on profile viewed / shortlisted / rejected
│   ├── bulk_parsing_service.py   # Proxy to BULK_PARSER_URL (upload, progress, download)
│   └── local_bulk_parser.py  # In-process bulk parsing fallback
└── schema_pg/
    ├── 01_schema.sql        # Main tables (hr_signup, jobs, applications, parsed_*, etc.)
    ├── 02_seed_admin_accounts.sql
    └── 03_employee_feedback.sql
```

---

## 2. App Entry and Configuration

### 2.1 `app.py`

**What it does:**

1. **Load env:** `load_dotenv` from the backend directory so `.env` is found regardless of current working directory.

2. **Validate env:** Runs `EnvValidator.validate()`. If invalid, prints errors and exits. If valid but with warnings, prints warnings and continues.

3. **Flask app:** Creates `Flask(__name__)`, sets `JWT_SECRET` from env, configures Flask-Mail (server, port, TLS, username, password, suppress send, timeout, retries). Validates that `MAIL_USERNAME` looks like an email when sending is enabled. Sets `app.url_map.strict_slashes = False` to avoid redirects that can break CORS preflight.

4. **CORS:** Builds allowed origins from `FRONTEND_URLS` or `FRONTEND_URL` or default localhost/127.0.0.1 and local IP. Uses `CORS(app, resources={r"/*": {...}})` with that list, methods GET/POST/PUT/PATCH/DELETE/OPTIONS/HEAD, allow_headers including Authorization and Content-Type, supports_credentials True, max_age 3600.

5. **Extensions:** `mail.init_app(app)`.

6. **Models:** `init_models()` (SQLAlchemy).

7. **Database:** `init_db()` is called at startup (not lazy) so the first request does not wait for schema run. Runs `run_migrations()` from db.py.

8. **Routes:**  
   - `GET /` — API root JSON.  
   - `GET /health` — Health status and optional bulk_parser reachability.  
   - `GET|OPTIONS /api/test-cors` — CORS test.  
   Then registers blueprints: auth_bp (`/api`), jobs_bp (`/api/jobs`), simple_candidate_auth_bp (`/api/candidate`), candidate_bp (`/api/candidate`), applications_bp (`/api/applications`), sessions_bp (`/api/sessions`), parsing_bp (`/api`), support_bp (`/api/support`), feedback_bp (`/api/feedback`), admin_bp (`/api/admin`), super_admin_bp (`/api/super-admin`).

9. **Run:** If `__name__ == '__main__'`, reads PORT and FLASK_DEBUG, optionally disables reloader, runs `app.run(host='0.0.0.0', port=..., debug=..., use_reloader=..., threaded=True)`.

---

## 3. Database Layer

### 3.1 `db.py`

**Purpose:** Single place for PostgreSQL connectivity and query execution. Uses psycopg (v3); placeholders are normalized from `?` to `%s`.

**Connection:**

- **DATABASE_URL:** From env or built from POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD (with quote_plus for user/pass).
- **ConnectionPool:** A queue of connections (default size 5). `get_connection(timeout)` returns a connection: if pool not initialized, fills it; gets from queue or creates new; validates with `SELECT 1`; on validation failure closes and creates new. `return_connection(conn)` puts back in pool if not full, else closes.
- **get_conn():** Context manager that gets a connection, yields it, commits on success, rollbacks on exception, and always returns the connection to the pool.

**Query helpers:**

- **db_run(query, params):** Replaces `?` with `%s`, executes in a new connection, returns `{ lastID, changes }`. If the query contains `RETURNING`, lastID is taken from the first returned row (e.g. for INSERT).
- **db_get(query, params):** Same replacement, uses cursor with dict_row, returns the first row as a dict or None.
- **db_all(query, params):** Returns all rows as a list of dicts.

**Migrations:**

- **run_migrations():** Reads all `.sql` files from `schema_pg/` in order, strips comments and empty lines, splits by `;` (keeping `DO $$ ... END $$;` as one statement), executes each. Then ensures columns `is_super_admin` and `is_head_hr` exist on `hr_signup` (idempotent ALTER).
- **init_db():** Just calls `run_migrations()`.

---

## 4. Auth and Authorization Helpers

### 4.1 `utils.py`

**Password:** `validate_password_strength(password)` — enforces min length 8, at least one upper, one lower, one digit, one special character. Returns `(True, None)` or `(False, error_message)`.

**JWT:**

- `JWT_SECRET`, `JWT_ACCESS_EXPIRY_SECONDS`, `JWT_REFRESH_EXPIRY_SECONDS` from env (defaults: 1h access, 30d refresh).
- `build_jwt_payload(identity_dict, refresh=False)` — copies identity, adds `type` ('access' or 'refresh'), `iat`, `exp`.

**Decorators:**

- **authenticate_token(f):** Reads `Authorization: Bearer <token>`. If no token, returns 401. Decodes JWT with JWT_SECRET; if `type == 'refresh'` returns 403 (refresh token cannot be used as access). Sets `request.user` to the decoded payload and calls `f`.
- **optional_authenticate_token(f):** If no Bearer header, sets `request.user = None` and calls `f`. If Bearer present, same decode as above; invalid/expired/refresh-type returns 401.
- **require_hr(f):** Must be used after authenticate_token. Checks `request.user` and that `role` is 'HR' or 'head_hr'; else 403.
- **require_candidate(f):** Requires `request.user` and `role == 'candidate'`; else 403.
- **require_super_admin(f):** Requires `request.user` and `role == 'super_admin'`; else 403.
- **require_head_hr(f):** Requires role 'head_hr' or 'super_admin'; else 403.

---

## 5. Auth Blueprint (HR) — `auth.py`

**Prefix:** `/api` (so routes are e.g. `/api/signup`, `/api/login`).

**Routes and logic:**

- **POST /signup:** Body: fullName, email, password, company. Validates; checks email not already in hr_signup; hashes password with bcrypt; generates OTP and expiry (5 min); creates/updates HRAuth (SQLAlchemy) with is_verified=False; sends OTP email via send_email_otp. Returns “OTP sent”.
- **POST /verify-otp:** Body: email, otp. Loads HRAuth; compares OTP; checks expiry (with 30s grace); marks verified and flushes. If email already in hr_signup returns error; else generates next hrid (HRID001, HRID002…), inserts into hr_signup (full_name, email, company, password from HRAuth), then can return token+user (so frontend can log in immediately after verify).
- **POST /resend-otp:** Body: email. Finds HRAuth, generates new OTP and expiry, updates and sends email.
- **POST /forgot-password:** Body: email. Finds hr_signup; creates/updates HRAuth with OTP and expiry; sends OTP email.
- **POST /forgot-password/verify-otp:** Body: email, otp. Validates OTP and expiry; returns “OTP verified”.
- **POST /reset-password:** Body: email, otp, newPassword, confirmPassword. Validates password strength and match; finds HRAuth, validates OTP and expiry; hashes new password; updates HRAuth (clear OTP) and hr_signup.password; sends “password changed” email.
- **POST /login:** Body: email, password. Looks up hr_signup by email; verifies password with bcrypt; records login in hr_login and login_history; optionally sends “new login” email if new device/IP; builds JWT access and refresh with identity (hrId, email, role); returns token, refresh_token, user.
- **POST /change-password:** Bearer required. Body: currentPassword, newPassword. Validates new password strength; checks current password against hr_signup; updates password; sends confirmation email.
- **POST /refresh:** Body: refresh_token. Decodes JWT; if type != 'refresh' returns 401; checks identity; issues new access and refresh tokens; returns new token pair.
- **POST /logout:** Bearer optional; if token provided, can deactivate session (sessions_service). Returns success.

---

## 6. Jobs Blueprint — `jobs.py`

**Prefix:** `/api/jobs`.

**Helpers:**

- `_send_notification(...)` — delegates to candidate_notification_service to send email (e.g. profile viewed, shortlisted).
- `_resume_bytes(data)` — normalizes resume blob to bytes for response.
- `generate_jdid_from_title(title)` — builds jdid like DA001, SD002 from first letters of words in title and next sequence number from DB.

**Routes:**

- **GET /** (`optional_authenticate_token`): List jobs. If user is HR (role HR and has hrId), selects jobs where posted_by = hrId, optionally filtered by company from JWT. Otherwise selects jobs where enabled = true or null, ordered by posted_on. Returns array of job objects (id, title, company, location, salary, experience, description, enabled, postedOn).
- **GET /all** (`authenticate_token`, `require_hr`): All jobs for this HR (posted_by = hrId).
- **GET /:job_id** (`optional_authenticate_token`): Single job. HR can only see own jobs; others only enabled. Returns 404 if not found or access denied.
- **GET /:job_id/applications** (`authenticate_token`, `require_hr`): Verifies job belongs to hrId; selects applications with candidate profile and ATS fields; for each candidate loads education, experiences, certifications; returns formatted list (matchScore, shortlisted, atsReasoning, atsAnalysis, fullName, email, resumeUrl, education, experiences, certifications). If job not found, returns 200 with empty list.
- **GET /:job_id/applications/:candidate_id/resume** (`authenticate_token`, `require_hr`): Verifies job and application; gets resume from candidate_profiles; returns binary response with Content-Disposition inline.
- **POST /** (`authenticate_token`, `require_hr`): Body: job fields. Generates jdid via generate_jdid_from_title; inserts into jobs (title, company, location, salary, experience, description, enabled, posted_by).
- **PUT /:job_id** (`authenticate_token`, `require_hr`): Verifies job belongs to hrId; updates job fields.
- **PATCH /:job_id/enabled** (`authenticate_token`, `require_hr`): Body: enabled. Updates jobs.enabled.
- **DELETE /:job_id** (`authenticate_token`, `require_hr`): Deletes job if owned by hrId.
- **POST /:job_id/applications/:candidate_id/viewed** (`authenticate_token`, `require_hr`): Marks application as profile viewed; sends notification email; updates application status (e.g. profile_viewed).
- **PATCH /:job_id/applications/:candidate_id/status** (`authenticate_token`, `require_hr`): Body: action (shortlist | reject). Sends notification email and updates application status and shortlisted flag.

---

## 7. Candidate Blueprint — `candidate.py`

**Prefix:** `/api/candidate`. Note: candidate signup/login/verify/resend are in `routes/simple_candidate_auth.py` under the same prefix.

**Routes:**

- **POST /logout:** Reads Bearer token; calls sessions_service to deactivate session; returns success.
- **POST /change-password** (`authenticate_token`, `require_candidate`): Body: currentPassword, newPassword. Validates new password strength; loads candidate_signup; verifies current password with bcrypt; hashes new password and updates candidate_signup.
- **GET /profile** (`authenticate_token`, `require_candidate`): Selects from candidate_profiles (no resume binary); returns parsed profile (fullName, email, education, experiences, certifications, completed, etc.) or default empty shape. Uses a `parse_profile` helper to map DB columns to camelCase and structure.
- **POST /profile** (`authenticate_token`, `require_candidate`): Accepts JSON or multipart/form-data. For multipart, reads form and parses JSON fields (education, certifications, experiences). Reads resume from request.files['resume'] or base64 from JSON. If profile exists: if new resume bytes provided, UPDATE with resume; else UPDATE without resume. If no profile, INSERT. Then deletes and re-inserts candidate_education, candidate_certifications, candidate_experiences from the request arrays. Returns success.
- **GET /resume:** Returns the resume binary for the authenticated candidate (from candidate_profiles).
- **GET /profile/:candidate_id** (`authenticate_token`, `require_hr`): Same as GET /profile but for a given candidate_id so HR can view candidate profile.

**Note:** Candidate forgot-password endpoints (`/api/candidate/forgot-password`, verify-otp, reset-password) are not implemented in this blueprint; the frontend calls them but they return 404.

---

## 8. Simple Candidate Auth — `routes/simple_candidate_auth.py`

**Prefix:** `/api/candidate`. Registered before candidate_bp so signup/login take precedence.

**Routes:**

- **POST /signup:** Body: name, email, password. Validates; hashes password; generates OTP and expiry; inserts or updates CandidateAuth table (raw SQL, not SQLAlchemy) with is_verified false; sends OTP email.
- **POST /verify-otp:** Body: email, otp. Loads CandidateAuth; validates OTP and expiry; marks verified; creates or updates candidate_signup (name, email, password from CandidateAuth). Returns message and cid.
- **POST /resend-otp:** Body: email. New OTP and expiry; updates CandidateAuth and sends email.
- **POST /login:** Body: email, password. Selects candidate_signup by email; verifies password with bcrypt; builds JWT access and refresh (identity: id=cid, email, role=candidate); optionally loads profile for user object; returns token, refresh_token, user.

---

## 9. Applications Blueprint — `applications.py`

**Prefix:** `/api/applications`.

**Helpers:**

- `_run_ats_and_update_application(candidate_id, job_id, parsed_resume, parsed_jd, app_id)` — calls ats_service.match_candidate_to_job; on success updates application row (match_score, shortlisted, ats_reasoning, ats_analysis, status). Runs in a background thread so the apply response is immediate.
- `_jd_toon_from_job_row(job)` — builds a minimal TOON dict from job row (title, skills, responsibilities, etc.) when no parsed JD exists so ATS can still run.
- N8N: optional `trigger_n8n(...)` and callback handling (see below).

**Routes:**

- **POST /** (`authenticate_token`, `require_candidate`): Body: jobId. Validates job exists and enabled; checks no duplicate application; checks candidate_profiles.completed. Loads parsed_resume (by candidate_id or uploader_id) and parsed_jd (or builds from job row). Inserts application (status 'applied', shortlisted false). Starts background thread for _run_ats_and_update_application. Returns 201 with message and status.
- **GET /** (`authenticate_token`, `require_candidate`): Selects applications for request.user['id'] with job details; returns array with id, jobId, status, appliedAt, matchScore, shortlisted, atsReasoning, atsAnalysis, job.
- **POST /ats/result** (no auth; optional header): Callback for n8n ATS. If N8N_CALLBACK_SECRET is set, validates X-N8N-Callback-Secret. Body: candidate_id, job_id, match_score, shortlisted, reasoning, analysis. Finds application; if status still 'applied', sets status to shortlisted/rejected; updates match_score, shortlisted, ats_reasoning, ats_analysis (and stores analysis JSON). Returns 200.

---

## 10. Parsing Blueprint — `parsing_routes.py`

**Prefix:** `/api`.

**Config:** ALLOWED_EXTENSIONS (pdf, doc, docx), MAX_FILE_SIZE (10MB), MIME_TYPE_MAP.

**Helpers:** `allowed_file(filename)`, `get_mime_type(filename)`, `calculate_confidence(toon, doc_type)` — scores resume/JD TOON completeness for a 0–1 confidence.

**Routes:**

- **POST /parse/resume** (`authenticate_token`): Expects multipart file in `request.files['file']`. Validates extension and size. Gets uploader_id and role from JWT (candidate or admin). Computes file hash; if get_cached_parsing_result returns a cached parse, links parsed_resumes.candidate_id if candidate and returns cached toon/confidence. Otherwise: store_raw_file, extract_text (text_extraction), call LLM (llm_service) to get TOON, compute confidence, store_parsed_resume, link candidate_id for candidates; returns raw_file_id, parsed_id, confidence, toon.
- **POST /parse/jd** (`authenticate_token`): Similar flow for JD: store raw file, extract text, LLM to get JD TOON, store_parsed_jd, return id and toon.
- **GET /parsed/resume/:id** (`authenticate_token`): Returns parsed resume by id (toon, confidence) if the user is allowed (owner or HR).
- **GET /parsed/jd/:id** (`authenticate_token`): Same for JD.

---

## 11. Support and Feedback Blueprints

### 11.1 `support.py` — Prefix `/api/support`

- **POST /submit:** Body: name, email, subject, message, optional user_id, user_type, priority. Validates; inserts into support_requests; optionally sends email to SUPPORT_NOTIFICATION_EMAIL. Returns id.
- **GET /my-requests** (Bearer): Returns requests for request.user.
- **GET /all** (Bearer, HR): Returns all support requests.
- **GET /:request_id** (Bearer): Returns one request.
- **PATCH /:request_id/status** (Bearer): Updates status.

### 11.2 `feedback_routes.py` — Prefix `/api/feedback`

- **POST /submit:** Body: employee_name, employee_id, department, feedback_type, severity, module, description, optional screenshot file. Validates; saves to employee_feedback table; uploads file to UPLOAD_FOLDER/feedback; sends email to FEEDBACK_NOTIFICATION_EMAIL. Returns id.
- **GET /list** (Bearer, HR): Returns list of feedback with optional status filter.
- **PATCH /:feedback_id/status** (Bearer, HR): Updates feedback status.

---

## 12. Admin and Super-Admin Blueprints

### 12.1 `modules/admin/routes.py` — Prefix `/api/admin`

- **POST /bulk-parse/upload** (`authenticate_token`, `require_hr`): Accepts multipart files; validates extension (pdf, doc, docx); calls bulk_parsing_service.upload_files; returns job id or error (503 if BULK_PARSER unreachable).
- **GET /bulk-parse/progress/:job_id** (`authenticate_token`, `require_hr`): Proxies to bulk_parsing_service.get_progress.
- **GET /bulk-parse/download/:job_id** (`authenticate_token`, `require_hr`): Streams Excel from bulk_parsing_service.stream_download; returns attachment.
- **GET /job-matches** (`authenticate_token`, `require_hr`): Returns jobs posted by this HR with application counts and shortlisted counts.

### 12.2 `super_admin.py` — Prefix `/api/super-admin`

- **POST /login:** Body: email, password. Looks up hr_signup by email; verifies password; checks is_super_admin; issues JWT with role 'super_admin'. Returns token and user.
- **GET /stats** (`authenticate_token`, `require_head_hr`): Counts hr_signup, candidate_signup, jobs, applications, active jobs, shortlisted. Returns JSON.
- **GET /admins** (`authenticate_token`, `require_super_admin`): List HR admins.
- **POST /admins** (`authenticate_token`, `require_super_admin`): Create admin (signup flow).
- **DELETE /admins/:hrid** (`authenticate_token`, `require_super_admin`): Delete HR admin.
- **GET /candidates**, **GET /candidates/:cid**, **GET /candidates/:cid/resume** (`authenticate_token`, require_head_hr or super_admin): List/detail/resume.
- **DELETE /candidates/:cid** (`authenticate_token`, `require_super_admin`): Delete candidate.
- **GET /jobs**, **GET /jobs/:jdid** (`authenticate_token`): List/detail jobs.
- **DELETE /jobs/:jdid** (`authenticate_token`, `require_super_admin`): Delete job.
- **GET /applications**, **GET /applications/:id** (`authenticate_token`): List/detail applications.
- **GET /settings** (`authenticate_token`): Returns settings (e.g. feature flags).

Many GET routes use `allow_options_no_auth` so OPTIONS preflight succeeds without auth.

---

## 13. Sessions — `sessions_routes.py`

**Prefix:** `/api/sessions`.

- **GET /my-sessions** (Bearer): Returns active sessions for the user.
- **GET /my-history** (Bearer): Returns login history.
- **POST /logout-session** (Bearer): Deactivates one session by token/session id.
- **POST /logout-all** (Bearer): Deactivates all other sessions for the user.

Implementation details (session storage, deactivation) live in `sessions_service.py`.

---

## 14. Helpers and Services (Summary)

### 14.1 `helpers/otp_utils.py`

- **generate_otp():** Returns a 6-digit string.
- **is_valid_email(email):** Simple format check.
- **send_email_otp(email, otp, user_type):** Uses Flask-Mail to send OTP email (template from email_templates).
- **parse_otp_expiry(value):** Converts DB timestamp to datetime.
- **utc_now_aware(), normalize_to_utc_aware(dt):** Timezone-aware UTC for PostgreSQL comparison.

### 14.2 `helpers/email_utils.py` and `email_templates.py`

- **send_notification_email(to, subject, body, html=...):** Sends via Flask-Mail. Used for OTP, password changed, login alert, support received, feedback received.

### 14.3 `services/ats_service.py`

- **match_candidate_to_job(candidate_id, job_id, parsed_resume, parsed_jd, apply_id):** Can call internal matching logic or external ATS_API_URL. Returns (success, result). Result may contain json_output (overall_match_score, decision, final_reasoning) and toon_output. Used by applications blueprint in the background thread after apply.

### 14.4 `services/candidate_notification_service.py`

- **send_and_get_output(hr_action, candidate_name, candidate_email, job_title, company_name, application_id, timestamp):** Sends email to candidate (e.g. “Your profile was viewed”, “You have been shortlisted”). Returns dict with profile_update and status_db for the application status to set.

### 14.5 `services/bulk_parsing_service.py`

- **upload_files(files_list, append):** POSTs to BULK_PARSER_URL; returns (success, result). result may contain job_id or error/code (e.g. BULK_PARSER_NOT_CONFIGURED).
- **get_progress(job_id):** GET progress from BULK_PARSER_URL.
- **stream_download(job_id):** GET Excel stream; returns (iterator, filename, content_type) or (False, error_payload).

### 14.6 `toon.py`

- **toon_loads_flex(s):** Parses JSON from string or bytes; handles TOON structure. Used when reading parsed_resume/parsed_jd or ats_analysis from DB.
- **toon_dumps(obj):** Serializes to JSON string for storage.

### 14.7 `parsing_utils.py`

- **compute_file_hash(data):** Hash for duplicate detection.
- **store_raw_file(...):** Inserts into raw_files; returns record with id.
- **store_parsed_resume(...)** / **store_parsed_jd(...):** Inserts into parsed_resumes/parsed_jds with toon, confidence, model_version.
- **get_cached_parsing_result(file_hash, uploader_id, doc_type):** Returns existing parsed record if same file was parsed before.
- **validate_toon_format(toon, doc_type):** Validates required fields for resume or JD TOON.

### 14.8 `llm_service.py`

- **call_llm(...):** Sends content to LLM (e.g. Grok via XAI); uses llm_key_manager for key rotation; returns parsed TOON or error.
- **classify_document(text):** Classifies as resume or JD. Used in parsing flow.

### 14.9 `text_extraction.py`

- **extract_text(file_data, filename):** Extracts text from PDF (e.g. PyPDF2 or pdfplumber) or DOC/DOCX (python-docx, etc.). Returns plain text for LLM.

---

## 15. Data Flow Summary

1. **Request:** Flask receives HTTP request; CORS handles preflight; route matches a blueprint.
2. **Auth:** If the route uses `authenticate_token`, the decorator reads Bearer token, decodes JWT, sets `request.user`. If `require_hr`/`require_candidate`/etc., checks role and returns 403 if wrong.
3. **Handler:** View function reads `request.get_json()` or `request.files`/`request.form`; validates input; uses `db_get`/`db_all`/`db_run` for DB; may call helpers (email, ATS, parsing).
4. **Response:** Returns `jsonify(...)` or `Response(body, mimetype=..., headers=...)`. Exceptions can be caught and converted to 500 with a generic message.
5. **Background:** Apply flow inserts the application and starts a thread for ATS; parsing may call LLM and store TOON; notifications are sent via Flask-Mail or candidate_notification_service.

This completes the backend structure and code documentation.
