# Frontend Structure & Code Documentation

> **Update (public apply):** Candidate accounts and `CandidateGuard` / applicant login pages are removed.
> Job applications use a public Apply form on `/jobs` (`ApplyJobModal`) with resume autofill via `POST /api/parse/resume/public`.
> Staff login remains at `/login` → `/login/admin`. Forgot-password is admin-only.

This document describes the frontend directory structure, the purpose of each file and folder, and how the code works.

---

## 1. Frontend Directory Structure

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

## 2. Entry and App Shell

### 2.1 `index.html`

- Single HTML page. The root `<div id="root">` is where React mounts.
- Script: `<script type="module" src="/src/main.jsx">` — Vite serves this as the app entry.

### 2.2 `main.jsx` — React Entry

**What it does:**

- Imports React, ReactDOM, `BrowserRouter`, `App`, and global CSS.
- Creates the root with `ReactDOM.createRoot(document.getElementById('root'))`.
- Renders inside `React.StrictMode` and `BrowserRouter` so the whole app has client-side routing.
- Renders `<App />` as the top-level component.

**Why BrowserRouter:** All routes are client-side; the backend does not serve HTML for these paths.

### 2.3 `App.jsx` — Routes, Providers, and Guards

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

## 3. Context: Global State and API

### 3.1 `context/AppContext.jsx`

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

## 4. Guards

Guards are small wrapper components that either render `children` or redirect.

### 4.1 `guards/AdminGuard.jsx`

- Uses `useApp()` to read `auth`.
- If `!auth.isLoggedIn` or role is not `HR` or `head_hr`, returns `<Navigate to="/login/admin" replace />`.
- Otherwise returns `children`.

### 4.2 `guards/CandidateGuard.jsx`

- Uses `applicantAuth` and `auth`.
- `isHr = auth?.isLoggedIn && auth?.role === 'HR'`.
- `isCandidate = applicantAuth?.isLoggedIn && !isHr`.
- If not `isCandidate`, redirects to `/login/applicant`; otherwise renders `children`.

### 4.3 `guards/HeadHrGuard.jsx`

- If `!auth.isLoggedIn` or role is not `HEAD_HR`, redirects to `/login/admin`.
- Otherwise renders `children`.

---

## 5. Layouts

### 5.1 `layouts/MainLayout.jsx`

- Renders a full-height flex column: `Navbar`, `<main><Outlet /></main>`, and a footer.
- `Outlet` is where child routes (e.g. Home, Jobs) render.

### 5.2 `layouts/DashboardLayout.jsx`

- Same idea as MainLayout but wraps the main content in `PageContainer` for consistent max-width and padding.
- Used for HR dashboard-style pages.

### 5.3 `layouts/AdminLayout.jsx`

- Used for admin sections (e.g. bulk parser, feedback); provides Navbar and Outlet (and optionally sidebar) so admin pages share the same chrome.

---

## 6. Pages (Selected) — Purpose and Code

### 6.1 `pages/Home.jsx`

- **Purpose:** Landing page with hero and search.
- **Code:** Uses `useNavigate()`. Renders `<Hero onSearch={handleSearch}>`. `handleSearch` builds `URLSearchParams` from `keywords` and `location` and navigates to `/jobs?q=...&loc=...`.

### 6.2 `pages/Jobs.jsx`

- **Purpose:** List jobs with client-side filter and apply/save actions.
- **State:** `applyError`, `applyingJobId`; reads from context: jobs, applicantAuth, applicantProfile, jobsError, jobsLoading, fetchJobs, applicantApplications, applicantSavedJobs, toggleSaveJob, applyToJobAsApplicant, auth, superAdminAuth.
- **Query:** Reads `location.search` and builds `query = { keywords, location }` from `q` and `loc`.
- **Filtering:** `useMemo` filters `jobs` by `enabled !== false`, then by keywords (title/company/description) and location (substring match).
- **Search:** `handleSearch` updates URL with new `q` and `loc` so the same filter logic applies and the URL is shareable.
- **Error handling:** If `jobsError`, shows a retry banner and calls `fetchJobs` after 5 seconds. If `applyError`, shows message and optional “Complete profile” link to `/profile/applicant`.
- **Apply:** For each job, calls `applyToJobAsApplicant(job.id)` with loading state in `applyingJobId`; shows “Applying…” and handles `profile_incomplete` / `not_logged_in` etc. via `applyError`.
- **Render:** FilterBar (with initial query), then grid of JobCards with onApply, onToggleSave, isApplied, isSaved, matchScore from context.

