# HR Job Portal — Technical Documentation

**Version:** 1.0  
**Audience:** Internal engineering, architecture reviews, production readiness  
**Last Updated:** June 2026

> **Related:** AI platform docs live in [`ai/README.md`](../ai/README.md). Full documentation index: [`docs/DOCUMENTATION_MAP.md`](DOCUMENTATION_MAP.md).

---

## 1. Executive Summary

### 1.1 What the System Does

The **HR Job Portal** is a full-stack recruitment platform that enables:

- **HR/Recruiters** to post jobs, manage applications, view candidate resumes, run bulk resume parsing, and use AI-powered matching (ATS).
- **Candidates** to sign up (OTP-verified), build profiles with resume upload, browse and apply to jobs, and track application status with match scores.
- **Super Admins** to manage the entire system: view stats, manage HR admins, candidates, jobs, and applications in read-only/delete mode.

The system integrates resume and job-description (JD) parsing (LLM-based TOON format), optional external ATS/n8n webhooks, and an Electron desktop option for bulk resume parser folder access.

### 1.2 Target Users

| User Type       | Access Path              | Primary Capabilities                                      |
|-----------------|--------------------------|-----------------------------------------------------------|
| **Candidates**  | `/login/applicant`       | Signup (OTP), profile, resume upload, apply, track status |
| **HR / Head HR**| `/login/admin`           | Job CRUD, view applications, bulk parser, feedback       |
| **Super Admin**| `/login/admin` (special) | Dashboard, admins/candidates/jobs/applications, settings   |
| **Guests**      | Public                   | Browse jobs, FAQ, contact, HRMS feedback form             |

### 1.3 Core Features

- **Authentication:** Separate HR (OTP signup/verify, JWT access+refresh) and candidate (OTP signup/verify, JWT) flows; super admin uses `hr_signup` with `is_super_admin=true`.
- **Jobs:** CRUD, enable/disable, jdid auto-generation from title; list filtered by role (HR sees own, public sees enabled only).
- **Applications:** Apply (validates profile + parsed resume); ATS runs in background (in-process or n8n callback); shortlist/reject and match score stored.
- **Resume/JD parsing:** PDF/DOC/DOCX upload, LLM-based TOON extraction, storage in `parsed_resumes`/`parsed_jds`; used for apply and ATS.
- **Bulk resume parsing:** Admin upload to external Bulk-Resume-Parser API (or in-process fallback); progress and Excel download.
- **Support & feedback:** Support requests (contact), employee HRMS testing feedback with optional screenshot.

### 1.4 High-Level Architecture

- **Frontend:** React 18 SPA (Vite), single `AppContext` for state, React Router with role-based guards.
- **Backend:** Flask (Python 3.8+), PostgreSQL via psycopg3 and connection pool; blueprints for auth, jobs, candidate, applications, sessions, parsing, support, feedback, admin, super-admin.
- **Communication:** REST JSON APIs; `Authorization: Bearer` JWT; CORS with credentials; frontend uses `fetch` with retry and token refresh on 403.
- **Optional:** External ATS (n8n webhook + callback), external Bulk-Resume-Parser, Electron shell for desktop bulk parser.

---

## 2. Architecture Overview

### 2.1 System Architecture

**Model:** SPA + API backend (monolithic API, single Flask app).

- **Frontend:** Single-page application served by Vite dev server (or static build). No server-side rendering.
- **Backend:** One Flask application; all API routes under `/api` (or `/api/jobs`, `/api/candidate`, etc.). Database access via `db.py` (pool, raw SQL with `%s` placeholders).
- **Parsing:** In-process (Flask + `llm_service`/`text_extraction`/`toon`) for single-file resume/JD; optional external Bulk-Resume-Parser for admin bulk upload.

### 2.2 Technology Stack

| Layer      | Technology |
|-----------|------------|
| Frontend  | React 18, Vite 5, React Router 6, Tailwind CSS, Radix UI primitives, Framer Motion, jspdf/jspdf-autotable, xlsx, lottie-react |
| Backend   | Python 3.8+, Flask, psycopg (v3), bcrypt, PyJWT, Flask-Mail, python-dotenv |
| Database  | PostgreSQL 12+ |
| Auth      | JWT (access + refresh), OTP via email (Flask-Mail) |
| Parsing   | In-app: `text_extraction`, `llm_service` (Grok/XAI), TOON schema. Optional: external Bulk-Resume-Parser, ATS/n8n |

### 2.3 Component Interaction (High Level)

```
[Browser] <---> [Vite/Static] (React SPA)
                    |
                    | HTTP + Bearer JWT
                    v
[Flask app] <---> [PostgreSQL]
     |
     +-- auth_bp, jobs_bp, candidate_bp, applications_bp, ...
     +-- parsing (resume/JD) -> llm_service -> XAI
     +-- (optional) ATS callback from n8n -> applications_bp
     +-- (optional) Bulk parser HTTP client -> BULK_PARSER_URL
```

