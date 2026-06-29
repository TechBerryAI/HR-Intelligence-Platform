# Sprint 1.3 — Legacy Architecture Cleanup Report

**Document ID:** ARCH-13  
**Status:** Complete — single source of truth for RBAC  
**Date:** 2026-06-29  
**Related:** [12_DATABASE_FREEZE_REPORT.md](12_DATABASE_FREEZE_REPORT.md)

---

## Summary

Sprint 1.3 permanently removed legacy RBAC boolean columns, JWT/API role aliases, and compatibility layers introduced during Sprint 1.1–1.2 migration. The platform now uses **one role model** everywhere:

| Role | Scope |
|------|-------|
| `CEO` | Read-only executive analytics |
| `HEAD_HR` | Full org administration |
| `RECRUITER` | Own jobs, candidates, bulk parse |
| `CANDIDATE` | Own profile and applications |

---

## 1. Legacy code removed

| Area | Removed |
|------|---------|
| `rbac.py` | `ROLE_HR`, `ROLE_SUPER_ADMIN_LEGACY`, `normalize_role()`, `resolve_hr_role_from_flags()`, flag-based `resolve_hr_role()` |
| `utils.py` | `require_super_admin`, legacy JWT fields (`hrId`, `id`, `readOnly` in token payload) |
| `auth.py` | Login response `isCeo`, `isHeadHr`, `isSuperAdmin`; refresh token `super_admin` → `head_hr` migration |
| `super_admin.py` | Legacy flag SELECT columns; login response boolean flags |
| `db.py` | Idempotent ensures for `is_super_admin`, `is_head_hr`, `is_ceo` |
| `04_domain_freeze.sql` | `hr_signup_role_sync` trigger and flag backfill |
| Frontend `rbac.js` | `super_admin` normalization, `HR` role constant |
| Frontend | `AdminGuard.jsx` (replaced by `RecruiterGuard.jsx`) |

---

## 2. Database columns removed

From `hr_signup`:

- `is_super_admin` — dropped
- `is_head_hr` — dropped
- `is_ceo` — dropped

Migration: [`backend/schema_pg/05_remove_legacy_rbac.sql`](backend/schema_pg/05_remove_legacy_rbac.sql)

Trigger removed: `trg_hr_signup_role_sync` / `hr_signup_role_sync()`

**Verified on dev DB:** all three columns report `REMOVED`.

---

## 3. Files deleted

| File | Reason |
|------|--------|
| `frontend/src/guards/AdminGuard.jsx` | Replaced by `RecruiterGuard.jsx` |

---

## 4. Files modified

### Backend
- `rbac.py` — canonical roles `CEO`, `HEAD_HR`, `RECRUITER`, `CANDIDATE`
- `utils.py` — `build_jwt_payload()` emits `user_id`, `role`, `email`, `iat`, `exp`, `type`
- `auth.py`, `head_hr.py`, `jobs.py`, `candidate.py`, `parsing_routes.py`
- `modules/admin/routes.py`, `sessions_routes.py`, `sessions_service.py`
- `routes/simple_candidate_auth.py`
- `db.py`
- `schema_pg/01_schema.sql`, `04_domain_freeze.sql`, `06_seed_admin_accounts.sql`, `07_seed_ceo_account.sql`

### Frontend
- `utils/rbac.js`, `App.jsx`, `AppContext.jsx`, `LoginAdmin.jsx`
- `Navbar.jsx`, `ContactUs.jsx`, `AppliedCandidates.jsx`, `HRMSTestingFeedback.jsx`
- New: `guards/RecruiterGuard.jsx`

---

## 5. Guards renamed

| Before | After |
|--------|-------|
| `AdminGuard` | `RecruiterGuard` |
| `SuperAdminGuard` | `HeadHrGuard` |
| `CeoGuard` | unchanged |
| `CandidateGuard` | unchanged |

Backend: `require_recruiter` decorator (RECRUITER + HEAD_HR; removed `require_hr` alias in Sprint 1.4).

---

## 6. JWT changes

**Before:** `{ hrId, role: 'HR' \| 'head_hr' \| 'ceo', email, readOnly?, type, iat, exp }`