### 6.3 `pages/LoginApplicant.jsx`

- **Purpose:** Applicant sign-in form.
- **State:** `applicantId` (email/username), `applicantPassword`, `error`.
- **Submit:** `onApplicantSubmit` calls `loginApplicant(applicantId, applicantPassword)`. On success, reads `redirect` and `applyFor` from `location.search` and navigates to `/profile/applicant` with optional redirect/applyFor in query; otherwise to `/jobs`.
- **UI:** AuthPageLayout with title/subtitle; form with email and PasswordInput; error div; links to “Forgot password?” and “Create account”.

### 6.4 Other pages (short)

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

## 7. Components — Purpose and Code

### 7.1 `components/Navbar.jsx`

- **Purpose:** Top bar with logo, Jobs link, role-based menu (Login / HR dropdown / Applicant dropdown / Super Admin button), and Support dropdown.
- **Derived state:** `isHrLoggedIn`, `isApplicantLoggedIn`, `isSuperAdminLoggedIn` from context auth. `applicantInitials` and `hrInitials` from profile/user names (first letters of first two words).
- **Logout:** `handleLogout` calls `logout()` then `navigate('/')`.
- **NavLink:** Uses a function for `className`: active route gets `text-slate-900 font-semibold`, else `text-slate-600 hover:text-slate-900`.
- **Conditional UI:** If no one logged in, show “Login”. If HR, show avatar dropdown with Dashboard, Candidates, Bulk Resume Parser, Feedback, Settings, Logout. If applicant, dropdown with Profile, Application Status, Settings, Logout. If super admin, link/button to “Super Admin”. Support dropdown: FAQ, Contact Us, HRMS Testing Feedback.

### 7.2 `components/Hero.jsx`

- **Purpose:** Hero section on home page with headline, subtitle, feature pills, and search.
- **Code:** Gradient background and radial overlay; motion.div for headline “Find Your Dream Job Today”; motion.p for subtitle (mentions “AI-powered matching”); list of feature pills (AI Resume Parsing, Instant Apply, Smart Matching) with icons; at the bottom a `SearchBar` with `onSearch={onSearch}` and `large` so the search submits to the parent’s `handleSearch` (which in Home.jsx navigates to `/jobs?q=...&loc=...`).

### 7.3 `components/SearchBar.jsx`

- **Purpose:** Keywords and location inputs with a Search button.
- **Props:** `onSearch`, `large`, `defaultQuery`, `className`.
- **State:** `keywords`, `location`, `isFocused` (for focus ring).
- **Submit:** `submit(e)` calls `e.preventDefault()` and `onSearch({ keywords: keywords.trim(), location: location.trim() })`.
- **Render:** Form with two inputs (keywords placeholder “Title, skills, or company”, location “Location”) and a submit button; optional `large` styling.

### 7.4 `components/FilterBar.jsx`

- **Purpose:** Wrapper that shows SearchBar in a card-style container with initial values from URL.
- **Code:** Receives `onSearch` and `initial` (e.g. `{ keywords, location }`). Renders a motion.div with border/shadow and inside it `<SearchBar key={...} onSearch={onSearch} defaultQuery={initial} />`. The key forces SearchBar to reset when initial query changes.

### 7.5 `components/JobCard.jsx`