### 2.4 Key Design Decisions and Trade-offs

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| Single AppContext | Simplicity; one place for auth, jobs, applicant state | Context can become large; no granular subscription |
| JWT in localStorage + memory | Works with CORS and stateless API | XSS can steal token; doc suggests HttpOnly cookies for production |
| Raw SQL + db_run/db_get/db_all | No ORM overhead; full control | Manual escaping; ?→%s conversion in db layer |
| Optional ATS (in-process + n8n) | Flexibility for internal vs external ATS | Two code paths; callback must be secured (N8N_CALLBACK_SECRET) |
| Lazy-loaded routes | Smaller initial bundle | Slight delay on first visit to each page |
| Candidate auth in simple_candidate_auth (no SQLAlchemy) | Avoids session timeout issues with SQLAlchemy | Duplicate patterns vs auth.py (HR) |

---

## 3. Project Structure

**Detailed structure and code-level explanations:** See [FRONTEND_DOCUMENTATION.md](FRONTEND_DOCUMENTATION.md) for the frontend (every folder and file, plus how the code works) and [BACKEND_DOCUMENTATION.md](BACKEND_DOCUMENTATION.md) for the backend.

### 3.1 Directory Breakdown

```
HR-Job-Portal-App/
├── start.js                 # Unified start: env, venv, pip, npm, backend+frontend, browser
├── README.md
├── SETUP.md, PERFORMANCE_OPTIMIZATION.md, LICENSE
├── frontend/
│   ├── index.html            # Entry HTML; script /src/main.jsx
│   ├── vite.config.js        # React plugin, @ -> ./src, server :5173
│   ├── tailwind.config.js, postcss.config.js, jsconfig.json
│   ├── package.json
│   ├── public/_redirects      # SPA redirect (e.g. Netlify)
│   └── src/
│       ├── main.jsx          # React root, BrowserRouter, App
│       ├── App.jsx           # AppProvider, Toast, ErrorBoundary, ConnectionStatus, Navbar, Routes, guards
│       ├── index.css         # Tailwind imports
│       ├── context/
│       │   └── AppContext.jsx # Single app state + actions (auth, jobs, applicant, superAdmin)
│       ├── guards/
│       │   ├── AdminGuard.jsx      # HR or head_hr -> else /login/admin
│       │   ├── CandidateGuard.jsx  # applicantAuth and not HR -> else /login/applicant
│       │   └── SuperAdminGuard.jsx # superAdminAuth -> else /login/admin
│       ├── layouts/
│       │   ├── MainLayout.jsx, DashboardLayout.jsx, AdminLayout.jsx
│       │   └── (super-admin) SuperAdminLayout.jsx
│       ├── pages/            # Lazy-loaded route components
│       │   ├── Home.jsx, Jobs.jsx, Login.jsx, LoginApplicant.jsx, LoginAdmin.jsx
│       │   ├── SignupApplicant.jsx, SignupAdmin.jsx
│       │   ├── ForgotPassword*.jsx, ApplicantProfile.jsx, ApplicationStatus.jsx, Settings.jsx
│       │   ├── Dashboard.jsx, AppliedCandidates.jsx
│       │   ├── admin/ BulkResumeParser.jsx, FeedbackAdmin.jsx
│       │   ├── super-admin/ SuperAdmin*.jsx
│       │   ├── FAQ.jsx, ContactUs.jsx, HRMSTestingFeedback.jsx, NotFound.jsx
│       ├── components/       # Shared + feature components
│       │   ├── ui/           # Button, Card, Input, Badge, Avatar, Modal, Tabs, Table, etc.
│       │   ├── Navbar.jsx, Hero.jsx, JobCard.jsx, CandidateCard.jsx, SearchBar.jsx, FilterBar.jsx
│       │   ├── ResumeUploadWithParsing.jsx, JDUploadWithParsing.jsx, JobDescriptionView.jsx
│       │   ├── MatchExplanation/, Toast.jsx, ErrorBoundary.jsx, ConnectionStatus.jsx
│       ├── services/
│       │   └── adminService.js  # getJobApplications(jobId)
│       ├── utils/
│       │   ├── api.js        # apiRequest, BASE_URL, retry, refresh, setUnauthorizedHandler
│       │   ├── tokenService.js
│       │   ├── healthCheck.js, parsingApi.js, passwordValidation.js, reportUtils.js, pdfReportUtils.js, avatarColor.js
│       └── hooks/
│           └── useAsyncAction.js
├── backend/
│   ├── app.py                # Flask app, CORS, mail, init_db, blueprint registration
│   ├── auth.py               # HR signup/verify/resend/forgot/reset/login/change-password/refresh/logout
│   ├── jobs.py               # Jobs CRUD, applications list/resume/status, jdid generation
│   ├── candidate.py          # Candidate profile GET/POST, resume, logout, change-password
│   ├── applications.py      # Apply, get my applications, ATS callback (n8n)
│   ├── sessions_routes.py    # my-sessions, my-history, logout-session, logout-all
│   ├── parsing_routes.py     # parse/resume, parse/jd, parsed/resume/:id, parsed/jd/:id
│   ├── support.py            # support submit, my-requests, all, by id, status
│   ├── feedback_routes.py    # feedback submit, list, status
│   ├── super_admin.py        # super-admin login, stats, admins, candidates, jobs, applications
│   ├── db.py                 # PostgreSQL pool, get_conn, db_run, db_get, db_all, run_migrations, init_db
│   ├── utils.py              # JWT, authenticate_token, require_hr, require_candidate, require_super_admin, optional_authenticate_token
│   ├── env_validator.py, extensions.py (Flask-Mail)
│   ├── toon.py, text_extraction.py, parsing_utils.py, llm_service.py
│   ├── matching.py, llm_key_manager.py
│   ├── models/               # SQLAlchemy: hr_auth.py, candidate_auth.py (HR/candidate OTP flows)
│   ├── routes/
│   │   └── simple_candidate_auth.py  # candidate signup, verify-otp, resend-otp, login (no SQLAlchemy)
│   ├── modules/admin/
│   │   └── routes.py         # bulk-parse upload/progress/download, job-matches
│   ├── helpers/              # email_utils, email_templates, otp_utils, mail_send
│   ├── services/             # ats_service, candidate_notification_service, bulk_parsing_service
│   ├── schema_pg/
│   │   ├── 01_schema.sql     # Tables: hr_signup, candidate_signup, jobs, applications, parsed_*, etc.
│   │   ├── 02_seed_admin_accounts.sql
│   │   └── 03_employee_feedback.sql
│   ├── requirements.txt, .env.example
│   └── gunicorn.conf.py
├── electron/                 # Desktop shell (native dialogs, IPC only)
│   ├── main.js, preload.js, ipc-handlers.js
├── scripts/                  # Root utilities
├── tests/                    # Test index
├── tools/                    # CLI index
└── ai/toon/v1/types/         # TOON TypeScript contracts (toon.ts)
```

