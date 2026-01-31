# Bulk Resume Parsing Incident — Root Cause Analysis & Fix Plan

## 1. Root Cause Analysis (ordered by likelihood)

1. **Bulk-Resume-Parser service not running on port 8001**
   - Backend proxies bulk upload/progress/download to `BULK_PARSER_URL` (default `http://localhost:8001`). If nothing is listening, `requests` raises `ConnectionError` → admin route returns **502** and error body includes "Connection refused".
   - **Evidence**: `HTTPConnectionPool(host='localhost', port=8001): Max retries exceeded - Connection refused`.

2. **GET /api/jobs/all → 401: token not sent on initial load**
   - `/api/jobs/all` requires `@authenticate_token` and `@require_hr`. 401 is returned when `Authorization: Bearer <token>` is missing.
   - **Evidence**: `AppContext` restores `auth` from localStorage (e.g. `isLoggedIn: true`, `role: 'HR'`) but `token` is restored asynchronously from `tokenService` in a `useEffect`. `fetchJobs()` runs on mount (another effect with `[]`) and when auth changes; on first paint it can run with `token` state still empty, so the request is sent with `token: undefined` → no header → **401**.
   - Independent of 502: same session can see 401 on jobs list and 502 on bulk upload.

3. **Frontend treats 502 as “processing” and retries**
   - If upload returns 502, the UI should show “Bulk parsing service unavailable”, not a fake “Processing (102)”. Polling progress after a failed upload can cause retry storms (repeated 502s).

---

## 2. Evidence Mapping

| Symptom | Cause |
|--------|--------|
| GET /api/jobs/all → 401 | Request sent without `Authorization` (token state empty when fetchJobs runs before token hydration). |
| POST /api/admin/bulk-parse/upload → 502 | Backend calls `bulk_upload()` → `requests.post(BULK_PARSER_URL + '/api/upload')` → Connection refused → returns (False, {'error': '...'}) → route returns 502. |
| Connection refused localhost:8001 | No process listening on 8001; Bulk-Resume-Parser microservice not started. |
| “Processing (102)” after failure | Frontend may set jobId/progress from a previous run or from a partial response; or shows file count as “processing” even when upload failed. |

---

## 3. Step-by-Step Fix Plan

### A. Backend: Bulk parser service availability

- **Start the Bulk-Resume-Parser service** on port 8001 (or set `BULK_PARSER_URL` to where it runs).
- **Startup check**: On app load, if `BULK_PARSER_URL` is set, optionally probe it (e.g. GET health or HEAD) and log a **warning** (do not block startup) so operators see “Bulk parser unreachable” in logs.
- **Health endpoint**: Expose a `/health/bulk-parser` or include bulk-parser status in `/health` so the frontend or a load balancer can detect dependency failure.

### B. Auth/JWT for admin routes

- **Send token for /api/jobs/all**: When calling `apiRequest` for HR-only routes, use a token that is definitely present: e.g. `token: auth.isLoggedIn ? (token || tokenService.getToken()) : undefined` so that even before React state `token` is hydrated, the request uses `tokenService.getToken()`.
- **Do not call fetchJobs for HR until token is available**: Alternatively, run fetchJobs only when `auth.isLoggedIn && (token || tokenService.getToken())` for the HR branch, so we never send /api/jobs/all without a token.

### C. Internal service-to-service (backend → Bulk-Resume-Parser)

- **Timeouts**: Already 30s upload, 10s progress, 120s download; keep them.
- **Clear 502/503**: When bulk_parsing_service returns failure due to connection error, return **503** with a body like `{"error": "Bulk parsing service unavailable", "code": "BULK_PARSER_UNREACHABLE"}` so the frontend can show a specific message and avoid retry storms (e.g. do not retry 503 for upload).
- **No retry storm**: Backend should not retry the outbound request to 8001 indefinitely; current code does one attempt per request, which is correct.

### D. Frontend behavior

- **502/503 on upload**: Do not set `jobId` or “processing” state. Show error: “Bulk parsing service unavailable. Ensure the parsing service is running.”
- **Retry**: Do not retry upload on 502/503 (treat as “dependency down”); optionally retry progress/download with backoff and a max count.
- **Auth**: Use `tokenService.getToken()` when `auth.isLoggedIn` and `token` state is empty so /api/jobs/all and admin routes always send a token when the user is logged in.