- **Purpose:** One job card: title, company, location, salary, experience, skills, description preview; Apply / Save; optional match score and status badge; modal with full description.
- **Props:** `job`, `onApply`, `isApplied`, `applicationStatus`, `isSaved`, `onToggleSave`, `isAdmin`, `isApplying`, `matchScore`.
- **Skills:** Uses `extractRequiredSkillsFromDescription(job.description)`; fallback to `job.skills` or regex on description. Deduplicates by lowercased string.
- **Modal:** `showDescriptionModal` state. Click on card (but not on buttons) opens modal; Escape or overlay click closes. Modal shows full job details and `JobDescriptionView` for description.
- **Apply/Save:** Apply button disabled when `isDisabled` (job.enabled === false) or `isApplied`. Save button toggles via `onToggleSave`; filled bookmark when `isSaved`. Both button areas use `onClick={(e) => e.stopPropagation()` so they don’t trigger the card click.
- **Status badge:** Uses `STATUS_BADGES[applicationStatus]` (applied, reviewed, shortlisted, rejected) for label and icon.

### 7.6 `components/ResumeUploadWithParsing.jsx`

- **Purpose:** Resume upload with optional AI parsing; when parsed, can autofill profile form.
- **Props:** `onAutofill`, `onFileSelect`, `currentFileName`, `onRemove`, `onOpenResume`.
- **State:** `isUploading`, `parseError`, `parseSuccess`, `confidence`, `isDragging`.
- **Flow:** If user is not logged in (no token or !applicantAuth.isLoggedIn), only `onFileSelect(file)` is called (no parsing). If logged in, validates file with `validateFileForParsing(file)`; then calls `onFileSelect(file)` and starts upload. Shows `PremiumUploadOverlay` during upload. Calls `uploadAndParseResume(file)` from parsingApi; on success gets TOON and runs `mapResumeTOONToForm(toon)` then `onAutofill(mapped)`. Sets confidence and success/error message.
- **Drag and drop:** `handleDrop` / `handleDragOver` / `handleDragLeave` for drag state and passing file to `processFile`.
- **Remove:** `handleRemove` clears messages and ref value and calls `onRemove?.()`.

### 7.7 `components/ErrorBoundary.jsx`

- **Purpose:** Catches JavaScript errors in the child tree and shows a fallback UI.
- **Code:** Class component with `state = { hasError: false }`. `getDerivedStateFromError()` sets `hasError: true`. `componentDidCatch` logs error and info. In render, if `hasError` shows “Something went wrong” and “Please refresh the page”; otherwise renders `this.props.children`.

### 7.8 `components/Toast.jsx`

- **Purpose:** Global toast notifications.
- **ToastProvider:** Holds `toasts` array. `push(message, { type, duration })` adds a toast with a random id and removes it after `duration` (default 3000 ms). `remove(id)` filters out that id. `success` and `error` are wrappers around `push` with type. Renders a fixed div (bottom-right) that maps toasts to small cards (red for error, green for success, neutral for info).
- **useToast:** Returns the context value; must be used inside ToastProvider.

### 7.9 `components/ConnectionStatus.jsx`

- **Purpose:** Shows a banner when the backend is unhealthy.
- **Code:** Reads `backendHealthy` from `useApp()`. If false, after 3 seconds sets `showWarning` true so a banner appears (“Connecting to server... backend is starting up”). When healthy again, hides immediately. Renders a fixed top bar with amber background and short message.

---

## 8. Utils — Purpose and Code

### 8.1 `utils/api.js`

- **BASE_URL:** From `import.meta.env.VITE_API_URL` or `http://localhost:3000`, trimmed of trailing slash.
- **apiRequest(path, options):** Options: `method`, `body`, `token`, `headers`, `timeoutMs`, `skipRetry`. Builds full URL; for non-FormData body sets Content-Type and Accept. Adds `Authorization: Bearer` from token or tokenService. Uses AbortController for timeout. On 403 with token, calls `tryRefresh()` (POST /api/refresh with refresh_token); if refresh succeeds, retries the request once with new token. On 401/403 with token, calls `onUnauthorized`. Throws an error with `status` and `data`. Retry loop: up to 2 attempts (or 1 if skipRetry), exponential backoff; only retries on network/5xx/ECONNREFUSED/ETIMEDOUT/ENOTFOUND.
- **setUnauthorizedHandler(fn) / setOnTokensRefreshed(fn):** Store callbacks used by api.js for logout and token update.