### 3.2 Entry Points

| Role     | Entry |
|----------|--------|
| Frontend | `frontend/index.html` → `<script type="module" src="/src/main.jsx">` |
| React    | `frontend/src/main.jsx` (ReactDOM.createRoot, BrowserRouter, App) |
| Backend  | `backend/app.py` (`if __name__ == '__main__'`: app.run) |
| Unified  | Root `node start.js`: copies backend .env, venv+pip, npm install, starts backend then frontend, waits for health, opens browser |

---

## 4. Frontend Documentation

### 4.1 Framework & Tooling

- **React 18** with `createRoot`.
- **Vite 5**: dev server `0.0.0.0:5173`, `@` alias to `./src`, build target `es2018`. No API proxy by default (CORS used).
- **Tailwind CSS** for styling; **Radix UI** (Avatar, Dialog, Dropdown, Progress, Separator, Slot) for primitives; **class-variance-authority**, **clsx**, **tailwind-merge** for variant styling.
- **React Router DOM 6**: `Routes`, `Route`, `Navigate`, `useLocation`; no data APIs (loaders/actions).

### 4.2 Routing System

Defined in `App.jsx`. All page components are lazy-loaded via `React.lazy()`.

- **Public:** `/`, `/jobs`, `/support/faq`, `/support/contact`, `/support/hrms-feedback`, `/login`, `/login/applicant`, `/login/admin`, `/signup/applicant`, `/signup/admin`, `/forgot-password/:variant`, `/forgot-password/:variant/verify`, `/forgot-password/:variant/reset`.
- **Candidate-only (CandidateGuard):** `/profile/applicant`, `/settings/applicant`, `/applications`.
- **HR-only (PrivateRoute):** `/dashboard`, `/candidates`, `/settings`.
- **Admin (AdminGuard):** `/admin/bulk-resume-parser`, `/admin/feedback`.
- **Super Admin (SuperAdminGuard):** `/super-admin`, `/super-admin/admins`, `/super-admin/candidates`, `/super-admin/candidates/:cid`, `/super-admin/jobs`, `/super-admin/jobs/:jdid`, `/super-admin/applications`, `/super-admin/applications/:id`, `/super-admin/settings`.
- **Redirects:** `/signup` → `/signup/applicant`, `/login/super-admin` → `/login/admin`.
- **Fallback:** `*` → `NotFound`.

`PrivateRoute` allows `auth.isLoggedIn && (auth.role === 'HR' || auth.role === 'head_hr')`. Navbar is hidden when `pathname.startsWith('/super-admin')`.

### 4.3 State Management

- **No Redux.** Single **AppContext** (`context/AppContext.jsx`).
- **State:** jobs, jobsLoading, jobsError; auth (HR), applicantAuth, superAdminAuth; applicantProfile, applicantApplications, applicantSavedJobs; user; token; backendHealthy; authLoading, authError.
- **Persistence:** localStorage for auth, applicantAuth, superAdminAuth, applicantProfile, applicantApplications, applicantSavedJobs, user (keys in `STORAGE_KEYS`). Token is also in `tokenService` (in-memory + localStorage). Jobs are not persisted (fetched from API).
- **Actions:** loginHR, loginApplicant, loginSuperAdmin; signup/verify/resend OTP (HR and applicant); forgot-password/verify/reset (HR and applicant); changePassword (HR and applicant); saveApplicantProfile, markApplicantProfileCompleted; applyToJobAsApplicant, toggleSaveJob; fetchJobs, addJob, updateJob, setJobEnabled; fetchApplicantData, fetchApplicationsForJob, fetchAllApplications; logout, logoutSuperAdmin.
- **Effects:** On mount, setUnauthorizedHandler(logout), setOnTokensRefreshed(update token state). Initial health check after 2s; then every 30s. Token hydrated from tokenService on load. Jobs fetched on mount and when auth/applicantAuth changes. Applicant data fetched when applicantAuth and token are set.

