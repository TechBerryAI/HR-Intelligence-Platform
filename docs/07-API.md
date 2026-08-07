# API

## Contents

- [Authority](#authority)
- [Conventions](#conventions)
- [Authentication](#authentication)
- [Blueprint map](#blueprint-map)
- [Public API](#public-api)
- [Staff API — Identity](#staff-api--identity)
- [Staff API — Jobs & applications](#staff-api--jobs--applications)
- [Staff API — Parsing](#staff-api--parsing)
- [Staff API — Head HR](#staff-api--head-hr)
- [Staff API — Admin / bulk](#staff-api--admin--bulk)
- [Staff API — Candidate, support, feedback](#staff-api--candidate-support-feedback)
- [Error shape](#error-shape)
- [Versioning](#versioning)
- [Generated inventory (auto)](#generated-inventory-auto)

**Source of truth for registration:** `apps/backend/app/bootstrap/create_app.py`  
**Related:** [03-System-Architecture.md](03-System-Architecture.md) · [09-Security.md](09-Security.md) · [legacy/ENGINEERING.md](legacy/ENGINEERING.md) (archive)  
**Auto-sync:** `python scripts/sync_docs_from_code.py` refreshes the generated inventory below.

---

## Authority

| Layer | Role |
|-------|------|
| **`01`–`10` docs (this file)** | Canonical API map for HCIP |
| **`create_app.py` + route modules** | Runtime truth — if docs disagree, fix the docs |
| **legacy/ENGINEERING.md** | Historical narrative; defer to this file + code for endpoints |

---

## Conventions

- Base path: `/api`
- JSON for most staff calls
- `multipart/form-data` for file uploads and public apply
- Staff auth: `Authorization: Bearer <access_jwt>`
- IDs: job `jdid` strings; application integer ids; candidate ids as used in `candidate_signup`

---

## Authentication

| Audience | Mechanism |
|----------|-----------|
| Staff (Recruiter, Head HR, CEO) | JWT access + refresh (`/api/login`, `/api/refresh`) |
| Public candidate apply / public resume parse | No JWT — validated payloads; public parse rate-limited |

There is **no** candidate login required for the core apply path (passwordless apply).

---

## Blueprint map

| Prefix | Blueprint | Domain package |
|--------|-----------|----------------|
| `/api` | `auth_bp` | `identity` |
| `/api/jobs` | `jobs_bp` | `recruitment` |
| `/api/candidate` | `candidate_bp` | `candidate` |
| `/api/applications` | `applications_bp` | `recruitment` |
| `/api/sessions` | `sessions_bp` | `identity` (`/my-sessions`, `/my-history`, logout helpers) |
| `/api` | `parsing_bp` | `recruitment` (`/parse/*`, `/parsed/*`) |
| `/api/support` | `support_bp` | `support` |
| `/api/feedback` | `feedback_bp` | `employee` |
| `/api/admin` | `admin_bp` | `administration` |
| `/api/head-hr` | `head_hr_bp` | `administration` |
| `/api/integrations` | `integrations_bp` | `integrations` (job-board framework) |

**Not registered:** interview scheduling / AI interview session blueprints (tables may exist as scaffolds).

---

## Public API

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/api/jobs/` | List jobs (public board as exposed) | None / as implemented |
| GET | `/api/jobs/<job_id>` | Job detail | None / as implemented |
| POST | `/api/parse/resume/public` | Resume parse for apply autofill | None (rate-limited) |
| POST | `/api/jobs/<job_id>/apply` | Submit application (multipart) | None |
| POST | `/api/support/submit` | Support request | None / as implemented |

### Public apply contract (critical)

**Preconditions**

1. Job exists and is enabled  
2. Client completed `POST /api/parse/resume/public` and sends `parsedId`  
3. Payload passes `validate_public_apply_payload`  
4. Resume file present  

**Effects**

1. Upsert passwordless candidate  
2. Save profile + education / experience / certifications  
3. Link parsed resume  
4. Run in-process ATS match  
5. Persist `applications` + `matches`  

**Rejects**

- Validation errors → `400`  
- Job missing / disabled → `404`  
- Duplicate candidate+job → `400`  
- Missing / unlinkable parse → `400`  

**UI note (current):** Job cards expose **Apply** only. Bookmark / “save job” control was removed from the public jobs UI. The `saved_jobs` table may still exist in schema as a scaffold/legacy structure — it is **not** a current product surface.

See [04-Workflow.md](04-Workflow.md) (Candidate + Matching).

---

## Staff API — Identity

Prefix: `/api` (`auth_bp`)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/signup` | Start staff signup (OTP pending) |
| POST | `/api/verify-otp` | Complete signup |
| POST | `/api/resend-otp` | Resend OTP |
| POST | `/api/login` | Issue access + refresh JWT |
| POST | `/api/refresh` | Refresh access token |
| POST | `/api/logout` | End session |
| POST | `/api/forgot-password` | Start reset |
| POST | `/api/forgot-password/verify-otp` | Verify reset OTP |
| POST | `/api/reset-password` | Set new password |
| POST | `/api/change-password` | Authenticated password change |

---

## Staff API — Jobs & applications

Prefix: `/api/jobs` (`jobs_bp`) — JWT + RBAC

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/jobs/` | Public board: all **enabled** jobs (auth ignored for listing) |
| GET | `/api/jobs/all` | Staff list: CEO/Head HR all jobs; recruiters **company** postings |
| GET | `/api/jobs/<job_id>` | Detail |
| POST | `/api/jobs/` | Create job |
| PUT | `/api/jobs/<job_id>` | Update job |
| PATCH | `/api/jobs/<job_id>/enabled` | Enable / disable (disabled jobs leave public `GET /api/jobs`) |
| DELETE | `/api/jobs/<job_id>` | Delete job and cascade applications/matches for that job |
| GET | `/api/jobs/<job_id>/applications` | Applicants for job |
| GET | `/api/jobs/<job_id>/applications/<candidate_id>/resume` | Resume download/view |
| POST | `/api/jobs/<job_id>/applications/<candidate_id>/viewed` | Mark viewed |
| PATCH | `/api/jobs/<job_id>/applications/<candidate_id>/status` | Update status |

Prefix: `/api/applications`

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/applications/ats/result` | Optional external ATS / n8n callback |

---

## Staff API — Integrations

Prefix: `/api/integrations` (`integrations_bp`) — company-scoped via `company_key`

**Current:** Built-ins `linkedin` / `naukri` (staging IDs until partner APIs). Builtin brand icons are frontend inline SVG / react-icons (not stored as repo images or DB blobs). Custom platforms: any slug `[a-z0-9_]+` except reserved builtins; `settings_json.adapter = "http"` with `baseUrl` + `endpoints` + optional HTTPS `logoUrl`. Secrets encrypted and masked in responses. HTTP adapters publish/sync via `GenericHttpProvider`; synced candidates stored in `external_applications`.

**Custom platform `POST /provider` body (required):** `name` or `provider` slug; `baseUrl` (or `settings.baseUrl`); credentials (`accessToken` and/or `clientId`+`clientSecret`). Optional: `logoUrl` / `settings.logoUrl` (HTTPS only), `settings.endpoints` (`test`, `publish`, `update`, `close`, `applications`, `status` as `"METHOD /path"` with `{externalJobId}`), `custom: true`, toggles.

**`settings_json` contract (custom HTTP):**

```json
{
  "adapter": "http",
  "displayName": "Glassdoor",
  "baseUrl": "https://api.example.com",
  "logoUrl": "https://cdn.example.com/glassdoor.png",
  "authHeader": "Bearer",
  "endpoints": {
    "test": "GET /health",
    "publish": "POST /jobs",
    "update": "PUT /jobs/{externalJobId}",
    "close": "POST /jobs/{externalJobId}/close",
    "applications": "GET /jobs/{externalJobId}/applications",
    "status": "GET /jobs/{externalJobId}"
  }
}
```

`logoUrl` must be `https://…` (reject `http://`, `data:`, relative paths). Empty string clears it.
| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/api/integrations/` | Summary + provider catalog | Staff JWT |
| GET | `/api/integrations/providers` | Built-ins + company custom platforms | Staff JWT |
| GET | `/api/integrations/provider/<provider>` | One provider config (masked) | Staff JWT |
| POST | `/api/integrations/provider` | Create/upsert (builtins or custom HTTP) | Head HR |
| PUT | `/api/integrations/provider/<provider>` | Update config / toggles / HTTP settings | Head HR |
| DELETE | `/api/integrations/provider/<provider_or_id>` | Delete config | Head HR |
| POST | `/api/integrations/provider/<provider>/connect` | Mark connected | Head HR |
| POST | `/api/integrations/provider/<provider>/disconnect` | Clear tokens / disconnect | Head HR |
| POST | `/api/integrations/provider/<provider>/test` | Test connection (HTTP or builtin staging) | Staff write roles |
| POST | `/api/integrations/provider/<provider>/sync` | Sync applications → `external_applications` | Head HR / write roles |
| POST | `/api/integrations/publish/<jobId>` | Manual publish (`providers` optional) | Recruiter / Head HR |
| POST | `/api/integrations/republish/<jobId>` | Republish | Recruiter / Head HR |
| POST | `/api/integrations/retry/<externalJobId>` | Retry failed/dead mapping | Recruiter / Head HR |
| GET | `/api/integrations/jobs` | External job mappings | Staff JWT |
| GET | `/api/integrations/applications` | Synced external applications | Staff JWT |
| GET | `/api/integrations/logs` | Sync logs | Staff JWT |
| GET | `/api/integrations/status` | Published / pending / failed counts | Staff JWT |
| GET | `/api/integrations/dashboard` | Dashboard aggregate | Staff JWT |

**Future:** OAuth connect flows and official LinkedIn/Naukri APIs — same paths.

---

## Public media

Prefix: `/api/media` (`media_bp`)

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/api/media/public/hero-video` | Stream landing hero MP4 from Postgres `site_assets.landing.hero_video` (BYTEA); disk under `MEDIA_ROOT` is seed/fallback only | None |
| GET | `/api/media/health` | Media root + hero present (DB and/or disk) | None |

Override landing URL with frontend `VITE_HERO_VIDEO_URL` (HTTPS CDN) without code changes. Frontend default is `/api/media/public/hero-video` — not a file under `apps/frontend/public/`.

---

## Staff API — Parsing

Prefix: `/api` (`parsing_bp`) — JWT unless noted

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| POST | `/api/parse/resume/public` | Public apply parse | None |
| POST | `/api/parse/resume` | Staff resume parse | JWT |
| POST | `/api/parse/jd` | JD parse | JWT + recruiter scope |
| GET | `/api/parsed/resume/<parsed_id>` | Fetch parsed resume | JWT / as implemented |
| GET | `/api/parsed/jd/<parsed_id>` | Fetch parsed JD | JWT / as implemented |

---

## Staff API — Head HR

Prefix: `/api/head-hr` — JWT `HEAD_HR` (CEO read where allowed)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/head-hr/stats` | Org dashboard stats (`totalAdmins` = all `hr_signup`; `totalCandidates` = distinct applicants on `applications`) |
| GET | `/api/head-hr/admins` | List admins |
| POST | `/api/head-hr/admins` | Create admin |
| DELETE | `/api/head-hr/admins/<hrid>` | Remove admin |
| GET | `/api/head-hr/candidates` | Applicants who applied (with application counts / jobs) |
| GET | `/api/head-hr/candidates/<cid>` | Candidate detail |
| GET | `/api/head-hr/candidates/<cid>/resume` | Resume |
| DELETE | `/api/head-hr/candidates/<cid>` | Delete candidate |
| GET | `/api/head-hr/jobs` | Org jobs |
| GET/DELETE | `/api/head-hr/jobs/<jdid>` | Job detail / delete |
| GET | `/api/head-hr/applications` | Org applications |
| GET | `/api/head-hr/applications/<app_id>` | Application detail |

---

## Staff API — Admin / bulk

Prefix: `/api/admin`

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/admin/bulk-parse/jobs` | Create bulk parse job/session |
| POST | `/api/admin/bulk-parse/upload` | Upload files |
| POST | `/api/admin/bulk-parse/start/<job_id>` | Start processing |
| GET | `/api/admin/bulk-parse/progress/<job_id>` | Progress |
| GET | `/api/admin/bulk-parse/download/<job_id>` | Download results |
| GET | `/api/admin/job-matches` | Job matches listing (as implemented) |

---

## Staff API — Candidate, support, feedback

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/candidate/profile/<candidate_id>` | Candidate profile |
| GET | `/api/support/my-requests` | Own support requests |
| GET | `/api/support/all` | All requests (staff) |
| GET | `/api/support/<id>` | Request detail |
| PATCH | `/api/support/<id>/status` | Update status |
| POST | `/api/feedback/submit` | Submit feedback |
| GET | `/api/feedback/list` | List feedback |
| POST | `/api/feedback/<id>/status` | Update feedback status |

### Sessions

Prefix: `/api/sessions`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/sessions/my-sessions` | Active sessions |
| GET | `/api/sessions/my-history` | Login/session history |
| POST | `/api/sessions/logout-session` | End one session |
| POST | `/api/sessions/logout-all` | End all sessions |

---

## Error shape

Typical JSON:

```json
{ "error": "Human-readable message" }
```

HTTP status reflects class of failure (`400`, `401`, `403`, `404`, `500`).

---

## Versioning

Prefer additive routes. Breaking changes require migration notes and a compatibility window per [01-Product-Constitution.md](01-Product-Constitution.md).

When this document and `legacy/ENGINEERING.md` disagree on an endpoint, **trust `create_app.py` + the domain route module**, then update this file.

---

## Generated inventory (auto)

Refresh with:

```bash
python scripts/sync_docs_from_code.py
```

<!-- BEGIN:GENERATED-API-ROUTES -->
_Auto-generated on 2026-08-06 by `scripts/sync_docs_from_code.py`. Do not hand-edit this block._

### Registered blueprints

| Blueprint | URL prefix |
|-----------|------------|
| `auth_bp` | `/api` |
| `parsing_bp` | `/api` |
| `admin_bp` | `/api/admin` |
| `developer_bp` | `/api/admin/developer` |
| `applications_bp` | `/api/applications` |
| `candidate_bp` | `/api/candidate` |
| `feedback_bp` | `/api/feedback` |
| `head_hr_bp` | `/api/head-hr` |
| `integrations_bp` | `/api/integrations` |
| `jobs_bp` | `/api/jobs` |
| `media_bp` | `/api/media` |
| `sessions_bp` | `/api/sessions` |
| `support_bp` | `/api/support` |

### Discovered routes

| Method | Path | Blueprint | Source |
|--------|------|-----------|--------|
| `GET` | `/api/admin/bulk-parse/download/<job_id>` | `admin_bp` | `app/domains/administration/api/admin.py` |
| `POST` | `/api/admin/bulk-parse/jobs` | `admin_bp` | `app/domains/administration/api/admin.py` |
| `GET` | `/api/admin/bulk-parse/progress/<job_id>` | `admin_bp` | `app/domains/administration/api/admin.py` |
| `POST` | `/api/admin/bulk-parse/start/<job_id>` | `admin_bp` | `app/domains/administration/api/admin.py` |
| `POST` | `/api/admin/bulk-parse/upload` | `admin_bp` | `app/domains/administration/api/admin.py` |
| `DELETE` | `/api/admin/developer/performance/clear` | `developer_bp` | `app/domains/administration/api/developer.py` |
| `POST` | `/api/admin/developer/performance/clear` | `developer_bp` | `app/domains/administration/api/developer.py` |
| `GET` | `/api/admin/developer/performance/export` | `developer_bp` | `app/domains/administration/api/developer.py` |
| `GET` | `/api/admin/developer/performance/recent` | `developer_bp` | `app/domains/administration/api/developer.py` |
| `GET` | `/api/admin/developer/performance/request/<path:request_id>` | `developer_bp` | `app/domains/administration/api/developer.py` |
| `GET` | `/api/admin/developer/performance/stats` | `developer_bp` | `app/domains/administration/api/developer.py` |
| `GET` | `/api/admin/developer/status` | `developer_bp` | `app/domains/administration/api/developer.py` |
| `GET` | `/api/admin/job-matches` | `admin_bp` | `app/domains/administration/api/admin.py` |
| `POST` | `/api/applications/ats/result` | `applications_bp` | `app/domains/recruitment/api/applications.py` |
| `GET` | `/api/candidate/profile/<string:candidate_id>` | `candidate_bp` | `app/domains/candidate/api/routes.py` |
| `POST` | `/api/change-password` | `auth_bp` | `app/domains/identity/api/hr_auth.py` |
| `PATCH` | `/api/feedback/<int:feedback_id>/status` | `feedback_bp` | `app/domains/employee/api/feedback.py` |
| `GET` | `/api/feedback/list` | `feedback_bp` | `app/domains/employee/api/feedback.py` |
| `POST` | `/api/feedback/submit` | `feedback_bp` | `app/domains/employee/api/feedback.py` |
| `POST` | `/api/forgot-password` | `auth_bp` | `app/domains/identity/api/hr_auth.py` |
| `POST` | `/api/forgot-password/verify-otp` | `auth_bp` | `app/domains/identity/api/hr_auth.py` |
| `GET` | `/api/head-hr/admins` | `head_hr_bp` | `app/domains/administration/api/head_hr.py` |
| `POST` | `/api/head-hr/admins` | `head_hr_bp` | `app/domains/administration/api/head_hr.py` |
| `DELETE` | `/api/head-hr/admins/<hrid>` | `head_hr_bp` | `app/domains/administration/api/head_hr.py` |
| `GET` | `/api/head-hr/applications` | `head_hr_bp` | `app/domains/administration/api/head_hr.py` |
| `GET` | `/api/head-hr/applications/<int:app_id>` | `head_hr_bp` | `app/domains/administration/api/head_hr.py` |
| `OPTIONS` | `/api/head-hr/applications/<int:app_id>` | `head_hr_bp` | `app/domains/administration/api/head_hr.py` |
| `GET` | `/api/head-hr/candidates` | `head_hr_bp` | `app/domains/administration/api/head_hr.py` |
| `DELETE` | `/api/head-hr/candidates/<cid>` | `head_hr_bp` | `app/domains/administration/api/head_hr.py` |
| `GET` | `/api/head-hr/candidates/<cid>` | `head_hr_bp` | `app/domains/administration/api/head_hr.py` |
| `OPTIONS` | `/api/head-hr/candidates/<cid>` | `head_hr_bp` | `app/domains/administration/api/head_hr.py` |
| `GET` | `/api/head-hr/candidates/<cid>/resume` | `head_hr_bp` | `app/domains/administration/api/head_hr.py` |
| `OPTIONS` | `/api/head-hr/candidates/<cid>/resume` | `head_hr_bp` | `app/domains/administration/api/head_hr.py` |
| `GET` | `/api/head-hr/jobs` | `head_hr_bp` | `app/domains/administration/api/head_hr.py` |
| `DELETE` | `/api/head-hr/jobs/<jdid>` | `head_hr_bp` | `app/domains/administration/api/head_hr.py` |
| `GET` | `/api/head-hr/jobs/<jdid>` | `head_hr_bp` | `app/domains/administration/api/head_hr.py` |
| `OPTIONS` | `/api/head-hr/jobs/<jdid>` | `head_hr_bp` | `app/domains/administration/api/head_hr.py` |
| `GET` | `/api/head-hr/stats` | `head_hr_bp` | `app/domains/administration/api/head_hr.py` |
| `GET` | `/api/integrations/` | `integrations_bp` | `app/domains/integrations/api/routes.py` |
| `GET` | `/api/integrations/applications` | `integrations_bp` | `app/domains/integrations/api/routes.py` |
| `GET` | `/api/integrations/dashboard` | `integrations_bp` | `app/domains/integrations/api/routes.py` |
| `GET` | `/api/integrations/jobs` | `integrations_bp` | `app/domains/integrations/api/routes.py` |
| `GET` | `/api/integrations/logs` | `integrations_bp` | `app/domains/integrations/api/routes.py` |
| `POST` | `/api/integrations/provider` | `integrations_bp` | `app/domains/integrations/api/routes.py` |
| `GET` | `/api/integrations/provider/<string:provider>` | `integrations_bp` | `app/domains/integrations/api/routes.py` |
| `PUT` | `/api/integrations/provider/<string:provider>` | `integrations_bp` | `app/domains/integrations/api/routes.py` |
| `POST` | `/api/integrations/provider/<string:provider>/connect` | `integrations_bp` | `app/domains/integrations/api/routes.py` |
| `POST` | `/api/integrations/provider/<string:provider>/disconnect` | `integrations_bp` | `app/domains/integrations/api/routes.py` |
| `POST` | `/api/integrations/provider/<string:provider>/sync` | `integrations_bp` | `app/domains/integrations/api/routes.py` |
| `POST` | `/api/integrations/provider/<string:provider>/test` | `integrations_bp` | `app/domains/integrations/api/routes.py` |
| `DELETE` | `/api/integrations/provider/<string:provider_or_id>` | `integrations_bp` | `app/domains/integrations/api/routes.py` |
| `GET` | `/api/integrations/providers` | `integrations_bp` | `app/domains/integrations/api/routes.py` |
| `POST` | `/api/integrations/publish/<string:job_id>` | `integrations_bp` | `app/domains/integrations/api/routes.py` |
| `POST` | `/api/integrations/republish/<string:job_id>` | `integrations_bp` | `app/domains/integrations/api/routes.py` |
| `POST` | `/api/integrations/retry/<int:external_job_id>` | `integrations_bp` | `app/domains/integrations/api/routes.py` |
| `GET` | `/api/integrations/status` | `integrations_bp` | `app/domains/integrations/api/routes.py` |
| `GET` | `/api/jobs/` | `jobs_bp` | `app/domains/recruitment/api/jobs.py` |
| `POST` | `/api/jobs/` | `jobs_bp` | `app/domains/recruitment/api/jobs.py` |
| `DELETE` | `/api/jobs/<string:job_id>` | `jobs_bp` | `app/domains/recruitment/api/jobs.py` |
| `GET` | `/api/jobs/<string:job_id>` | `jobs_bp` | `app/domains/recruitment/api/jobs.py` |
| `PUT` | `/api/jobs/<string:job_id>` | `jobs_bp` | `app/domains/recruitment/api/jobs.py` |
| `GET` | `/api/jobs/<string:job_id>/applications` | `jobs_bp` | `app/domains/recruitment/api/jobs.py` |
| `GET` | `/api/jobs/<string:job_id>/applications/<string:candidate_id>/resume` | `jobs_bp` | `app/domains/recruitment/api/jobs.py` |
| `PATCH` | `/api/jobs/<string:job_id>/applications/<string:candidate_id>/status` | `jobs_bp` | `app/domains/recruitment/api/jobs.py` |
| `POST` | `/api/jobs/<string:job_id>/applications/<string:candidate_id>/viewed` | `jobs_bp` | `app/domains/recruitment/api/jobs.py` |
| `POST` | `/api/jobs/<string:job_id>/apply` | `jobs_bp` | `app/domains/recruitment/api/jobs.py` |
| `PATCH` | `/api/jobs/<string:job_id>/enabled` | `jobs_bp` | `app/domains/recruitment/api/jobs.py` |
| `GET` | `/api/jobs/all` | `jobs_bp` | `app/domains/recruitment/api/jobs.py` |
| `POST` | `/api/login` | `auth_bp` | `app/domains/identity/api/hr_auth.py` |
| `POST` | `/api/logout` | `auth_bp` | `app/domains/identity/api/hr_auth.py` |
| `GET` | `/api/media/health` | `media_bp` | `app/domains/support/api/media.py` |
| `GET` | `/api/media/public/hero-video` | `media_bp` | `app/domains/support/api/media.py` |
| `POST` | `/api/parse/jd` | `parsing_bp` | `app/domains/recruitment/api/parsing.py` |
| `POST` | `/api/parse/jd/stream` | `parsing_bp` | `app/domains/recruitment/api/parsing.py` |
| `GET` | `/api/parse/jobs/<job_id>/progress` | `parsing_bp` | `app/domains/recruitment/api/parsing.py` |
| `POST` | `/api/parse/resume` | `parsing_bp` | `app/domains/recruitment/api/parsing.py` |
| `POST` | `/api/parse/resume/public` | `parsing_bp` | `app/domains/recruitment/api/parsing.py` |
| `POST` | `/api/parse/resume/public/stream` | `parsing_bp` | `app/domains/recruitment/api/parsing.py` |
| `GET` | `/api/parsed/jd/<parsed_id>` | `parsing_bp` | `app/domains/recruitment/api/parsing.py` |
| `GET` | `/api/parsed/resume/<parsed_id>` | `parsing_bp` | `app/domains/recruitment/api/parsing.py` |
| `POST` | `/api/refresh` | `auth_bp` | `app/domains/identity/api/hr_auth.py` |
| `POST` | `/api/resend-otp` | `auth_bp` | `app/domains/identity/api/hr_auth.py` |
| `POST` | `/api/reset-password` | `auth_bp` | `app/domains/identity/api/hr_auth.py` |
| `POST` | `/api/sessions/logout-all` | `sessions_bp` | `app/domains/identity/sessions/routes.py` |
| `POST` | `/api/sessions/logout-session` | `sessions_bp` | `app/domains/identity/sessions/routes.py` |
| `GET` | `/api/sessions/my-history` | `sessions_bp` | `app/domains/identity/sessions/routes.py` |
| `GET` | `/api/sessions/my-sessions` | `sessions_bp` | `app/domains/identity/sessions/routes.py` |
| `POST` | `/api/signup` | `auth_bp` | `app/domains/identity/api/hr_auth.py` |
| `GET` | `/api/support/<int:request_id>` | `support_bp` | `app/domains/support/api/routes.py` |
| `PATCH` | `/api/support/<int:request_id>/status` | `support_bp` | `app/domains/support/api/routes.py` |
| `GET` | `/api/support/all` | `support_bp` | `app/domains/support/api/routes.py` |
| `GET` | `/api/support/my-requests` | `support_bp` | `app/domains/support/api/routes.py` |
| `POST` | `/api/support/submit` | `support_bp` | `app/domains/support/api/routes.py` |
| `POST` | `/api/verify-otp` | `auth_bp` | `app/domains/identity/api/hr_auth.py` |

_Route count: 94. If a route is missing, ensure it uses `@blueprint.route` / `.get` / `.post` and the blueprint is registered in `create_app.py`._
<!-- END:GENERATED-API-ROUTES -->
Prefix: `/api/admin/developer` — **requires `DEVELOPER_MODE=true`** and `HEAD_HR` (`developer:performance`). Otherwise 404 / 403.
| GET | `/api/admin/developer/status` | SPA flag (`enabled` only for Head HR when mode on) |
| GET | `/api/admin/developer/performance/recent` | Latest timing sessions (filterable; Resume vs Bulk separated) |
| POST / DELETE | `/api/admin/developer/performance/clear` | Wipe in-memory recent timing sessions |
| GET | `/api/admin/developer/performance/request/<id>` | Full breakdown for one request |
| GET | `/api/admin/developer/performance/stats` | Averages, p95, slowest/fastest, chart series |
| GET | `/api/admin/developer/performance/export` | CSV export of timing events |
| `developer_bp` | `/api/admin/developer` |
| `GET` | `/api/admin/developer/performance/export` | `developer_bp` | `app/domains/administration/api/developer.py` |
| `GET` | `/api/admin/developer/performance/recent` | `developer_bp` | `app/domains/administration/api/developer.py` |
| `GET` | `/api/admin/developer/performance/request/<request_id>` | `developer_bp` | `app/domains/administration/api/developer.py` |
| `GET` | `/api/admin/developer/performance/stats` | `developer_bp` | `app/domains/administration/api/developer.py` |
| `GET` | `/api/admin/developer/status` | `developer_bp` | `app/domains/administration/api/developer.py` |