---

## 4. Concrete Fixes

### Backend

- **Config (.env)**
  - Document `BULK_PARSER_URL` (e.g. `http://localhost:8001`). If the service runs elsewhere, set it. If not using bulk parsing, leave unset or comment out; admin upload will then return 503 with a clear message if we add a check.
- **Startup**
  - Optional: after app init, in a background thread or after first request, check reachability of `BULK_PARSER_URL` and log a warning if unreachable. Do not block startup.
- **bulk_parsing_service.py**
  - On `ConnectionError` (and similar), return a structured error, e.g. `{'error': 'Bulk parsing service unavailable', 'code': 'BULK_PARSER_UNREACHABLE'}`.
- **admin routes**
  - When bulk_upload returns failure with `code == 'BULK_PARSER_UNREACHABLE'`, return **503** and the same body; otherwise keep 502 for other upstream errors.
- **Health**
  - Add GET `/health` or extend existing to optionally include `bulk_parser: "ok" | "unreachable"` by probing `BULK_PARSER_URL` (non-blocking, short timeout).

### Frontend

- **AppContext fetchJobs**
  - Use `token: auth.isLoggedIn ? (token || tokenService.getToken()) : undefined` so HR requests always send a token once auth says logged in.
- **BulkResumeParser**
  - On upload response: if status 502/503, do not set jobId; set error state: “Bulk parsing service unavailable. Ensure the parsing service is running (see README).”
  - **api.js**: For upload only, consider `skipRetry: true` on 502/503 to avoid retry storms (or keep retry but with small max and backoff; prefer no retry for 503).

---

## 5. Bad Production Patterns Identified

- **Silent auth failure**: Sending /api/jobs/all without a token when auth state says “logged in” leads to 401 and confusing UX; fix by ensuring token is sent (e.g. from tokenService when state not yet hydrated).
- **Retry storm on 502**: Retrying POST /api/admin/bulk-parse/upload on 502 when the parsing service is down causes repeated failures; treat 502/503 as “dependency down” and do not retry upload (or limit to 1 retry with backoff).
- **Misleading “Processing” state**: Showing “Processing (102)” when upload failed (502) is incorrect; only set processing state when upload returns 200 and a job_id.
- **No dependency visibility**: Backend does not expose whether the bulk parser is reachable; adding a health check or /health detail improves operability.

---

## 6. Hardening Recommendations

- **Health checks**
  - Backend: GET /health returns 200 and optionally `{"bulk_parser": "ok"|"unreachable"}`.
  - Frontend: On bulk parser page, optionally call a “bulk parser status” or /health and show a banner if unreachable before user uploads.
- **Startup dependency validation**
  - Log a clear warning at startup if `BULK_PARSER_URL` is set but unreachable (e.g. “Bulk parser at … is not reachable; bulk upload will return 503”). Do not block startup.
- **Error surfacing**
  - Backend: Return 503 with `code: "BULK_PARSER_UNREACHABLE"` when the parsing service cannot be reached.
  - Frontend: Map 502/503 on upload to a single, actionable message and do not show “Processing” when upload failed.

---

## 7. Verification Checklist

- [ ] Bulk-Resume-Parser process is running and listening on the port specified by `BULK_PARSER_URL` (e.g. 8001).
- [ ] `curl -s http://localhost:8001/health` (or equivalent) returns 200 when the service is up.
- [ ] Backend `.env` has `BULK_PARSER_URL=http://localhost:8001` (or correct URL).
- [ ] As HR, after login, GET /api/jobs/all returns 200 with `Authorization: Bearer <token>` (check Network tab; no 401).
- [ ] POST /api/admin/bulk-parse/upload with valid JWT and files returns 200 and a `job_id` when the parser is up; returns 503 with body containing “Bulk parsing service unavailable” when the parser is down.
- [ ] Frontend bulk parser page: on 503/502 upload response, shows “Bulk parsing service unavailable” and does not show “Processing (102)” or set jobId.
- [ ] Frontend jobs list (HR): no 401 on initial load after login; token is sent (tokenService used when token state empty).