### 4.4 Reusable UI System

Location: `frontend/src/components/ui/`. Barrel: `ui/index.js`.

- **Button** (buttonVariants), **Card** (CardHeader, CardFooter, CardTitle, CardDescription, CardContent), **Input**, **Textarea**, **Badge** (badgeVariants), **Avatar** (AvatarImage, AvatarFallback, AvatarWithInitials), **StatCard**, **Modal**, **Tabs** (TabPanel), **Skeleton**, **SkeletonLoader** (SkeletonCard, SkeletonList), **DropdownMenu** (Trigger, Content, Item, Label, Separator), **Dialog** (Trigger, Content, Header, Footer, Title, Description), **Progress**, **Table** (Header, Body, Footer, Head, Row, Cell, Caption), **Separator**.

Built with Radix primitives and Tailwind; variants via cva + cn.

### 4.5 Guards & Authentication Flow

- **AdminGuard:** Renders children only if `auth.isLoggedIn && (auth.role === 'HR' || auth.role === 'head_hr')`; else `<Navigate to="/login/admin" replace />`.
- **CandidateGuard:** Renders children only if `applicantAuth?.isLoggedIn && !(auth?.isLoggedIn && auth?.role === 'HR')`; else `<Navigate to="/login/applicant" replace />`.
- **SuperAdminGuard:** Renders children only if `superAdminAuth?.isLoggedIn`; else `<Navigate to="/login/admin" replace />`.

Login flows: HR and candidate each use email + password; HR and candidate signup use OTP email verification. Super admin uses same login page as admin; backend returns 403 if not `is_super_admin`. On 401/403 with token, `api.js` calls optional `onUnauthorized` (wired to logout) and on 403 attempts one token refresh via `POST /api/refresh` then retries the request.

### 4.6 Services & API Integration

- **HTTP client:** `utils/api.js`.
  - **BASE_URL:** `import.meta.env.VITE_API_URL` (default `http://localhost:3000`), no trailing slash.
  - **apiRequest(path, { method, body, token, headers, timeoutMs, skipRetry }):** Uses `fetch` with `credentials: 'include'`. Timeout from `VITE_API_TIMEOUT_MS` (default 30s). Retry: max 2 attempts, exponential backoff (500ms base, 3s max); retries only on network/5xx/ECONNREFUSED/ETIMEDOUT/ENOTFOUND. On 403 with token, one refresh via `POST /api/refresh` then retry. On 401/403 with token, calls `setUnauthorizedHandler` (logout). Sets `Authorization: Bearer` from `token` or `tokenService.getToken()`.
- **Token:** `utils/tokenService.js` — getToken, setToken, getRefreshToken, setRefreshToken, clear; in-memory + localStorage (`jwtToken`, `refreshToken`).
- **adminService.js:** `getJobApplications(jobId)` → `apiRequest(\`/api/jobs/${jobId}/applications\`)`.
- **parsingApi.js:** Uses same BASE_URL (or `VITE_PARSING_API_URL` for separate parsing service); helpers for TOON arrays and date normalization (ensureArray, normalizeToYYYYMM, ensureStringArray, etc.).

### 4.7 Key Components (Purpose, Props, Logic)

- **Navbar:** Top navigation; shows links by role (candidate vs HR); logout. Uses `useApp()` for auth state.
- **JobCard:** Displays one job; actions: apply, save; uses applicantApplications/applicantSavedJobs and applyToJobAsApplicant, toggleSaveJob from context.
- **ResumeUploadWithParsing:** File input for resume; calls parsing API; maps TOON to profile fields; used in ApplicantProfile.
- **ConnectionStatus:** Shows backend health (backendHealthy from context); may show offline/retry UI.
- **ErrorBoundary:** Catches React errors; renders fallback UI.
- **Toast (ToastProvider, useToast):** Global toast queue; used for auth errors and notifications.

---

## 5. Backend Documentation

### 5.1 Framework & Structure

- **Flask** application in `app.py`. Loads `.env` from backend directory; runs `EnvValidator` at startup; configures CORS (origins from `FRONTEND_URLS`/`FRONTEND_URL` or localhost + local IP), Flask-Mail, `init_models()`, `init_db()`; registers blueprints.
- **Database:** `db.py` — PostgreSQL via psycopg3, connection pool (default 5), `get_conn()`, `db_run`, `db_get`, `db_all`. Placeholders normalized from `?` to `%s` for psycopg. Migrations: `schema_pg/*.sql` run in order by `run_migrations()`.