### 8.2 `utils/tokenService.js`

- In-memory variables plus localStorage keys `jwtToken` and `refreshToken`.
- **getToken / setToken:** Read/write access token in memory and localStorage.
- **getRefreshToken / setRefreshToken:** Same for refresh token.
- **clear():** Clears both in memory and localStorage.

### 8.3 `utils/healthCheck.js`

- **checkBackendHealth(force):** GET `BASE_URL/health`. If not forced and last check was recent and healthy, returns cached true. Sets `backendHealthy` and `lastCheckTime`. Returns true if response ok, false on failure or timeout (3s).
- **waitForBackend(maxAttempts, delayMs):** Polls checkBackendHealth(true) until true or maxAttempts.
- **getBackendHealthStatus():** Returns cached `backendHealthy`.

### 8.4 `utils/parsingApi.js`

- **ensureArray(value):** Returns [] for null/undefined, the array if array, else [value].
- **normalizeToYYYYMM(value):** Converts parser date (string, object with year/month) to "YYYY-MM" for MonthYearPicker.
- **ensureStringArray(value):** Converts value to array of non-empty strings (handles array, pipe/newline-separated string).
- **validateFileForParsing(file):** Checks extension (pdf, doc, docx) and size (e.g. 10MB); returns { valid, error }.
- **uploadAndParseResume(file):** FormData with file, POST to parse/resume (or VITE_PARSING_API_URL), returns parsed result.
- **mapResumeTOONToForm(toon):** Maps TOON fields (person, education, experience, certifications, skills) to the profile form shape (fullName, email, education[], experiences[], certifications[], etc.) using the above helpers.

### 8.5 Other utils

- **passwordValidation.js:** Client-side password strength rules (length, upper, lower, digit, special).
- **reportUtils.js / pdfReportUtils.js:** Build data and generate PDF reports (e.g. for candidates).
- **avatarColor.js:** Derives a color from a string (e.g. name) for avatar background.

---

## 9. Services

### 9.1 `services/adminService.js`

- **getJobApplications(jobId):** Calls `apiRequest(\`/api/jobs/${jobId}/applications\`)` and returns the response (list of applications with candidate and ATS data). Used by HR views to load candidates per job.

### 9.2 `services/bulkParsingService.js`

- Wraps admin bulk-parse API: upload, progress, download. Used by the BulkResumeParser page.

---

## 10. Hooks

### 10.1 `hooks/useAsyncAction.js`

- **Purpose:** Run an async function once at a time and expose loading state (e.g. for submit buttons).
- **Returns:** `{ run, loading }`.
- **run(asyncFn):** If already running (busyRef), returns. Sets busyRef and loading true, awaits asyncFn(), then sets busyRef and loading false in finally. Prevents double submission and shows loading state.

---

## 11. UI Primitives (`components/ui/`)

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

## 12. Data Flow Summary

1. **User opens app:** main.jsx mounts App → AppProvider hydrates state from localStorage and tokenService, fetches jobs, starts health check.
2. **Navigation:** React Router renders the matching route component; guards redirect if role is wrong.
3. **User action (e.g. Apply):** Page/component calls context action (e.g. applyToJobAsApplicant) → context updates state (optimistic) → apiRequest in api.js → backend; on success context may refetch (fetchApplicantData) or update state; on failure context reverts and may set error message.
4. **Auth:** Login pages call loginHR/loginApplicant; context sets token, user, auth state and persists to localStorage; api.js uses token from tokenService or passed option; on 403 api.js may refresh token and retry, or call logout.

This completes the frontend structure and code documentation.