**After:** `{ user_id, role: 'CEO' \| 'HEAD_HR' \| 'RECRUITER' \| 'CANDIDATE', email, type, iat, exp }`

- Staff login identity built via `build_hr_identity()` → `user_id = hrid`
- Candidate login identity → `user_id = cid`, `role = CANDIDATE`
- Refresh tokens carry same canonical fields only
- **Breaking change:** existing sessions with old JWT roles (`HR`, `head_hr`, `ceo`) must re-login

Login API `user` object still includes `hrId` for UI convenience (not in JWT).

---

## 7. RBAC verification

| Check | Result |
|-------|--------|
| `resolve_hr_role({'role': 'RECRUITER'})` → `RECRUITER` | Pass |
| `build_hr_identity()` sets `user_id` + canonical role | Pass |
| `PERMISSIONS` use `RECRUITER` not `HR` | Pass |
| Legacy DB columns absent | Pass |
| DB roles: CEO, HEAD_HR only in seed data | Pass |

---

## 8. Authentication verification

| Flow | Status |
|------|--------|
| Recruiter signup OTP → JWT `RECRUITER` | Updated |
| Staff login → role from `hr_signup.role` | Updated |
| Candidate login → JWT `CANDIDATE` | Updated |
| Token refresh → `user_id`, `role`, `email` only | Updated |

---

## 9. Authorization verification

| Decorator / guard | Roles allowed |
|-------------------|---------------|
| `require_recruiter` | `RECRUITER`, `HEAD_HR` |
| `require_head_hr` | `HEAD_HR` |
| `require_candidate` | `CANDIDATE` |
| `RecruiterGuard` | `RECRUITER` only |
| `HeadHrGuard` | `HEAD_HR` |
| `CeoGuard` | `CEO` |

---

## 10. Dead code removed

- `resolve_hr_role_from_flags()` alias
- `require_super_admin()` decorator
- JWT `super_admin` refresh migration block
- Login response boolean role flags
- DB role↔flag sync trigger
- Frontend `superAdminAuth` session state in `AppContext` (removed in HEAD_HR unification)

---

## 11. Duplicate code consolidated

- Single `resolve_hr_role()` reading `hr_signup.role` only
- Single `get_user_id()` for JWT user identification (replaces `hrId` / `id` in middleware)
- Frontend `getRole()` validates against `ROLES` enum only (no normalization layer)

---

## 12. Final repository health assessment

| Check | Result |
|-------|--------|
| PostgreSQL migrations | Pass — legacy columns dropped |
| Frontend `npm run build` | Pass |
| Backend `rbac` module | Pass |
| Backend full `app` import | Requires `flask_mail` in env (pre-existing dependency) |

### Post-deploy action required

**All users must log in again** after deploy — old JWTs with `HR`/`head_hr`/`ceo` roles are invalid.

### Intentionally unchanged (temporary)

- `login_history.user_type` still uses `'HR'` / `'candidate'` (audit category, not JWT role)
- `hrId` in login API response body for frontend display

---

## 13. HEAD_HR / Super Admin unification (post–Sprint 1.3)

| Layer | Before | After |
|-------|--------|-------|
| API prefix | `/api/super-admin` | `/api/head-hr` only (legacy removed Sprint 1.4) |
| UI routes | `/super-admin/*` | `/head-hr/*` only (redirects removed Sprint 1.4) |
| Guard | `SuperAdminGuard` | `HeadHrGuard` |
| Login | `/api/login` + `/api/super-admin/login` | `/api/login` only |
| Auth state | `auth` + `superAdminAuth` | `auth` only |
| Seed accounts | 2 HEAD_HR blocks | 1 HEAD_HR (`chetan.gore`) |

**Files renamed:** `super_admin.py` → `head_hr.py`; `pages/super-admin/*` → `pages/head-hr/HeadHr*`

---

## Migration file order (final)

1. `01_schema.sql`
2. `03_employee_feedback.sql`
3. `04_domain_freeze.sql`
4. `05_remove_legacy_rbac.sql`
5. `06_seed_admin_accounts.sql`
6. `07_seed_ceo_account.sql`

---

**Platform foundation is now frozen with a single RBAC model. Ready for Sprint 2 — Resume Intelligence.**