### 5.2 API Design

- REST-style; JSON request/response. Auth: `Authorization: Bearer <access_token>`.
- HR auth and password reset under `/api` (auth_bp); candidate auth under `/api/candidate` (simple_candidate_auth_bp + candidate_bp). Same JWT secret for all roles; payload includes `role` and identity fields.

### 5.3 Controllers / Services / Models

- **Blueprints:** auth, jobs, candidate (simple_candidate_auth + candidate), applications, sessions, parsing, support, feedback, admin, super_admin.
- **Models (SQLAlchemy):** `models/hr_auth.py`, `models/candidate_auth.py` for OTP verification tables (HRAuth, CandidateAuth). Main data access is raw SQL via `db.py`.
- **Services:** `ats_service` (match_candidate_to_job), `candidate_notification_service`, `bulk_parsing_service` (upload, progress, stream_download to BULK_PARSER_URL).

### 5.4 Authentication & Authorization

- **utils.py:** `authenticate_token`: reads Bearer token, decodes JWT with `JWT_SECRET`, sets `request.user`; rejects if token is refresh type; 401 if no token, 403 if invalid/expired. `require_hr`: after authenticate_token, allows role `HR` or `head_hr`. `require_candidate`: allows role `candidate`. `require_super_admin`: allows role `super_admin`. `require_head_hr`: allows `head_hr` or `super_admin`. `optional_authenticate_token`: if Bearer present, validate and set request.user; else request.user = None.
- **JWT:** `build_jwt_payload(identity_dict, refresh=False)` adds `type`, `iat`, `exp`; access and refresh expiry from env (default 1h / 30d).

### 5.5 Database Interaction

- All queries go through `db_run`, `db_get`, `db_all`. Schema in `schema_pg/01_schema.sql`: hr_signup, candidate_signup, candidate_education/certifications/experiences, hr_login, candidate_login, jobs, candidate_profiles, applications, support_requests, raw_files, parsed_resumes, parsed_jds, login_history, CandidateAuth, HRAuth. Additional tables in 02/03 for seed and employee_feedback.

---

## 6. API Documentation

### 6.1 Endpoints Overview

Base URL: `http://localhost:3000` (or `VITE_API_URL`). All below are relative to that.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | — | API root |
| GET | `/health` | — | Health + bulk_parser status |
| GET/OPTIONS | `/api/test-cors` | — | CORS test |

**Auth (HR) — prefix `/api`**

| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/signup` | fullName, email, password, company | HR signup (sends OTP) |
| POST | `/verify-otp` | email, otp | Verify OTP; may return token+user |
| POST | `/resend-otp` | email | Resend OTP |
| POST | `/forgot-password` | email | Send reset OTP |
| POST | `/forgot-password/verify-otp` | email, otp | Verify reset OTP |
| POST | `/reset-password` | email, otp, newPassword, confirmPassword | Reset HR password |
| POST | `/login` | email, password | Returns token, refresh_token, user |
| POST | `/change-password` | currentPassword, newPassword | Bearer |
| POST | `/refresh` | refresh_token | Returns token, refresh_token |
| POST | `/logout` | — | Bearer; invalidate session |

**Candidate auth — prefix `/api/candidate`**

| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/signup` | name, email, password | Candidate signup (OTP) |
| POST | `/verify-otp` | email, otp | Verify OTP |
| POST | `/resend-otp` | email | Resend OTP |
| POST | `/login` | email, password | Returns token, refresh_token, user |
| POST | `/logout` | — | Bearer |
| POST | `/change-password` | currentPassword, newPassword | Bearer |
| GET | `/profile` | — | Bearer; candidate profile |
| POST | `/profile` | JSON or multipart (resume file) | Bearer; save profile |
| GET | `/resume` | — | Bearer; resume file |
| GET | `/profile/:candidate_id` | — | Bearer HR; profile by id |

**Note:** Candidate forgot-password endpoints (`/api/candidate/forgot-password`, `/api/candidate/forgot-password/verify-otp`, `/api/candidate/reset-password`) are **called by the frontend but not implemented in the backend**. HR forgot-password is under `/api` (auth_bp).

**Jobs — prefix `/api/jobs`**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Optional Bearer | List jobs (HR: own jobs; else enabled) |
| GET | `/all` | Bearer HR | All jobs (admin) |
| GET | `/:job_id` | — | Job by jdid |
| GET | `/:job_id/applications` | Bearer HR | Applications for job |
| GET | `/:job_id/applications/:candidate_id/resume` | Bearer HR | Resume file |
| POST | `/` | Bearer HR | Create job |
| PUT | `/:job_id` | Bearer HR | Update job |
| PATCH | `/:job_id/enabled` | Bearer HR | Set enabled |
| DELETE | `/:job_id` | Bearer HR | Delete job |
| POST | `/:job_id/applications/:candidate_id/viewed` | Bearer HR | Mark viewed |
| PATCH | `/:job_id/applications/:candidate_id/status` | Bearer HR | Update application status |

