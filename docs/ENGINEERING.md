# Engineering

Full-stack technical reference for the HR Job Portal — architecture, APIs, backend, and frontend.

> **Authority:** Prefer live code when this file disagrees. This document is a **deep narrative archive**.

Related: [README.md](README.md) · [DEVELOPMENT.md](DEVELOPMENT.md) · [ARCHITECTURE.md](ARCHITECTURE.md)

---

## Table of contents

- [Technical overview](#technical-overview)
- [Backend](#backend)
- [Frontend](#frontend)

---

## Technical overview

**Version:** 1.0  
**Audience:** Internal engineering, architecture reviews, production readiness  
**Last Updated:** August 2026

> **Related:** AI platform docs live in [`ai/README.md`](../../ai/README.md). Full documentation index: [README.md](../README.md).

### Intelligence Engine (Resume & JD)

Parsing is orchestrated by the **Human Capital Intelligence Engine** (`apps/backend/app/ai/parser/engine/`):

```
Document → Layout/Text → Sections → Deterministic parsers → Knowledge →
Semantic AI (gaps only) → TOON → Validate → Persist → Form mapping
```

- **Resume:** deterministic-first (`RESUME_SKIP_LLM_WHEN_DETERMINISTIC`); LLM only for semantic gaps.
- **JD:** deterministic-first (`JD_SKIP_LLM_WHEN_DETERMINISTIC`); same engine entry.
- **TOON** remains the canonical structured representation.
- **Progress:** `GET /api/parse/jobs/:id/progress` and SSE streams `/api/parse/resume/public/stream`, `/api/parse/jd/stream`.
Adaptive runtime: `apply_hardware_env()` sets `OLLAMA_MODEL` from the hardware tier
when the operator has not set it (`gpu_high`→14b, `gpu_mid`→7b, `cpu`→3b). Also sets
concurrency, OCR DPI, and `RESUME_LAYOUT_ENABLED` / `HCIP_ENABLE_DOCLAYOUT`.

Bulk resume parsing uses `parse_resume_text_via_engine` (same sections/parsers/knowledge path).

---

### 1. Executive Summary

#### 1.1 What the System Does

The **HR Job Portal** is a full-stack recruitment platform that enables:

- **HR/Recruiters** to post jobs, manage applications, view candidate resumes, run bulk resume parsing, and use AI-powered matching (ATS).
- **Candidates** to sign up (OTP-verified), build profiles with resume upload, browse and apply to jobs, and track application status with match scores.
- **Head of HRs** to manage the entire system: view stats, manage HR admins, candidates, jobs, and applications in read-only/delete mode.

The system integrates resume and job-description (JD) parsing (LLM-based TOON format), optional external ATS/n8n webhooks, and an Electron desktop option for bulk resume parser folder access.

#### 1.2 Target Users

| User Type       | Access Path              | Primary Capabilities                                      |
|-----------------|--------------------------|-----------------------------------------------------------|
| **Candidates**  | `/login/applicant`       | Signup (OTP), profile, resume upload, apply, track status |
| **HR / Head HR**| `/login/admin`           | Job CRUD, view applications, bulk parser, feedback       |
| **Head of HR**| `/login/admin` (special) | Dashboard, admins/candidates/jobs/applications, settings   |
| **Guests**      | Public                   | Browse jobs, FAQ, contact, HRMS feedback form             |

#### 1.3 Core Features

- **Authentication:** Separate HR (OTP signup/verify, JWT access+refresh) and candidate (OTP signup/verify, JWT) flows; Head of HR (`HEAD_HR`) uses `POST /api/login` like other staff roles.
- **Jobs:** CRUD, enable/disable, jdid auto-generation from title; list filtered by role (HR sees own, public sees enabled only).
- **Applications:** Apply (validates profile + parsed resume); ATS runs in background (in-process or n8n callback); shortlist/reject and match score stored.
- **Resume/JD parsing:** PDF/DOC/DOCX upload, LLM-based TOON extraction, storage in `parsed_resumes`/`parsed_jds`; used for apply and ATS.
- **Bulk resume parsing:** Admin upload to external Bulk-Resume-Parser API (or in-process fallback); progress and Excel download.
- **Support & feedback:** Support requests (contact), employee HRMS testing feedback with optional screenshot.

#### 1.4 High-Level Architecture

- **Frontend:** React 18 SPA (Vite), single `AppContext` for state, React Router with role-based guards.
- **Backend:** Flask (Python 3.8+), PostgreSQL via psycopg3 and connection pool; blueprints for auth, jobs, candidate, applications, sessions, parsing, support, feedback, admin, head-hr.
- **Communication:** REST JSON APIs; `Authorization: Bearer` JWT; CORS with credentials; frontend uses `fetch` with retry and token refresh on 403.
- **Optional:** External ATS (n8n webhook + callback), external Bulk-Resume-Parser, Electron shell for desktop bulk parser.

---

### 2. Architecture Overview

#### 2.1 System Architecture

**Model:** SPA + API backend (monolithic API, single Flask app).

- **Frontend:** Single-page application served by Vite dev server (or static build). No server-side rendering.
- **Backend:** One Flask application; all API routes under `/api` (or `/api/jobs`, `/api/candidate`, etc.). Database access via `db.py` (pool, raw SQL with `%s` placeholders).
- **Parsing:** In-process (Flask + `llm_service`/`text_extraction`/`toon`) for single-file resume/JD; optional external Bulk-Resume-Parser for admin bulk upload.

#### 2.2 Technology Stack

| Layer      | Technology |
|-----------|------------|
| Frontend  | React 18, Vite 5, React Router 6, Tailwind CSS, Radix UI primitives, Framer Motion, jspdf/jspdf-autotable, xlsx, lottie-react |
| Backend   | Python 3.8+, Flask, psycopg (v3), bcrypt, PyJWT, Flask-Mail, python-dotenv |
| Database  | PostgreSQL 12+ |
| Auth      | JWT (access + refresh), OTP via email (Flask-Mail) |
| Parsing   | In-app: `text_extraction`, `llm_service` (Grok/XAI), TOON schema. Optional: external Bulk-Resume-Parser, ATS/n8n |

#### 2.3 Component Interaction (High Level)

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

#### 2.4 Key Design Decisions and Trade-offs

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| Single AppContext | Simplicity; one place for auth, jobs, applicant state | Context can become large; no granular subscription |
| JWT in localStorage + memory | Works with CORS and stateless API | XSS can steal token; doc suggests HttpOnly cookies for production |
| Raw SQL + db_run/db_get/db_all | No ORM overhead; full control | Manual escaping; ?→%s conversion in db layer |
| Optional ATS (in-process + n8n) | Flexibility for internal vs external ATS | Two code paths; callback must be secured (N8N_CALLBACK_SECRET) |
| Lazy-loaded routes | Smaller initial bundle | Slight delay on first visit to each page |
| Candidate auth in simple_candidate_auth (no SQLAlchemy) | Avoids session timeout issues with SQLAlchemy | Duplicate patterns vs auth.py (HR) |

---

### 3. Project Structure

**Detailed structure and code-level explanations:** See [Frontend](#frontend) and [Backend](#backend) below.

#### 3.1 Directory Breakdown

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
│       │   └── AppContext.jsx # Single app state + actions (auth, jobs, applicant, auth)
│       ├── guards/
│       │   ├── RecruiterGuard.jsx      # HR or head_hr -> else /login/admin
│       │   ├── CandidateGuard.jsx  # applicantAuth and not HR -> else /login/applicant
│       │   └── HeadHrGuard.jsx # auth (HEAD_HR) -> else /login/admin
│       ├── layouts/
│       │   ├── MainLayout.jsx, DashboardLayout.jsx, AdminLayout.jsx
│       │   └── (head-hr) HeadHrLayout.jsx
│       ├── pages/            # Lazy-loaded route components
│       │   ├── Home.jsx, Jobs.jsx, Login.jsx, LoginApplicant.jsx, LoginAdmin.jsx
│       │   ├── SignupApplicant.jsx, SignupAdmin.jsx
│       │   ├── ForgotPassword*.jsx, ApplicantProfile.jsx, ApplicationStatus.jsx, Settings.jsx
│       │   ├── Dashboard.jsx, AppliedCandidates.jsx
│       │   ├── admin/ BulkResumeParser.jsx, FeedbackAdmin.jsx
│       │   ├── head-hr/ HeadHr*.jsx
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
│   ├── head_hr.py        # head-hr stats, stats, admins, candidates, jobs, applications
│   ├── db.py                 # PostgreSQL pool, get_conn, db_run, db_get, db_all, run_migrations, init_db
│   ├── utils.py              # JWT, authenticate_token, require_recruiter, require_candidate, require_head_hr, optional_authenticate_token
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

#### 3.2 Entry Points

| Role     | Entry |
|----------|--------|
| Frontend | `frontend/index.html` → `<script type="module" src="/src/main.jsx">` |
| React    | `frontend/src/main.jsx` (ReactDOM.createRoot, BrowserRouter, App) |
| Backend  | `backend/app.py` (`if __name__ == '__main__'`: app.run) |
| Unified  | Root `node start.js`: copies backend .env, venv+pip, npm install, starts backend then frontend, waits for health, opens browser |

---

### 4. Frontend Documentation

#### 4.1 Framework & Tooling

- **React 18** with `createRoot`.
- **Vite 5**: dev server `0.0.0.0:5173`, `@` alias to `./src`, build target `es2018`. No API proxy by default (CORS used).
- **Tailwind CSS** for styling; **Radix UI** (Avatar, Dialog, Dropdown, Progress, Separator, Slot) for primitives; **class-variance-authority**, **clsx**, **tailwind-merge** for variant styling.
- **React Router DOM 6**: `Routes`, `Route`, `Navigate`, `useLocation`; no data APIs (loaders/actions).

#### 4.2 Routing System

Defined in `App.jsx`. All page components are lazy-loaded via `React.lazy()`.

- **Public:** `/`, `/jobs`, `/support/faq`, `/support/contact`, `/support/hrms-feedback`, `/login`, `/login/applicant`, `/login/admin`, `/signup/applicant`, `/signup/admin`, `/forgot-password/:variant`, `/forgot-password/:variant/verify`, `/forgot-password/:variant/reset`.
- **Candidate-only (CandidateGuard):** `/profile/applicant`, `/settings/applicant`, `/applications`.
- **HR-only (PrivateRoute):** `/dashboard`, `/candidates`, `/settings`.
- **Admin (RecruiterGuard):** `/admin/bulk-resume-parser`, `/admin/feedback`.
- **Head of HR (HeadHrGuard):** `/head-hr`, `/head-hr/admins`, `/head-hr/candidates`, `/head-hr/candidates/:cid`, `/head-hr/jobs`, `/head-hr/jobs/:jdid`, `/head-hr/applications`, `/head-hr/applications/:id`, `/head-hr/settings`.
- **Redirects:** `/signup` → `/signup/applicant`, `/login/head-hr` → `/login/admin`.
- **Fallback:** `*` → `NotFound`.

`PrivateRoute` allows `auth.isLoggedIn && (auth.role === 'HR' || auth.role === 'head_hr')`. Navbar is hidden when `pathname.startsWith('/head-hr')`.

#### 4.3 State Management

- **No Redux.** Single **AppContext** (`context/AppContext.jsx`).
- **State:** jobs, jobsLoading, jobsError; auth (HR), applicantAuth, auth (HEAD_HR); applicantProfile, applicantApplications, applicantSavedJobs; user; token; backendHealthy; authLoading, authError.
- **Persistence:** localStorage for auth, applicantAuth, auth (HEAD_HR), applicantProfile, applicantApplications, applicantSavedJobs, user (keys in `STORAGE_KEYS`). Token is also in `tokenService` (in-memory + localStorage). Jobs are not persisted (fetched from API).
- **Actions:** loginHR, loginApplicant, loginHR; signup/verify/resend OTP (HR and applicant); forgot-password/verify/reset (HR and applicant); changePassword (HR and applicant); saveApplicantProfile, markApplicantProfileCompleted; applyToJobAsApplicant, toggleSaveJob; fetchJobs, addJob, updateJob, setJobEnabled; fetchApplicantData, fetchApplicationsForJob, fetchAllApplications; logout, logout.
- **Effects:** On mount, setUnauthorizedHandler(logout), setOnTokensRefreshed(update token state). Initial health check after 2s; then every 30s. Token hydrated from tokenService on load. Jobs fetched on mount and when auth/applicantAuth changes. Applicant data fetched when applicantAuth and token are set.

#### 4.4 Reusable UI System

Location: `frontend/src/components/ui/`. Barrel: `ui/index.js`.

- **Button** (buttonVariants), **Card** (CardHeader, CardFooter, CardTitle, CardDescription, CardContent), **Input**, **Textarea**, **Badge** (badgeVariants), **Avatar** (AvatarImage, AvatarFallback, AvatarWithInitials), **StatCard**, **Modal**, **Tabs** (TabPanel), **Skeleton**, **SkeletonLoader** (SkeletonCard, SkeletonList), **DropdownMenu** (Trigger, Content, Item, Label, Separator), **Dialog** (Trigger, Content, Header, Footer, Title, Description), **Progress**, **Table** (Header, Body, Footer, Head, Row, Cell, Caption), **Separator**.

Built with Radix primitives and Tailwind; variants via cva + cn.

#### 4.5 Guards & Authentication Flow

- **RecruiterGuard:** Renders children only if `auth.isLoggedIn && (auth.role === 'HR' || auth.role === 'head_hr')`; else `<Navigate to="/login/admin" replace />`.
- **CandidateGuard:** Renders children only if `applicantAuth?.isLoggedIn && !(auth?.isLoggedIn && auth?.role === 'HR')`; else `<Navigate to="/login/applicant" replace />`.
- **HeadHrGuard:** Renders children only if `auth (HEAD_HR)?.isLoggedIn`; else `<Navigate to="/login/admin" replace />`.

Login flows: HR and candidate each use email + password; HR and candidate signup use OTP email verification. Super admin uses same login page as admin; backend returns 403 if not `is_head_hr`. On 401/403 with token, `api.js` calls optional `onUnauthorized` (wired to logout) and on 403 attempts one token refresh via `POST /api/refresh` then retries the request.

#### 4.6 Services & API Integration

- **HTTP client:** `utils/api.js`.
  - **BASE_URL:** `import.meta.env.VITE_API_URL` (default `http://localhost:3000`), no trailing slash.
  - **apiRequest(path, { method, body, token, headers, timeoutMs, skipRetry }):** Uses `fetch` with `credentials: 'include'`. Timeout from `VITE_API_TIMEOUT_MS` (default 30s). Retry: max 2 attempts, exponential backoff (500ms base, 3s max); retries only on network/5xx/ECONNREFUSED/ETIMEDOUT/ENOTFOUND. On 403 with token, one refresh via `POST /api/refresh` then retry. On 401/403 with token, calls `setUnauthorizedHandler` (logout). Sets `Authorization: Bearer` from `token` or `tokenService.getToken()`.
- **Token:** `utils/tokenService.js` — getToken, setToken, getRefreshToken, setRefreshToken, clear; in-memory + localStorage (`jwtToken`, `refreshToken`).
- **adminService.js:** `getJobApplications(jobId)` → `apiRequest(\`/api/jobs/${jobId}/applications\`)`.
- **parsingApi.js:** Uses same BASE_URL (or `VITE_PARSING_API_URL` for separate parsing service); helpers for TOON arrays and date normalization (ensureArray, normalizeToYYYYMM, ensureStringArray, etc.).

#### 4.7 Key Components (Purpose, Props, Logic)

- **Navbar:** Top navigation; shows links by role (candidate vs HR); logout. Uses `useApp()` for auth state.
- **JobCard:** Displays one job; primary action: apply. Bookmark/save control removed from public Jobs UI (do not document as current).
- **ResumeUploadWithParsing:** File input for resume; calls parsing API; maps TOON to profile fields; used in ApplicantProfile.
- **ConnectionStatus:** Shows backend health (backendHealthy from context); may show offline/retry UI.
- **ErrorBoundary:** Catches React errors; renders fallback UI.
- **Toast (ToastProvider, useToast):** Global toast queue; used for auth errors and notifications.

---

### 5. Backend Documentation

#### 5.1 Framework & Structure

- **Flask** application in `app.py`. Loads `.env` from backend directory; runs `EnvValidator` at startup; configures CORS (origins from `FRONTEND_URLS`/`FRONTEND_URL` or localhost + local IP), Flask-Mail, `init_models()`, `init_db()`; registers blueprints.
- **Database:** `db.py` — PostgreSQL via psycopg3, connection pool (default 5), `get_conn()`, `db_run`, `db_get`, `db_all`. Placeholders normalized from `?` to `%s` for psycopg. Migrations: `schema_pg/*.sql` run in order by `run_migrations()`.

#### 5.2 API Design

- REST-style; JSON request/response. Auth: `Authorization: Bearer <access_token>`.
- HR auth and password reset under `/api` (auth_bp); candidate auth under `/api/candidate` (simple_candidate_auth_bp + candidate_bp). Same JWT secret for all roles; payload includes `role` and identity fields.

#### 5.3 Controllers / Services / Models

- **Blueprints:** auth, jobs, candidate (simple_candidate_auth + candidate), applications, sessions, parsing, support, feedback, admin, head_hr.
- **Models (SQLAlchemy):** `models/hr_auth.py`, `models/candidate_auth.py` for OTP verification tables (HRAuth, CandidateAuth). Main data access is raw SQL via `db.py`.
- **Services:** `ats_service` (match_candidate_to_job), `candidate_notification_service`, `bulk_parsing_service` (upload, progress, stream_download to BULK_PARSER_URL).

#### 5.4 Authentication & Authorization

- **utils.py:** `authenticate_token`: reads Bearer token, decodes JWT with `JWT_SECRET`, sets `request.user`; rejects if token is refresh type; 401 if no token, 403 if invalid/expired. `require_recruiter`: after authenticate_token, allows role `HR` or `head_hr`. `require_candidate`: allows role `candidate`. `require_head_hr`: allows role `head_hr`. `require_head_hr`: allows `head_hr` or `head_hr`. `optional_authenticate_token`: if Bearer present, validate and set request.user; else request.user = None.
- **JWT:** `build_jwt_payload(identity_dict, refresh=False)` adds `type`, `iat`, `exp`; access and refresh expiry from env (default 1h / 30d).

#### 5.5 Database Interaction

- All queries go through `db_run`, `db_get`, `db_all`. Schema in `schema_pg/01_schema.sql`: hr_signup, candidate_signup, candidate_education/certifications/experiences, hr_login, candidate_login, jobs, candidate_profiles, applications, support_requests, raw_files, parsed_resumes, parsed_jds, login_history, CandidateAuth, HRAuth. Additional tables in 02/03 for seed and employee_feedback.

---

### 6. API Documentation

#### 6.1 Endpoints Overview

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

**Head of HR — prefix `/api/head-hr`**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/login` | email, password | Super admin login |
| GET | `/stats` | Bearer head_hr/head_hr | Dashboard counts |
| GET | `/admins` | Bearer head_hr | List HR admins |
| POST | `/admins` | Bearer head_hr | Create admin |
| DELETE | `/admins/:hrid` | Bearer head_hr | Delete admin |
| GET | `/candidates`, `/candidates/:cid`, `/candidates/:cid/resume` | Bearer | List/detail/resume |
| DELETE | `/candidates/:cid` | Bearer head_hr | Delete candidate |
| GET | `/jobs`, `/jobs/:jdid` | Bearer | List/detail |
| DELETE | `/jobs/:jdid` | Bearer head_hr | Delete job |
| GET | `/applications`, `/applications/:id` | Bearer | List/detail |
| GET | `/settings` | Bearer | Settings (e.g. feature flags) |

#### 6.2 Request/Response Formats

- **Login (HR/candidate):** Request `{ email, password }`. Response `{ token, refresh_token?, user }` with `user` containing id, email, role, and optional profile fields.
- **Apply:** Request `{ jobId }`. Response 201 `{ message, status: 'applied', matchScore, shortlisted }`.
- **Jobs list:** Response array of job objects (jdid, title, company, location, salary, experience, description, enabled, posted_by, posted_on, company_name).
- **Applications list (candidate):** Array of `{ id, jobId, status, appliedAt, matchScore, shortlisted, atsReasoning, atsAnalysis, job }`.

#### 6.3 Error Handling

- 400: validation errors; body often `{ error: "message" }`.
- 401: missing or invalid token.
- 403: valid token but wrong role or refresh token used as access.
- 404: resource not found.
- 500: server error. Frontend `api.js` maps 500/503/network to user-friendly messages and retries on 5xx/network.

---

### 7. Data Flow

#### 7.1 User Input → API → Processing → UI

1. **User action** (e.g. click "Apply" on a job): Component calls context action `applyToJobAsApplicant(jobId)`.
2. **Context:** Validates applicantAuth, profile completed, resume and education present; performs optimistic update (applicantApplications[jobId] = { status: 'applied' }); calls `apiRequest('POST', '/api/applications', { body: { jobId }, token })`.
3. **api.js:** Builds URL, adds `Authorization: Bearer`, sends fetch. On 403, may call refresh then retry. On success, returns parsed JSON.
4. **Backend:** applications_bp receives request; authenticate_token + require_candidate; validates job and profile; fetches stored parsed_resume and parsed_jd; inserts application row; starts background thread for ATS; returns 201.
5. **Context:** On success, calls fetchApplicantData() to sync applications; returns { ok: true }. On failure, reverts optimistic update and returns { ok: false, message }.
6. **UI:** Component may show toast or update button state from context state (applicantApplications, jobs).

#### 7.2 Token Refresh Flow

1. Request returns 403 with a token that was sent.
2. api.js calls tryRefresh(): POST /api/refresh with refresh_token from tokenService.
3. Backend returns new token and refresh_token; tokenService and onTokensRefreshed (context setToken) update state.
4. Original request is retried once with new access token.

---

### 8. Core Workflows

#### 8.1 User Authentication (HR)

1. User opens `/login/admin`, enters email/password.
2. Frontend calls `loginHR(email, password)` → POST `/api/login` with `{ email, password }`.
3. Backend validates credentials against hr_signup, issues JWT access + refresh, returns token and user (role, email, company, etc.).
4. Frontend sets token in tokenService and state; sets auth to { isLoggedIn: true, role, email, ... }; persists to localStorage.
5. Redirect or navigation to `/dashboard`; PrivateRoute allows access.

#### 8.2 Job Application Flow

1. Candidate has completed profile and parsed resume. On Jobs or JobCard, clicks Apply.
2. Frontend: applyToJobAsApplicant(jobId) → optimistic update → POST `/api/applications` with { jobId }, Bearer token.
3. Backend: Validates job and candidate profile; ensures parsed_resume exists; creates application row (status 'applied'); starts background ATS (in-process or n8n); returns 201.
4. Frontend: fetchApplicantData() syncs applications; UI shows "Applied" and optional match score when ATS completes (polling or refetch).

#### 8.3 Resume Upload & Parsing

1. Candidate on ApplicantProfile uploads file; ResumeUploadWithParsing sends file to POST `/api/parse/resume` (Bearer).
2. Backend: parsing_routes stores raw file, extracts text, calls LLM for TOON, stores in parsed_resumes (and links candidate_id if known); returns TOON + id.
3. Frontend: parsingApi helpers normalize TOON (ensureArray, normalizeToYYYYMM); profile form is prefilled; saveApplicantProfile can send profile + optional new file to POST `/api/candidate/profile`.

#### 8.4 Admin Operations

1. **Bulk resume parser:** Admin opens `/admin/bulk-resume-parser`, uploads files → POST `/api/admin/bulk-parse/upload`. Backend proxies to BULK_PARSER_URL or uses in-process service. Frontend polls GET `/api/admin/bulk-parse/progress/:job_id`, then GET `/api/admin/bulk-parse/download/:job_id` for Excel.
2. **View candidates:** HR opens `/candidates` or job detail; frontend fetches GET `/api/jobs/:id/applications`; table shows candidates; resume via GET `/api/jobs/:id/applications/:candidate_id/resume`.

---

### 9. Key Modules Deep Dive

#### 9.1 AppContext (frontend/src/context/AppContext.jsx)

- **Purpose:** Single source of truth for auth (HR, applicant, super admin), jobs, applicant profile/applications/saved jobs, and all mutations that call the API.
- **Design:** useMemo value object to avoid unnecessary re-renders; many useEffect hooks for persistence and hydration (localStorage + storage event). fetchApplicantData is useCallback with [token, applicantAuth.isLoggedIn] to avoid loops.
- **Edge cases:** saveApplicantProfile saves locally first; on server failure returns ok: true with warning so data is not lost. applyToJobAsApplicant reverts optimistic update on API failure. Super admin login clears HR and applicant auth so only one session type is active.

#### 9.2 api.js (frontend/src/utils/api.js)

- **Purpose:** Central fetch wrapper with retry, timeout, refresh on 403, and global logout on 401/403.
- **Logic:** performRequest builds headers (Bearer from token or tokenService), sends fetch; on 403 with token, tryRefresh() then retry once; on auth failure invokes onUnauthorized. apiRequest loop: retries up to maxRetries on retryable errors (network, 5xx, ECONNREFUSED, etc.); does not retry 4xx or after refresh.
- **Edge cases:** FormData not sent as JSON; timeout uses AbortController; production warning if BASE_URL is http.

#### 9.3 applications.py (backend)

- **Purpose:** Apply to job and receive ATS results (in-process thread or n8n callback).
- **Apply flow:** Validates job, no duplicate application, profile completed; loads parsed_resume (by candidate_id or uploader_id) and parsed_jd (or builds minimal TOON from job row); inserts application; spawns thread for _run_ats_and_update_application (match_candidate_to_job or n8n trigger); returns 201 immediately.
- **ATS callback:** POST /api/applications/ats/result; optional X-N8N-Callback-Secret; updates application match_score, shortlisted, ats_reasoning, ats_analysis, status (if still 'applied').

#### 9.4 db.py (backend)

- **Purpose:** PostgreSQL connection pool and query helpers.
- **Design:** ConnectionPool with Queue; get_connection checks pool, validates with SELECT 1, or creates new connection. get_conn context manager commits on success, rollback on exception, always returns connection to pool. run_migrations runs schema_pg/*.sql in order; idempotent column adds for is_head_hr, is_head_hr.

---

### 10. Environment & Setup

#### 10.1 Installation

From repo root:

```bash
## 1. Copy backend env
cp backend/.env.example backend/.env   # or start.js does this

## 2. Edit backend/.env: POSTGRES_* or DATABASE_URL

## 3. Start (installs backend venv + pip, frontend npm, starts both, opens browser)
node start.js
```

Manual backend: `cd backend && python -m venv venv && .\venv\Scripts\Activate && pip install -r requirements.txt && python app.py`  
Manual frontend: `cd frontend && npm install && npm run dev`

#### 10.2 Environment Variables

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

#### 10.3 Build & Deployment

- **Frontend:** `npm run build` (Vite); output in `frontend/dist`. Serve with any static host; SPA redirect for * to index.html (e.g. `public/_redirects` for Netlify).
- **Backend:** `python app.py` or gunicorn (see gunicorn.conf.py). Set FRONTEND_URLS for CORS in production.

---

### 11. Design Patterns & Practices

- **Service layer:** Backend: blueprints as controllers; db.py as data access; services (ats_service, bulk_parsing_service) for external or complex logic. Frontend: api.js as HTTP layer; context as application service.
- **Guards:** Route-level components (RecruiterGuard, CandidateGuard, HeadHrGuard) enforce role before rendering page.
- **Optimistic updates:** applyToJobAsApplicant updates UI immediately and reverts on failure.
- **Persistence:** Critical client state (auth, profile, applications, saved jobs) in localStorage with storage event sync across tabs.
- **Lazy loading:** All route components lazy-loaded to reduce initial bundle.
- **Retry and refresh:** API retry for transient failures; single token refresh on 403 then retry.

---

### 12. Performance Considerations

- **Backend:** Connection pool (5) avoids per-request connection cost; init_db at startup (not lazy) prevents first-request delay. ATS run in background thread so apply response is fast.
- **Frontend:** Lazy routes, 30s health check interval, cached health result. Large context can cause broad re-renders; consider splitting or selectors if profiling shows issues.
- **Bottlenecks:** LLM parsing (resume/JD) can be slow; bulk parser depends on external service. Database: ensure indexes on applications(shortlisted, match_score), jobs(posted_by, enabled).

---

### 13. Security Analysis

- **Auth:** JWT in localStorage and in-memory; vulnerable to XSS. Comments in code recommend HttpOnly cookies for production. Refresh token stored same way; rotation on refresh.
- **Token handling:** Backend rejects refresh token used as access; expiry enforced. Frontend sends Bearer only when present; 401/403 trigger logout.
- **Input validation:** Backend validates email format, password strength (length, upper/lower/digit/special), required fields. File upload: extension and size limits (parsing, feedback).
- **Candidate forgot-password:** Frontend calls `/api/candidate/forgot-password` etc.; **backend does not implement these routes** — gap and possible 404 for users.
- **ATS callback:** Optional N8N_CALLBACK_SECRET to authenticate n8n callback. Without it, any client could POST /api/applications/ats/result.
- **CORS:** Explicit allow list (no *); supports_credentials true. Good for credentialed requests.

---

### 14. Risks & Technical Debt

- **Candidate forgot-password:** Frontend expects backend routes that do not exist; implement or remove UI.
- **JWT in localStorage:** Prefer HttpOnly cookies for production.
- **Large AppContext:** One context for all state may cause unnecessary re-renders; consider splitting or useReducer/selectors.
- **Dual ATS paths:** In-process ATS and n8n callback; two code paths to maintain and test.
- **SQLAlchemy + raw SQL:** HR OTP uses SQLAlchemy (HRAuth); candidate OTP uses raw SQL (CandidateAuth) to avoid session issues. Inconsistent pattern.
- **Error handling:** Some routes return 500 with generic message; structured error codes would help frontend.

---

### 15. Recommendations

1. **Implement candidate forgot-password** in backend (e.g. in candidate_bp or simple_candidate_auth) to match frontend, or remove the flow from UI.
2. **Move JWT to HttpOnly cookies** for production; keep credentials: 'include'; remove token from localStorage and tokenService for access token.
3. **Add request/response logging** (e.g. request id, duration) for debugging and audits.
4. **Split or scope AppContext** (e.g. AuthContext, JobsContext) or use selectors to reduce re-renders.
5. **Unify ATS integration** behind one interface (e.g. always enqueue job, worker calls in-process or n8n) to simplify code and testing.
6. **Document N8N_CALLBACK_SECRET** and recommend setting it when using n8n.
7. **Add API versioning** (e.g. /api/v1) if multiple clients or breaking changes are expected.

---

## Backend

> **Update (public apply):** Candidate login/signup OTP APIs are removed.
> Applicants apply via `POST /api/jobs/<job_id>/apply` (passwordless `candidate_signup`).
> Resume autofill uses `POST /api/parse/resume/public`. Migration `08_public_apply_purge_candidate_auth.sql` drops `CandidateAuth` / `candidate_login` and the password column.

This document describes the backend directory structure, the purpose of each file and folder, and how the code works.

---

### 1. Backend Directory Structure

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
├── head_hr.py            # Super-admin blueprint: login, stats, admins, candidates, jobs, applications
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
    ├── 03_employee_feedback.sql
    └── … through 13_site_assets.sql  # landing hero MP4 in Postgres BYTEA (site_assets)
```

---

### 2. App Entry and Configuration

#### 2.1 `app.py`

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
   Then registers blueprints: auth_bp (`/api`), jobs_bp (`/api/jobs`), simple_candidate_auth_bp (`/api/candidate`), candidate_bp (`/api/candidate`), applications_bp (`/api/applications`), sessions_bp (`/api/sessions`), parsing_bp (`/api`), support_bp (`/api/support`), feedback_bp (`/api/feedback`), admin_bp (`/api/admin`), head_hr_bp (`/api/head-hr`).

9. **Run:** If `__name__ == '__main__'`, reads PORT and FLASK_DEBUG, optionally disables reloader, runs `app.run(host='0.0.0.0', port=..., debug=..., use_reloader=..., threaded=True)`.

---

### 3. Database Layer

#### 3.1 `db.py`

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

- **run_migrations():** Reads all `.sql` files from `schema_pg/` in order, strips comments and empty lines, splits by `;` (keeping `DO $$ ... END $$;` as one statement), executes each. Then ensures columns `is_HEAD_HR` and `is_head_hr` exist on `hr_signup` (idempotent ALTER).
- **init_db():** Just calls `run_migrations()`.

---

### 4. Auth and Authorization Helpers

#### 4.1 `utils.py`

**Password:** `validate_password_strength(password)` — enforces min length 8, at least one upper, one lower, one digit, one special character. Returns `(True, None)` or `(False, error_message)`.

**JWT:**

- `JWT_SECRET`, `JWT_ACCESS_EXPIRY_SECONDS`, `JWT_REFRESH_EXPIRY_SECONDS` from env (defaults: 1h access, 30d refresh).
- `build_jwt_payload(identity_dict, refresh=False)` — copies identity, adds `type` ('access' or 'refresh'), `iat`, `exp`.

**Decorators:**

- **authenticate_token(f):** Reads `Authorization: Bearer <token>`. If no token, returns 401. Decodes JWT with JWT_SECRET; if `type == 'refresh'` returns 403 (refresh token cannot be used as access). Sets `request.user` to the decoded payload and calls `f`.
- **optional_authenticate_token(f):** If no Bearer header, sets `request.user = None` and calls `f`. If Bearer present, same decode as above; invalid/expired/refresh-type returns 401.
- **require_recruiter(f):** Must be used after authenticate_token. Checks `request.user` and that `role` is 'HR' or 'head_hr'; else 403.
- **require_candidate(f):** Requires `request.user` and `role == 'candidate'`; else 403.
- **require_HEAD_HR(f):** Requires `request.user` and `role == 'HEAD_HR'`; else 403.
- **require_head_hr(f):** Requires role 'head_hr' or 'HEAD_HR'; else 403.

---

### 5. Auth Blueprint (HR) — `auth.py`

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

### 6. Jobs Blueprint — `jobs.py`

**Prefix:** `/api/jobs`.

**Helpers:**

- `_send_notification(...)` — delegates to candidate_notification_service to send email (e.g. profile viewed, shortlisted).
- `_resume_bytes(data)` — normalizes resume blob to bytes for response.
- `generate_jdid_from_title(title)` — builds jdid like DA001, SD002 from first letters of words in title and next sequence number from DB.

**Routes:**

- **GET /** (`optional_authenticate_token`): List jobs. If user is HR (role HR and has hrId), selects jobs where posted_by = hrId, optionally filtered by company from JWT. Otherwise selects jobs where enabled = true or null, ordered by posted_on. Returns array of job objects (id, title, company, location, salary, experience, description, enabled, postedOn).
- **GET /all** (`authenticate_token`, `require_recruiter`): All jobs for this HR (posted_by = hrId).
- **GET /:job_id** (`optional_authenticate_token`): Single job. HR can only see own jobs; others only enabled. Returns 404 if not found or access denied.
- **GET /:job_id/applications** (`authenticate_token`, `require_recruiter`): Verifies job belongs to hrId; selects applications with candidate profile and ATS fields; for each candidate loads education, experiences, certifications; returns formatted list (matchScore, shortlisted, atsReasoning, atsAnalysis, fullName, email, resumeUrl, education, experiences, certifications). If job not found, returns 200 with empty list.
- **GET /:job_id/applications/:candidate_id/resume** (`authenticate_token`, `require_recruiter`): Verifies job and application; gets resume from candidate_profiles; returns binary response with Content-Disposition inline.
- **POST /** (`authenticate_token`, `require_recruiter`): Body: job fields. Generates jdid via generate_jdid_from_title; inserts into jobs (title, company, location, salary, experience, description, enabled, posted_by).
- **PUT /:job_id** (`authenticate_token`, `require_recruiter`): Verifies job belongs to hrId; updates job fields.
- **PATCH /:job_id/enabled** (`authenticate_token`, `require_recruiter`): Body: enabled. Updates jobs.enabled.
- **DELETE /:job_id** (`authenticate_token`, `require_recruiter`): Deletes job if owned by hrId.
- **POST /:job_id/applications/:candidate_id/viewed** (`authenticate_token`, `require_recruiter`): Marks application as profile viewed; sends notification email; updates application status (e.g. profile_viewed).
- **PATCH /:job_id/applications/:candidate_id/status** (`authenticate_token`, `require_recruiter`): Body: action (shortlist | reject). Sends notification email and updates application status and shortlisted flag.

---

### 7. Candidate Blueprint — `candidate.py`

**Prefix:** `/api/candidate`. Note: candidate signup/login/verify/resend are in `routes/simple_candidate_auth.py` under the same prefix.

**Routes:**

- **POST /logout:** Reads Bearer token; calls sessions_service to deactivate session; returns success.
- **POST /change-password** (`authenticate_token`, `require_candidate`): Body: currentPassword, newPassword. Validates new password strength; loads candidate_signup; verifies current password with bcrypt; hashes new password and updates candidate_signup.
- **GET /profile** (`authenticate_token`, `require_candidate`): Selects from candidate_profiles (no resume binary); returns parsed profile (fullName, email, education, experiences, certifications, completed, etc.) or default empty shape. Uses a `parse_profile` helper to map DB columns to camelCase and structure.
- **POST /profile** (`authenticate_token`, `require_candidate`): Accepts JSON or multipart/form-data. For multipart, reads form and parses JSON fields (education, certifications, experiences). Reads resume from request.files['resume'] or base64 from JSON. If profile exists: if new resume bytes provided, UPDATE with resume; else UPDATE without resume. If no profile, INSERT. Then deletes and re-inserts candidate_education, candidate_certifications, candidate_experiences from the request arrays. Returns success.
- **GET /resume:** Returns the resume binary for the authenticated candidate (from candidate_profiles).
- **GET /profile/:candidate_id** (`authenticate_token`, `require_recruiter`): Same as GET /profile but for a given candidate_id so HR can view candidate profile.

**Note:** Candidate forgot-password endpoints (`/api/candidate/forgot-password`, verify-otp, reset-password) are not implemented in this blueprint; the frontend calls them but they return 404.

---

### 8. Simple Candidate Auth — `routes/simple_candidate_auth.py`

**Prefix:** `/api/candidate`. Registered before candidate_bp so signup/login take precedence.

**Routes:**

- **POST /signup:** Body: name, email, password. Validates; hashes password; generates OTP and expiry; inserts or updates CandidateAuth table (raw SQL, not SQLAlchemy) with is_verified false; sends OTP email.
- **POST /verify-otp:** Body: email, otp. Loads CandidateAuth; validates OTP and expiry; marks verified; creates or updates candidate_signup (name, email, password from CandidateAuth). Returns message and cid.
- **POST /resend-otp:** Body: email. New OTP and expiry; updates CandidateAuth and sends email.
- **POST /login:** Body: email, password. Selects candidate_signup by email; verifies password with bcrypt; builds JWT access and refresh (identity: id=cid, email, role=candidate); optionally loads profile for user object; returns token, refresh_token, user.

---

### 9. Applications Blueprint — `applications.py`

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

### 10. Parsing Blueprint — `parsing_routes.py`

**Prefix:** `/api`.

**Config:** ALLOWED_EXTENSIONS (pdf, doc, docx), MAX_FILE_SIZE (10MB), MIME_TYPE_MAP.

**Helpers:** `allowed_file(filename)`, `get_mime_type(filename)`, `calculate_confidence(toon, doc_type)` — scores resume/JD TOON completeness for a 0–1 confidence.

**Routes:**

- **POST /parse/resume** (`authenticate_token`): Expects multipart file in `request.files['file']`. Validates extension and size. Gets uploader_id and role from JWT (candidate or admin). Computes file hash; if get_cached_parsing_result returns a cached parse, links parsed_resumes.candidate_id if candidate and returns cached toon/confidence. Otherwise: store_raw_file, extract_text (text_extraction), call LLM (llm_service) to get TOON, compute confidence, store_parsed_resume, link candidate_id for candidates; returns raw_file_id, parsed_id, confidence, toon.
- **POST /parse/jd** (`authenticate_token`): Similar flow for JD: store raw file, extract text, LLM to get JD TOON, store_parsed_jd, return id and toon.
- **GET /parsed/resume/:id** (`authenticate_token`): Returns parsed resume by id (toon, confidence) if the user is allowed (owner or HR).
- **GET /parsed/jd/:id** (`authenticate_token`): Same for JD.

---

### 11. Support and Feedback Blueprints

#### 11.1 `support.py` — Prefix `/api/support`

- **POST /submit:** Body: name, email, subject, message, optional user_id, user_type, priority. Validates; inserts into support_requests; optionally sends email to SUPPORT_NOTIFICATION_EMAIL. Returns id.
- **GET /my-requests** (Bearer): Returns requests for request.user.
- **GET /all** (Bearer, HR): Returns all support requests.
- **GET /:request_id** (Bearer): Returns one request.
- **PATCH /:request_id/status** (Bearer): Updates status.

#### 11.2 `feedback_routes.py` — Prefix `/api/feedback`

- **POST /submit:** Body: employee_name, employee_id, department, feedback_type, severity, module, description, optional screenshot file. Validates; saves to employee_feedback table; uploads file to UPLOAD_FOLDER/feedback; sends email to FEEDBACK_NOTIFICATION_EMAIL. Returns id.
- **GET /list** (Bearer, HR): Returns list of feedback with optional status filter.
- **PATCH /:feedback_id/status** (Bearer, HR): Updates feedback status.

---

### 12. Admin and Super-Admin Blueprints

#### 12.1 `modules/admin/routes.py` — Prefix `/api/admin`

- **POST /bulk-parse/upload** (`authenticate_token`, `require_recruiter`): Accepts multipart files; validates extension (pdf, doc, docx); calls bulk_parsing_service.upload_files; returns job id or error (503 if BULK_PARSER unreachable).
- **GET /bulk-parse/progress/:job_id** (`authenticate_token`, `require_recruiter`): Proxies to bulk_parsing_service.get_progress.
- **GET /bulk-parse/download/:job_id** (`authenticate_token`, `require_recruiter`): Streams Excel from bulk_parsing_service.stream_download; returns attachment.
- **GET /job-matches** (`authenticate_token`, `require_recruiter`): Returns jobs posted by this HR with application counts and shortlisted counts.

#### 12.2 `head_hr.py` — Prefix `/api/head-hr`

- **POST /login:** Body: email, password. Looks up hr_signup by email; verifies password; checks is_HEAD_HR; issues JWT with role 'HEAD_HR'. Returns token and user.
- **GET /stats** (`authenticate_token`, `require_head_hr`): Counts hr_signup, candidate_signup, jobs, applications, active jobs, shortlisted. Returns JSON.
- **GET /admins** (`authenticate_token`, `require_HEAD_HR`): List HR admins.
- **POST /admins** (`authenticate_token`, `require_HEAD_HR`): Create admin (signup flow).
- **DELETE /admins/:hrid** (`authenticate_token`, `require_HEAD_HR`): Delete HR admin.
- **GET /candidates**, **GET /candidates/:cid**, **GET /candidates/:cid/resume** (`authenticate_token`, require_head_hr or HEAD_HR): List/detail/resume.
- **DELETE /candidates/:cid** (`authenticate_token`, `require_HEAD_HR`): Delete candidate.
- **GET /jobs**, **GET /jobs/:jdid** (`authenticate_token`): List/detail jobs.
- **DELETE /jobs/:jdid** (`authenticate_token`, `require_HEAD_HR`): Delete job.
- **GET /applications**, **GET /applications/:id** (`authenticate_token`): List/detail applications.
- **GET /settings** (`authenticate_token`): Returns settings (e.g. feature flags).

Many GET routes use `allow_options_no_auth` so OPTIONS preflight succeeds without auth.

---

### 13. Sessions — `sessions_routes.py`

**Prefix:** `/api/sessions`.

- **GET /my-sessions** (Bearer): Returns active sessions for the user.
- **GET /my-history** (Bearer): Returns login history.
- **POST /logout-session** (Bearer): Deactivates one session by token/session id.
- **POST /logout-all** (Bearer): Deactivates all other sessions for the user.

Implementation details (session storage, deactivation) live in `sessions_service.py`.

---

### 14. Helpers and Services (Summary)

#### 14.1 `helpers/otp_utils.py`

- **generate_otp():** Returns a 6-digit string.
- **is_valid_email(email):** Simple format check.
- **send_email_otp(email, otp, user_type):** Uses Flask-Mail to send OTP email (template from email_templates).
- **parse_otp_expiry(value):** Converts DB timestamp to datetime.
- **utc_now_aware(), normalize_to_utc_aware(dt):** Timezone-aware UTC for PostgreSQL comparison.

#### 14.2 `helpers/email_utils.py` and `email_templates.py`

- **send_notification_email(to, subject, body, html=...):** Sends via Flask-Mail. Used for OTP, password changed, login alert, support received, feedback received.

#### 14.3 `services/ats_service.py`

- **match_candidate_to_job(candidate_id, job_id, parsed_resume, parsed_jd, apply_id):** Can call internal matching logic or external ATS_API_URL. Returns (success, result). Result may contain json_output (overall_match_score, decision, final_reasoning) and toon_output. Used by applications blueprint in the background thread after apply.

#### 14.4 `services/candidate_notification_service.py`

- **send_and_get_output(hr_action, candidate_name, candidate_email, job_title, company_name, application_id, timestamp):** Sends email to candidate (e.g. “Your profile was viewed”, “You have been shortlisted”). Returns dict with profile_update and status_db for the application status to set.

#### 14.5 `services/bulk_parsing_service.py`

- **upload_files(files_list, append):** POSTs to BULK_PARSER_URL; returns (success, result). result may contain job_id or error/code (e.g. BULK_PARSER_NOT_CONFIGURED).
- **get_progress(job_id):** GET progress from BULK_PARSER_URL.
- **stream_download(job_id):** GET Excel stream; returns (iterator, filename, content_type) or (False, error_payload).

#### 14.6 `toon.py`

- **toon_loads_flex(s):** Parses JSON from string or bytes; handles TOON structure. Used when reading parsed_resume/parsed_jd or ats_analysis from DB.
- **toon_dumps(obj):** Serializes to JSON string for storage.

#### 14.7 `parsing_utils.py`

- **compute_file_hash(data):** Hash for duplicate detection.
- **store_raw_file(...):** Inserts into raw_files; returns record with id.
- **store_parsed_resume(...)** / **store_parsed_jd(...):** Inserts into parsed_resumes/parsed_jds with toon, confidence, model_version.
- **get_cached_parsing_result(file_hash, uploader_id, doc_type):** Returns existing parsed record if same file was parsed before.
- **validate_toon_format(toon, doc_type):** Validates required fields for resume or JD TOON.

#### 14.8 `llm_service.py`

- **call_llm(...):** Sends content to LLM (e.g. Grok via XAI); uses llm_key_manager for key rotation; returns parsed TOON or error.
- **classify_document(text):** Classifies as resume or JD. Used in parsing flow.

#### 14.9 `text_extraction.py`

- **extract_text(file_data, filename):** Extracts text from PDF (e.g. PyPDF2 or pdfplumber) or DOC/DOCX (python-docx, etc.). Returns plain text for LLM.

---

### 15. Data Flow Summary

1. **Request:** Flask receives HTTP request; CORS handles preflight; route matches a blueprint.
2. **Auth:** If the route uses `authenticate_token`, the decorator reads Bearer token, decodes JWT, sets `request.user`. If `require_recruiter`/`require_candidate`/etc., checks role and returns 403 if wrong.
3. **Handler:** View function reads `request.get_json()` or `request.files`/`request.form`; validates input; uses `db_get`/`db_all`/`db_run` for DB; may call helpers (email, ATS, parsing).
4. **Response:** Returns `jsonify(...)` or `Response(body, mimetype=..., headers=...)`. Exceptions can be caught and converted to 500 with a generic message.
5. **Background:** Apply flow inserts the application and starts a thread for ATS; parsing may call LLM and store TOON; notifications are sent via Flask-Mail or candidate_notification_service.

This completes the backend structure and code documentation.

---

## Frontend

> **Update (public apply):** Candidate accounts and `CandidateGuard` / applicant login pages are removed.
> Job applications use a public Apply form on `/jobs` (`ApplyJobModal`) with resume autofill via `POST /api/parse/resume/public`.
> Staff login remains at `/login` → `/login/admin`. Forgot-password is admin-only.

This document describes the frontend directory structure, the purpose of each file and folder, and how the code works.

---

### 1. Frontend Directory Structure

```
apps/frontend/
├── index.html              # HTML shell; mounts React via /src/main.jsx
├── package.json            # Dependencies and scripts (dev, build, preview)
├── vite.config.js          # Vite config: React plugin, @ alias, server port 5173
├── tailwind.config.js      # Tailwind theme and content paths
├── postcss.config.js       # PostCSS (Tailwind, autoprefixer)
├── jsconfig.json           # Path alias @ -> ./src for imports
├── public/
│   └── _redirects          # SPA fallback (e.g. Netlify)
└── src/
    ├── main.jsx            # React entry: createRoot, BrowserRouter, App
    ├── App.jsx             # App tree: providers, Navbar, Routes, guards
    ├── index.css            # Tailwind directives and global styles
    ├── context/
    │   └── AppContext.jsx   # Global state and API actions
    ├── guards/
    │   ├── RecruiterGuard.jsx
    │   ├── CandidateGuard.jsx
    │   ├── HeadHrGuard.jsx
    │   └── CeoGuard.jsx
    ├── layouts/
    │   ├── MainLayout.jsx
    │   ├── DashboardLayout.jsx
    │   ├── AdminLayout.jsx
    │   └── (in pages/head-hr) HeadHrLayout.jsx
    ├── pages/               # One component per route (lazy-loaded)
    ├── components/          # Reusable and feature components
    │   └── ui/              # Primitive UI (Button, Card, Input, etc.)
    ├── services/
    │   ├── adminService.js
    │   └── bulkParsingService.js
    ├── utils/               # API client, token, health, parsing helpers
    └── hooks/
        └── useAsyncAction.js
```

---

### 2. Entry and App Shell

#### 2.1 `index.html`

- Single HTML page. The root `<div id="root">` is where React mounts.
- Script: `<script type="module" src="/src/main.jsx">` — Vite serves this as the app entry.

#### 2.2 `main.jsx` — React Entry

**What it does:**

- Imports React, ReactDOM, `BrowserRouter`, `App`, and global CSS.
- Creates the root with `ReactDOM.createRoot(document.getElementById('root'))`.
- Renders inside `React.StrictMode` and `BrowserRouter` so the whole app has client-side routing.
- Renders `<App />` as the top-level component.

**Why BrowserRouter:** All routes are client-side; the backend does not serve HTML for these paths.

#### 2.3 `App.jsx` — Routes, Providers, and Guards

**Structure:**

1. **Lazy imports**  
   Every page component is loaded with `React.lazy(() => import('./pages/...'))` so each route’s code is in a separate chunk and loaded on first visit.

2. **PrivateRoute (inline)**  
   - Uses `useApp()` to read `auth`.
   - Allows access only if `auth.isLoggedIn && (auth.role === 'HR' || auth.role === 'head_hr')`.
   - Otherwise redirects to `/login` with `<Navigate to="/login" replace />`.

3. **Component tree:**
   - `AppProvider` (wraps everything)
   - `ToastProvider`
   - `ErrorBoundary`
   - `ConnectionStatus`
   - Main div with optional `Navbar` (hidden when path starts with `/head-hr`)
   - `ErrorToasts` (shows `authError` from context as a toast)
   - `<main>` with `<Suspense>` and `<Routes>`
   - Footer (hidden on head-hr routes)

4. **Routes:**
   - Public: `/`, `/jobs`, `/support/*`, `/login`, `/login/applicant`, `/login/admin`, `/signup/*`, `/forgot-password/:variant` (request, verify, reset).
   - Candidate-only: wrapped in `<CandidateGuard>` — `/profile/applicant`, `/settings/applicant`, `/applications`.
   - HR-only: wrapped in `<PrivateRoute>` — `/dashboard`, `/candidates`, `/settings`.
   - Admin: wrapped in `<AdminGuard>` — `/admin/bulk-resume-parser`, `/admin/feedback`.
   - Head of HR: wrapped in `<HeadHrGuard>` — all `/head-hr/*` routes.
   - Catch-all `*` → `NotFound`.

5. **ErrorToasts**  
   Subscribes to `authError` from `useApp()` and shows it with `toast.push(authError, { type: 'error' })` when it changes.

---

### 3. Context: Global State and API

#### 3.1 `context/AppContext.jsx`

**Purpose:** Single source of truth for auth (HR, applicant, super admin), jobs list, applicant profile, applications, saved jobs, and all actions that call the API.

**State (summary):**

- `jobs`, `jobsLoading`, `jobsError`
- `auth` (HR: isLoggedIn, role, email, fullName, company)
- `applicantAuth` (isLoggedIn, email)
- `superAdminAuth` (isLoggedIn, email)
- `token` (access token string)
- `user` (current user object from login)
- `applicantProfile` (full profile shape: education, experiences, certifications, resumeFileName, etc.)
- `applicantApplications` (map: jobId → { status, shortlisted })
- `applicantSavedJobs` (map: jobId → true)
- `backendHealthy`, `authLoading`, `authError`

**Persistence:**  
`STORAGE_KEYS` define localStorage keys. Auth, applicantAuth, applicantProfile, applicantApplications, applicantSavedJobs, and user are written to localStorage in `useEffect` and rehydrated on load.

**Key logic:**

- **loginHR / loginApplicant:** Call the corresponding login API, then set token (and refresh in tokenService), user, and the relevant auth state; persist auth to localStorage. HEAD_HR uses `loginHR` like other staff roles.
- **saveApplicantProfile:** Updates local state and localStorage first. If logged in, sends profile to `POST /api/candidate/profile` (JSON or FormData if resume file). Then fetches profile again and merges into state. On server error, still returns success with a warning so the user knows data was saved locally.
- **applyToJobAsApplicant:** Checks profile completed, resume and education present. Does an optimistic update (sets applicantApplications[jobId]), then `POST /api/applications` with jobId. On success calls `fetchApplicantData()`; on failure reverts the optimistic update.
- **fetchJobs:** GET `/api/jobs` with optional token (so HR sees only their jobs). Sets jobs array or jobs.jobs from response.
- **fetchApplicantData:** GET profile and GET applications when applicant is logged in; normalizes applications into the applicantApplications map and writes to localStorage.
- **setUnauthorizedHandler / setOnTokensRefreshed:** Set in a mount effect. First is `logout`; second updates `token` state when api.js refreshes the token.

**useMemo:** The context value is built with `useMemo` so that only when the listed dependencies change does the value object change, reducing unnecessary re-renders of consumers.

---

### 4. Guards

Guards are small wrapper components that either render `children` or redirect.

#### 4.1 `guards/AdminGuard.jsx`

- Uses `useApp()` to read `auth`.
- If `!auth.isLoggedIn` or role is not `HR` or `head_hr`, returns `<Navigate to="/login/admin" replace />`.
- Otherwise returns `children`.

#### 4.2 `guards/CandidateGuard.jsx`

- Uses `applicantAuth` and `auth`.
- `isHr = auth?.isLoggedIn && auth?.role === 'HR'`.
- `isCandidate = applicantAuth?.isLoggedIn && !isHr`.
- If not `isCandidate`, redirects to `/login/applicant`; otherwise renders `children`.

#### 4.3 `guards/HeadHrGuard.jsx`

- If `!auth.isLoggedIn` or role is not `HEAD_HR`, redirects to `/login/admin`.
- Otherwise renders `children`.

---

### 5. Layouts

#### 5.1 `layouts/MainLayout.jsx`

- Renders a full-height flex column: `Navbar`, `<main><Outlet /></main>`, and a footer.
- `Outlet` is where child routes (e.g. Home, Jobs) render.

#### 5.2 `layouts/DashboardLayout.jsx`

- Same idea as MainLayout but wraps the main content in `PageContainer` for consistent max-width and padding.
- Used for HR dashboard-style pages.

#### 5.3 `layouts/AdminLayout.jsx`

- Used for admin sections (e.g. bulk parser, feedback); provides Navbar and Outlet (and optionally sidebar) so admin pages share the same chrome.

---

### 6. Pages (Selected) — Purpose and Code

#### 6.1 `pages/Home.jsx`

- **Purpose:** Landing page with hero and search.
- **Code:** Uses `useNavigate()`. Renders `<Hero onSearch={handleSearch}>`. `handleSearch` builds `URLSearchParams` from `keywords` and `location` and navigates to `/jobs?q=...&loc=...`.

#### 6.2 `pages/Jobs.jsx`

- **Purpose:** List jobs with client-side filter and apply/save actions.
- **State:** `applyError`, `applyingJobId`; reads from context: jobs, applicantAuth, applicantProfile, jobsError, jobsLoading, fetchJobs, applicantApplications, applicantSavedJobs, toggleSaveJob, applyToJobAsApplicant, auth, superAdminAuth.
- **Query:** Reads `location.search` and builds `query = { keywords, location }` from `q` and `loc`.
- **Filtering:** `useMemo` filters `jobs` by `enabled !== false`, then by keywords (title/company/description) and location (substring match).
- **Search:** `handleSearch` updates URL with new `q` and `loc` so the same filter logic applies and the URL is shareable.
- **Error handling:** If `jobsError`, shows a retry banner and calls `fetchJobs` after 5 seconds. If `applyError`, shows message and optional “Complete profile” link to `/profile/applicant`.
- **Apply:** For each job, calls `applyToJobAsApplicant(job.id)` with loading state in `applyingJobId`; shows “Applying…” and handles `profile_incomplete` / `not_logged_in` etc. via `applyError`.
- **Render:** FilterBar (with initial query), then grid of JobCards with onApply, onToggleSave, isApplied, isSaved, matchScore from context.

#### 6.3 `pages/LoginApplicant.jsx`

- **Purpose:** Applicant sign-in form.
- **State:** `applicantId` (email/username), `applicantPassword`, `error`.
- **Submit:** `onApplicantSubmit` calls `loginApplicant(applicantId, applicantPassword)`. On success, reads `redirect` and `applyFor` from `location.search` and navigates to `/profile/applicant` with optional redirect/applyFor in query; otherwise to `/jobs`.
- **UI:** AuthPageLayout with title/subtitle; form with email and PasswordInput; error div; links to “Forgot password?” and “Create account”.

#### 6.4 Other pages (short)

- **Login / LoginAdmin:** Same pattern: form → loginHR or login flow → redirect.
- **SignupApplicant / SignupAdmin:** Collect signup data → call signup API → redirect to OTP verify or login.
- **ForgotPasswordRequest / ForgotPasswordVerify / ForgotPasswordReset:** Use `:variant` (e.g. `applicant`, `hr`) to call the correct context methods (e.g. requestApplicantPasswordReset, verifyApplicantPasswordOtp, resetApplicantPassword).
- **ApplicantProfile:** Form for profile + ResumeUploadWithParsing; on save calls `saveApplicantProfile`; may redirect after login via query params.
- **ApplicationStatus:** Lists applicant’s applications from context; shows status, match score, link to job.
- **Dashboard (HR):** Uses context jobs and addJob; job list and create form.
- **AppliedCandidates:** Fetches applications per job via `fetchApplicationsForJob`; shows CandidateCard list and resume download.
- **admin/BulkResumeParser:** Upload files, poll progress, download Excel via admin bulk-parse API.
- **admin/FeedbackAdmin:** Lists and manages feedback from GET/PATCH feedback API.
- **head-hr/*:** Head of HR dashboard, admins, candidates, jobs, applications (list/detail), settings; uses `/api/head-hr` and `HeadHrGuard`.

---

### 7. Components — Purpose and Code

#### 7.1 `components/Navbar.jsx`

- **Purpose:** Top bar with logo, Jobs link, role-based menu (Login / HR dropdown / Applicant dropdown / Super Admin button), and Support dropdown.
- **Derived state:** `isHrLoggedIn`, `isApplicantLoggedIn`, `isSuperAdminLoggedIn` from context auth. `applicantInitials` and `hrInitials` from profile/user names (first letters of first two words).
- **Logout:** `handleLogout` calls `logout()` then `navigate('/')`.
- **NavLink:** Uses a function for `className`: active route gets `text-slate-900 font-semibold`, else `text-slate-600 hover:text-slate-900`.
- **Conditional UI:** If no one logged in, show “Login”. If HR, show avatar dropdown with Dashboard, Candidates, Bulk Resume Parser, Feedback, Settings, Logout. If applicant, dropdown with Profile, Application Status, Settings, Logout. If super admin, link/button to “Super Admin”. Support dropdown: FAQ, Contact Us, HRMS Testing Feedback.

#### 7.2 `components/Hero.jsx`

- **Purpose:** Hero section on home page with headline, subtitle, feature pills, and search.
- **Code:** Gradient background and radial overlay; motion.div for headline “Find Your Dream Job Today”; motion.p for subtitle (mentions “AI-powered matching”); list of feature pills (AI Resume Parsing, Instant Apply, Smart Matching) with icons; at the bottom a `SearchBar` with `onSearch={onSearch}` and `large` so the search submits to the parent’s `handleSearch` (which in Home.jsx navigates to `/jobs?q=...&loc=...`).

#### 7.3 `components/SearchBar.jsx`

- **Purpose:** Keywords and location inputs with a Search button.
- **Props:** `onSearch`, `large`, `defaultQuery`, `className`.
- **State:** `keywords`, `location`, `isFocused` (for focus ring).
- **Submit:** `submit(e)` calls `e.preventDefault()` and `onSearch({ keywords: keywords.trim(), location: location.trim() })`.
- **Render:** Form with two inputs (keywords placeholder “Title, skills, or company”, location “Location”) and a submit button; optional `large` styling.

#### 7.4 `components/FilterBar.jsx`

- **Purpose:** Wrapper that shows SearchBar in a card-style container with initial values from URL.
- **Code:** Receives `onSearch` and `initial` (e.g. `{ keywords, location }`). Renders a motion.div with border/shadow and inside it `<SearchBar key={...} onSearch={onSearch} defaultQuery={initial} />`. The key forces SearchBar to reset when initial query changes.

#### 7.5 `components/JobCard.jsx`

- **Purpose:** One job card: title, company, location, salary, experience, skills, description preview; Apply / Save; optional match score and status badge; modal with full description.
- **Props:** `job`, `onApply`, `isApplied`, `applicationStatus`, `isSaved`, `onToggleSave`, `isAdmin`, `isApplying`, `matchScore`.
- **Skills:** Uses `extractRequiredSkillsFromDescription(job.description)`; fallback to `job.skills` or regex on description. Deduplicates by lowercased string.
- **Modal:** `showDescriptionModal` state. Click on card (but not on buttons) opens modal; Escape or overlay click closes. Modal shows full job details and `JobDescriptionView` for description.
- **Apply:** Apply button disabled when `isDisabled` (job.enabled === false) or `isApplied`. Action areas use `onClick={(e) => e.stopPropagation()` so they don’t trigger the card click. Save/bookmark button is not present on the current Jobs UI.
- **Status badge:** Uses `STATUS_BADGES[applicationStatus]` (applied, reviewed, shortlisted, rejected) for label and icon.

#### 7.6 `components/ResumeUploadWithParsing.jsx`

- **Purpose:** Resume upload with optional AI parsing; when parsed, can autofill profile form.
- **Props:** `onAutofill`, `onFileSelect`, `currentFileName`, `onRemove`, `onOpenResume`.
- **State:** `isUploading`, `parseError`, `parseSuccess`, `confidence`, `isDragging`.
- **Flow:** If user is not logged in (no token or !applicantAuth.isLoggedIn), only `onFileSelect(file)` is called (no parsing). If logged in, validates file with `validateFileForParsing(file)`; then calls `onFileSelect(file)` and starts upload. Shows `PremiumUploadOverlay` during upload. Calls `uploadAndParseResume(file)` from parsingApi; on success gets TOON and runs `mapResumeTOONToForm(toon)` then `onAutofill(mapped)`. Sets confidence and success/error message.
- **Drag and drop:** `handleDrop` / `handleDragOver` / `handleDragLeave` for drag state and passing file to `processFile`.
- **Remove:** `handleRemove` clears messages and ref value and calls `onRemove?.()`.

#### 7.7 `components/ErrorBoundary.jsx`

- **Purpose:** Catches JavaScript errors in the child tree and shows a fallback UI.
- **Code:** Class component with `state = { hasError: false }`. `getDerivedStateFromError()` sets `hasError: true`. `componentDidCatch` logs error and info. In render, if `hasError` shows “Something went wrong” and “Please refresh the page”; otherwise renders `this.props.children`.

#### 7.8 `components/Toast.jsx`

- **Purpose:** Global toast notifications.
- **ToastProvider:** Holds `toasts` array. `push(message, { type, duration })` adds a toast with a random id and removes it after `duration` (default 3000 ms). `remove(id)` filters out that id. `success` and `error` are wrappers around `push` with type. Renders a fixed div (bottom-right) that maps toasts to small cards (red for error, green for success, neutral for info).
- **useToast:** Returns the context value; must be used inside ToastProvider.

#### 7.9 `components/ConnectionStatus.jsx`

- **Purpose:** Shows a banner when the backend is unhealthy.
- **Code:** Reads `backendHealthy` from `useApp()`. If false, after 3 seconds sets `showWarning` true so a banner appears (“Connecting to server... backend is starting up”). When healthy again, hides immediately. Renders a fixed top bar with amber background and short message.

---

### 8. Utils — Purpose and Code

#### 8.1 `utils/api.js`

- **BASE_URL:** From `import.meta.env.VITE_API_URL` or `http://localhost:3000`, trimmed of trailing slash.
- **apiRequest(path, options):** Options: `method`, `body`, `token`, `headers`, `timeoutMs`, `skipRetry`. Builds full URL; for non-FormData body sets Content-Type and Accept. Adds `Authorization: Bearer` from token or tokenService. Uses AbortController for timeout. On 403 with token, calls `tryRefresh()` (POST /api/refresh with refresh_token); if refresh succeeds, retries the request once with new token. On 401/403 with token, calls `onUnauthorized`. Throws an error with `status` and `data`. Retry loop: up to 2 attempts (or 1 if skipRetry), exponential backoff; only retries on network/5xx/ECONNREFUSED/ETIMEDOUT/ENOTFOUND.
- **setUnauthorizedHandler(fn) / setOnTokensRefreshed(fn):** Store callbacks used by api.js for logout and token update.

#### 8.2 `utils/tokenService.js`

- In-memory variables plus localStorage keys `jwtToken` and `refreshToken`.
- **getToken / setToken:** Read/write access token in memory and localStorage.
- **getRefreshToken / setRefreshToken:** Same for refresh token.
- **clear():** Clears both in memory and localStorage.

#### 8.3 `utils/healthCheck.js`

- **checkBackendHealth(force):** GET `BASE_URL/health`. If not forced and last check was recent and healthy, returns cached true. Sets `backendHealthy` and `lastCheckTime`. Returns true if response ok, false on failure or timeout (3s).
- **waitForBackend(maxAttempts, delayMs):** Polls checkBackendHealth(true) until true or maxAttempts.
- **getBackendHealthStatus():** Returns cached `backendHealthy`.

#### 8.4 `utils/parsingApi.js`

- **ensureArray(value):** Returns [] for null/undefined, the array if array, else [value].
- **normalizeToYYYYMM(value):** Converts parser date (string, object with year/month) to "YYYY-MM" for MonthYearPicker.
- **ensureStringArray(value):** Converts value to array of non-empty strings (handles array, pipe/newline-separated string).
- **validateFileForParsing(file):** Checks extension (pdf, doc, docx) and size (e.g. 10MB); returns { valid, error }.
- **uploadAndParseResume(file):** FormData with file, POST to parse/resume (or VITE_PARSING_API_URL), returns parsed result.
- **mapResumeTOONToForm(toon):** Maps TOON fields (person, education, experience, certifications, skills) to the profile form shape (fullName, email, education[], experiences[], certifications[], etc.) using the above helpers.

#### 8.5 Other utils

- **passwordValidation.js:** Client-side password strength rules (length, upper, lower, digit, special).
- **reportUtils.js / pdfReportUtils.js:** Build data and generate PDF reports (e.g. for candidates).
- **avatarColor.js:** Derives a color from a string (e.g. name) for avatar background.

---

### 9. Services

#### 9.1 `services/adminService.js`

- **getJobApplications(jobId):** Calls `apiRequest(\`/api/jobs/${jobId}/applications\`)` and returns the response (list of applications with candidate and ATS data). Used by HR views to load candidates per job.

#### 9.2 `services/bulkParsingService.js`

- Wraps admin bulk-parse API: upload, progress, download. Used by the BulkResumeParser page.

---

### 10. Hooks

#### 10.1 `hooks/useAsyncAction.js`

- **Purpose:** Run an async function once at a time and expose loading state (e.g. for submit buttons).
- **Returns:** `{ run, loading }`.
- **run(asyncFn):** If already running (busyRef), returns. Sets busyRef and loading true, awaits asyncFn(), then sets busyRef and loading false in finally. Prevents double submission and shows loading state.

---

### 11. UI Primitives (`components/ui/`)

- **Button:** Variants (default, outline, ghost, etc.) and sizes via `buttonVariants` (cva) and `cn()`.
- **Card:** CardHeader, CardFooter, CardTitle, CardDescription, CardContent — layout and styling for cards.
- **Input, Textarea:** Styled inputs with optional props.
- **Badge:** Status/type badges with `badgeVariants`.
- **Avatar:** AvatarImage, AvatarFallback, AvatarWithInitials (from Radix Avatar).
- **Modal, Dialog:** Overlay and content; Dialog uses Radix.
- **Tabs:** TabPanel and tab list.
- **Table:** Header, Body, Footer, Head, Row, Cell, Caption for consistent tables.
- **DropdownMenu:** Trigger, Content, Item, Label, Separator (Radix Dropdown).
- **Skeleton, SkeletonLoader:** Loading placeholders (SkeletonCard, SkeletonList).
- **Progress:** Progress bar (Radix).
- **Separator:** Horizontal/vertical divider.
- **StatCard:** Small stat display (e.g. number + label).

All use Tailwind and, where applicable, Radix UI primitives and `class-variance-authority` + `tailwind-merge` for variant styling.

---

### 12. Data Flow Summary

1. **User opens app:** main.jsx mounts App → AppProvider hydrates state from localStorage and tokenService, fetches jobs, starts health check.
2. **Navigation:** React Router renders the matching route component; guards redirect if role is wrong.
3. **User action (e.g. Apply):** Page/component calls context action (e.g. applyToJobAsApplicant) → context updates state (optimistic) → apiRequest in api.js → backend; on success context may refetch (fetchApplicantData) or update state; on failure context reverts and may set error message.
4. **Auth:** Login pages call loginHR/loginApplicant; context sets token, user, auth state and persists to localStorage; api.js uses token from tokenService or passed option; on 403 api.js may refresh token and retry, or call logout.

This completes the frontend structure and code documentation.