**Applications — prefix `/api/applications`**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/` | Bearer candidate | Apply (body: jobId) |
| GET | `/` | Bearer candidate | My applications |
| GET | `/all` | Bearer HR | All applications |
| POST | `/ats/result` | Optional X-N8N-Callback-Secret | n8n ATS callback |

**Sessions — prefix `/api/sessions`**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/my-sessions` | Bearer | Current sessions |
| GET | `/my-history` | Bearer | Login history |
| POST | `/logout-session` | Bearer | Logout one session |
| POST | `/logout-all` | Bearer | Logout all other sessions |

**Parsing — prefix `/api`**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/parse/resume` | Bearer | Upload resume; returns TOON |
| POST | `/parse/jd` | Bearer | Upload JD; returns TOON |
| GET | `/parsed/resume/:id` | Bearer | Get parsed resume by id |
| GET | `/parsed/jd/:id` | Bearer | Get parsed JD by id |

**Support — prefix `/api/support`**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/submit` | — | Create support request |
| GET | `/my-requests` | Bearer | My requests |
| GET | `/all` | Bearer HR | All requests |
| GET | `/:request_id` | Bearer | Request by id |
| PATCH | `/:request_id/status` | Bearer | Update status |

**Feedback — prefix `/api/feedback`**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/submit` | — | Submit HRMS feedback (optional file) |
| GET | `/list` | Bearer HR | List feedback |
| PATCH | `/:feedback_id/status` | Bearer HR | Update status |

**Admin — prefix `/api/admin`**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/bulk-parse/upload` | Bearer HR | Upload files (multipart) |
| GET | `/bulk-parse/progress/:job_id` | Bearer HR | Progress |
| GET | `/bulk-parse/download/:job_id` | Bearer HR | Excel download |
| GET | `/job-matches` | Bearer HR | Jobs with application counts |

**Super Admin — prefix `/api/super-admin`**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/login` | email, password | Super admin login |
| GET | `/stats` | Bearer head_hr/super_admin | Dashboard counts |
| GET | `/admins` | Bearer super_admin | List HR admins |
| POST | `/admins` | Bearer super_admin | Create admin |
| DELETE | `/admins/:hrid` | Bearer super_admin | Delete admin |
| GET | `/candidates`, `/candidates/:cid`, `/candidates/:cid/resume` | Bearer | List/detail/resume |
| DELETE | `/candidates/:cid` | Bearer super_admin | Delete candidate |
| GET | `/jobs`, `/jobs/:jdid` | Bearer | List/detail |
| DELETE | `/jobs/:jdid` | Bearer super_admin | Delete job |
| GET | `/applications`, `/applications/:id` | Bearer | List/detail |
| GET | `/settings` | Bearer | Settings (e.g. feature flags) |

### 6.2 Request/Response Formats

- **Login (HR/candidate):** Request `{ email, password }`. Response `{ token, refresh_token?, user }` with `user` containing id, email, role, and optional profile fields.
- **Apply:** Request `{ jobId }`. Response 201 `{ message, status: 'applied', matchScore, shortlisted }`.
- **Jobs list:** Response array of job objects (jdid, title, company, location, salary, experience, description, enabled, posted_by, posted_on, company_name).
- **Applications list (candidate):** Array of `{ id, jobId, status, appliedAt, matchScore, shortlisted, atsReasoning, atsAnalysis, job }`.

### 6.3 Error Handling

- 400: validation errors; body often `{ error: "message" }`.
- 401: missing or invalid token.
- 403: valid token but wrong role or refresh token used as access.
- 404: resource not found.
- 500: server error. Frontend `api.js` maps 500/503/network to user-friendly messages and retries on 5xx/network.

---

## 7. Data Flow

### 7.1 User Input → API → Processing → UI

1. **User action** (e.g. click "Apply" on a job): Component calls context action `applyToJobAsApplicant(jobId)`.
2. **Context:** Validates applicantAuth, profile completed, resume and education present; performs optimistic update (applicantApplications[jobId] = { status: 'applied' }); calls `apiRequest('POST', '/api/applications', { body: { jobId }, token })`.
3. **api.js:** Builds URL, adds `Authorization: Bearer`, sends fetch. On 403, may call refresh then retry. On success, returns parsed JSON.
4. **Backend:** applications_bp receives request; authenticate_token + require_candidate; validates job and profile; fetches stored parsed_resume and parsed_jd; inserts application row; starts background thread for ATS; returns 201.
5. **Context:** On success, calls fetchApplicantData() to sync applications; returns { ok: true }. On failure, reverts optimistic update and returns { ok: false, message }.
6. **UI:** Component may show toast or update button state from context state (applicantApplications, jobs).

### 7.2 Token Refresh Flow

1. Request returns 403 with a token that was sent.
2. api.js calls tryRefresh(): POST /api/refresh with refresh_token from tokenService.
3. Backend returns new token and refresh_token; tokenService and onTokensRefreshed (context setToken) update state.
4. Original request is retried once with new access token.

---

## 8. Core Workflows

### 8.1 User Authentication (HR)

1. User opens `/login/admin`, enters email/password.
2. Frontend calls `loginHR(email, password)` → POST `/api/login` with `{ email, password }`.
3. Backend validates credentials against hr_signup, issues JWT access + refresh, returns token and user (role, email, company, etc.).
4. Frontend sets token in tokenService and state; sets auth to { isLoggedIn: true, role, email, ... }; persists to localStorage.
5. Redirect or navigation to `/dashboard`; PrivateRoute allows access.

### 8.2 Job Application Flow

1. Candidate has completed profile and parsed resume. On Jobs or JobCard, clicks Apply.
2. Frontend: applyToJobAsApplicant(jobId) → optimistic update → POST `/api/applications` with { jobId }, Bearer token.
3. Backend: Validates job and candidate profile; ensures parsed_resume exists; creates application row (status 'applied'); starts background ATS (in-process or n8n); returns 201.
4. Frontend: fetchApplicantData() syncs applications; UI shows "Applied" and optional match score when ATS completes (polling or refetch).

### 8.3 Resume Upload & Parsing

1. Candidate on ApplicantProfile uploads file; ResumeUploadWithParsing sends file to POST `/api/parse/resume` (Bearer).
2. Backend: parsing_routes stores raw file, extracts text, calls LLM for TOON, stores in parsed_resumes (and links candidate_id if known); returns TOON + id.
3. Frontend: parsingApi helpers normalize TOON (ensureArray, normalizeToYYYYMM); profile form is prefilled; saveApplicantProfile can send profile + optional new file to POST `/api/candidate/profile`.

### 8.4 Admin Operations

1. **Bulk resume parser:** Admin opens `/admin/bulk-resume-parser`, uploads files → POST `/api/admin/bulk-parse/upload`. Backend proxies to BULK_PARSER_URL or uses in-process service. Frontend polls GET `/api/admin/bulk-parse/progress/:job_id`, then GET `/api/admin/bulk-parse/download/:job_id` for Excel.
2. **View candidates:** HR opens `/candidates` or job detail; frontend fetches GET `/api/jobs/:id/applications`; table shows candidates; resume via GET `/api/jobs/:id/applications/:candidate_id/resume`.

---

## 9. Key Modules Deep Dive

### 9.1 AppContext (frontend/src/context/AppContext.jsx)

- **Purpose:** Single source of truth for auth (HR, applicant, super admin), jobs, applicant profile/applications/saved jobs, and all mutations that call the API.
- **Design:** useMemo value object to avoid unnecessary re-renders; many useEffect hooks for persistence and hydration (localStorage + storage event). fetchApplicantData is useCallback with [token, applicantAuth.isLoggedIn] to avoid loops.
- **Edge cases:** saveApplicantProfile saves locally first; on server failure returns ok: true with warning so data is not lost. applyToJobAsApplicant reverts optimistic update on API failure. Super admin login clears HR and applicant auth so only one session type is active.

### 9.2 api.js (frontend/src/utils/api.js)

- **Purpose:** Central fetch wrapper with retry, timeout, refresh on 403, and global logout on 401/403.
- **Logic:** performRequest builds headers (Bearer from token or tokenService), sends fetch; on 403 with token, tryRefresh() then retry once; on auth failure invokes onUnauthorized. apiRequest loop: retries up to maxRetries on retryable errors (network, 5xx, ECONNREFUSED, etc.); does not retry 4xx or after refresh.
- **Edge cases:** FormData not sent as JSON; timeout uses AbortController; production warning if BASE_URL is http.

### 9.3 applications.py (backend)

- **Purpose:** Apply to job and receive ATS results (in-process thread or n8n callback).
- **Apply flow:** Validates job, no duplicate application, profile completed; loads parsed_resume (by candidate_id or uploader_id) and parsed_jd (or builds minimal TOON from job row); inserts application; spawns thread for _run_ats_and_update_application (match_candidate_to_job or n8n trigger); returns 201 immediately.
- **ATS callback:** POST /api/applications/ats/result; optional X-N8N-Callback-Secret; updates application match_score, shortlisted, ats_reasoning, ats_analysis, status (if still 'applied').

### 9.4 db.py (backend)

- **Purpose:** PostgreSQL connection pool and query helpers.
- **Design:** ConnectionPool with Queue; get_connection checks pool, validates with SELECT 1, or creates new connection. get_conn context manager commits on success, rollback on exception, always returns connection to pool. run_migrations runs schema_pg/*.sql in order; idempotent column adds for is_super_admin, is_head_hr.

---

## 10. Environment & Setup

### 10.1 Installation

From repo root:

```bash
# 1. Copy backend env
cp backend/.env.example backend/.env   # or start.js does this

# 2. Edit backend/.env: POSTGRES_* or DATABASE_URL

# 3. Start (installs backend venv + pip, frontend npm, starts both, opens browser)
node start.js
```

Manual backend: `cd backend && python -m venv venv && .\venv\Scripts\Activate && pip install -r requirements.txt && python app.py`  
Manual frontend: `cd frontend && npm install && npm run dev`

### 10.2 Environment Variables

**Backend (backend/.env)**  
- **Required:** POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD (or DATABASE_URL).  
- **App:** PORT=3000, JWT_SECRET, FLASK_DEBUG.  
- **Mail:** MAIL_USERNAME, MAIL_PASSWORD, MAIL_SUPPRESS_SEND.  
- **Parsing/LLM:** XAI_MODEL, HRMS_API_KEY_1..4, optional LLM_REQUEST_TIMEOUT, BULK_PARSE_MAX_WORKERS.  
- **Optional:** ATS_API_URL, BULK_PARSER_URL, N8N_WEBHOOK_URL, N8N_CALLBACK_SECRET, FRONTEND_URL/FRONTEND_URLS, SUPPORT_NOTIFICATION_EMAIL, FEEDBACK_NOTIFICATION_EMAIL.

**Frontend (frontend/.env)**  
- VITE_API_URL=http://localhost:3000  
- VITE_API_TIMEOUT_MS=30000  
- VITE_PARSING_API_URL (optional, for separate parsing service)

### 10.3 Build & Deployment

- **Frontend:** `npm run build` (Vite); output in `frontend/dist`. Serve with any static host; SPA redirect for * to index.html (e.g. `public/_redirects` for Netlify).
- **Backend:** `python app.py` or gunicorn (see gunicorn.conf.py). Set FRONTEND_URLS for CORS in production.

---

## 11. Design Patterns & Practices

- **Service layer:** Backend: blueprints as controllers; db.py as data access; services (ats_service, bulk_parsing_service) for external or complex logic. Frontend: api.js as HTTP layer; context as application service.
- **Guards:** Route-level components (AdminGuard, CandidateGuard, SuperAdminGuard) enforce role before rendering page.
- **Optimistic updates:** applyToJobAsApplicant updates UI immediately and reverts on failure.
- **Persistence:** Critical client state (auth, profile, applications, saved jobs) in localStorage with storage event sync across tabs.
- **Lazy loading:** All route components lazy-loaded to reduce initial bundle.
- **Retry and refresh:** API retry for transient failures; single token refresh on 403 then retry.

---

## 12. Performance Considerations

- **Backend:** Connection pool (5) avoids per-request connection cost; init_db at startup (not lazy) prevents first-request delay. ATS run in background thread so apply response is fast.
- **Frontend:** Lazy routes, 30s health check interval, cached health result. Large context can cause broad re-renders; consider splitting or selectors if profiling shows issues.
- **Bottlenecks:** LLM parsing (resume/JD) can be slow; bulk parser depends on external service. Database: ensure indexes on applications(shortlisted, match_score), jobs(posted_by, enabled).

---

## 13. Security Analysis

- **Auth:** JWT in localStorage and in-memory; vulnerable to XSS. Comments in code recommend HttpOnly cookies for production. Refresh token stored same way; rotation on refresh.
- **Token handling:** Backend rejects refresh token used as access; expiry enforced. Frontend sends Bearer only when present; 401/403 trigger logout.
- **Input validation:** Backend validates email format, password strength (length, upper/lower/digit/special), required fields. File upload: extension and size limits (parsing, feedback).
- **Candidate forgot-password:** Frontend calls `/api/candidate/forgot-password` etc.; **backend does not implement these routes** — gap and possible 404 for users.
- **ATS callback:** Optional N8N_CALLBACK_SECRET to authenticate n8n callback. Without it, any client could POST /api/applications/ats/result.
- **CORS:** Explicit allow list (no *); supports_credentials true. Good for credentialed requests.

---

## 14. Risks & Technical Debt

- **Candidate forgot-password:** Frontend expects backend routes that do not exist; implement or remove UI.
- **JWT in localStorage:** Prefer HttpOnly cookies for production.
- **Large AppContext:** One context for all state may cause unnecessary re-renders; consider splitting or useReducer/selectors.
- **Dual ATS paths:** In-process ATS and n8n callback; two code paths to maintain and test.
- **SQLAlchemy + raw SQL:** HR OTP uses SQLAlchemy (HRAuth); candidate OTP uses raw SQL (CandidateAuth) to avoid session issues. Inconsistent pattern.
- **Error handling:** Some routes return 500 with generic message; structured error codes would help frontend.

---

## 15. Recommendations

1. **Implement candidate forgot-password** in backend (e.g. in candidate_bp or simple_candidate_auth) to match frontend, or remove the flow from UI.
2. **Move JWT to HttpOnly cookies** for production; keep credentials: 'include'; remove token from localStorage and tokenService for access token.
3. **Add request/response logging** (e.g. request id, duration) for debugging and audits.
4. **Split or scope AppContext** (e.g. AuthContext, JobsContext) or use selectors to reduce re-renders.
5. **Unify ATS integration** behind one interface (e.g. always enqueue job, worker calls in-process or n8n) to simplify code and testing.
6. **Document N8N_CALLBACK_SECRET** and recommend setting it when using n8n.
7. **Add API versioning** (e.g. /api/v1) if multiple clients or breaking changes are expected.
