# HR Job Portal

Full-stack recruitment platform for HR teams and job seekers: job posting, candidate applications, AI-powered matching (ATS), resume/JD parsing, and optional bulk resume processing.

---

## Key Features

| Audience | Capabilities |
|----------|--------------|
| **HR / Recruiters** | Job CRUD, application tracking, resume viewing, AI match scores, bulk resume parser, feedback management |
| **Candidates** | OTP-verified signup, profile & resume upload, job search, one-click apply, application status & match score |
| **Super Admin** | System-wide dashboard, admin/candidate/job/application management |

- **Authentication:** Separate HR and candidate flows; JWT access + refresh; OTP email verification for signup
- **Parsing:** Resume and job description (PDF/DOC/DOCX) via LLM; TOON schema; optional external bulk parser
- **ATS:** In-process or n8n webhook; match score and shortlist stored on application
- **Support & feedback:** Contact form, HRMS testing feedback with optional screenshot

---

## Tech Stack

| Layer | Technologies |
|-------|---------------|
| **Frontend** | React 18, Vite 5, React Router 6, Tailwind CSS, Radix UI, Framer Motion |
| **Backend** | Python 3.8+, Flask, PostgreSQL (psycopg3), JWT, bcrypt, Flask-Mail |
| **Optional** | Electron (desktop bulk parser), n8n (ATS workflow), external Bulk-Resume-Parser API |

---

## Architecture Overview

```
[Browser] ──► [React SPA (Vite)] ──► [Flask API] ──► [PostgreSQL]
                    │                     │
                    │ Bearer JWT           ├── Parsing (LLM / TOON)
                    │                     ├── Optional: ATS callback, Bulk Parser
                    └─────────────────────┘
```

- **Frontend:** Single-page app; single AppContext for auth, jobs, applicant state; role-based route guards (HR, Candidate, Super Admin).
- **Backend:** Monolithic Flask app; blueprints for auth, jobs, candidate, applications, sessions, parsing, support, feedback, admin, super-admin. Connection-pooled PostgreSQL; raw SQL via `db_run`/`db_get`/`db_all`.

Detailed architecture, API catalog, data flows, and security notes: **[docs/TECHNICAL_DOCUMENTATION.md](docs/TECHNICAL_DOCUMENTATION.md)**.

---

## Screenshots

_Add screenshots here (e.g. Home, Jobs list, HR Dashboard, Applicant profile, Bulk parser) for GitHub and onboarding._

---

## Getting Started

### Prerequisites

| Requirement | Version | Check |
|-------------|---------|--------|
| Node.js | 16+ | `node --version` |
| Python | 3.8+ | `python --version` |
| PostgreSQL | 12+ | Local or cloud (e.g. Supabase, Neon) |

### Quick Start (recommended)

From repository root:

```bash
# 1. Copy backend env (or start.js will create from .env.example)
cp backend/.env.example backend/.env

# 2. Edit backend/.env: set POSTGRES_* or DATABASE_URL

# 3. Run app (installs deps, starts backend + frontend, opens browser)
node start.js
```

`start.js` creates backend venv, runs pip install, npm install in frontend, starts Flask (port 3000) and Vite (port 5173), waits for both to be ready, then opens http://localhost:5173. Use **Ctrl+C** to stop.

### Manual Run

**Backend:**

```bash
cd backend
python -m venv venv
# Windows: .\venv\Scripts\Activate  |  macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python app.py
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

- **Frontend:** http://localhost:5173  
- **Backend / Health:** http://localhost:3000, http://localhost:3000/health  

Database and tables are created automatically on first backend run from `backend/schema_pg/*.sql`.

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Yes* | PostgreSQL connection |
| `DATABASE_URL` | Yes* | Alternative: full URL (e.g. `postgresql://user:pass@host:5432/JobPortal`) |
| `PORT` | No | Server port (default `3000`) |
| `JWT_SECRET` | Yes | Secret for JWT signing (change in production) |
| `MAIL_USERNAME`, `MAIL_PASSWORD` | For OTP | SMTP (e.g. Gmail App Password); set `MAIL_SUPPRESS_SEND=true` to disable |
| `XAI_MODEL`, `HRMS_API_KEY_1`… | For parsing | LLM (e.g. Grok) for resume/JD parsing |
| `BULK_PARSER_URL` | Optional | External bulk resume parser API |
| `N8N_WEBHOOK_URL`, `N8N_CALLBACK_SECRET` | Optional | n8n ATS workflow and callback auth |

\* Either POSTGRES_* or DATABASE_URL.

### Frontend (`frontend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `http://localhost:3000` | Backend API base URL |
| `VITE_API_TIMEOUT_MS` | `30000` | Request timeout (ms) |
| `VITE_PARSING_API_URL` | — | Optional separate parsing service URL |

---

## Project Structure (summary)

```
├── start.js              # Unified start script
├── frontend/              # React SPA (Vite)
│   ├── src/
│   │   ├── App.jsx       # Routes + guards
│   │   ├── context/      # AppContext (state + API actions)
│   │   ├── guards/       # AdminGuard, CandidateGuard, SuperAdminGuard
│   │   ├── layouts/      # MainLayout, DashboardLayout, AdminLayout
│   │   ├── pages/        # Lazy-loaded route components
│   │   ├── components/   # UI primitives (ui/) + feature components
│   │   ├── services/     # adminService
│   │   └── utils/       # api.js, tokenService, healthCheck, parsingApi
│   └── package.json
├── backend/              # Flask API
│   ├── app.py            # App entry, CORS, blueprints
│   ├── auth.py, jobs.py, candidate.py, applications.py, ...
│   ├── db.py             # PostgreSQL pool + helpers
│   ├── utils.py          # JWT, auth decorators
│   ├── schema_pg/        # PostgreSQL schema (01_schema.sql, ...)
│   └── requirements.txt
├── electron/             # Desktop app for bulk parser (folder access)
└── docs/
    └── TECHNICAL_DOCUMENTATION.md   # Full technical reference
```

---

## API Overview

| Area | Prefix | Examples |
|------|--------|----------|
| Auth (HR) | `/api` | `POST /signup`, `POST /verify-otp`, `POST /login`, `POST /refresh`, `POST /forgot-password`, `POST /reset-password` |
| Candidate | `/api/candidate` | `POST /signup`, `POST /verify-otp`, `POST /login`, `GET|POST /profile` |
| Jobs | `/api/jobs` | `GET /`, `POST /`, `PUT /:id`, `GET /:id/applications` |
| Applications | `/api/applications` | `POST /` (apply), `GET /` (my applications) |
| Parsing | `/api` | `POST /parse/resume`, `POST /parse/jd` |
| Admin | `/api/admin` | `POST /bulk-parse/upload`, `GET /bulk-parse/progress/:id`, `GET /job-matches` |
| Super Admin | `/api/super-admin` | `POST /login`, `GET /stats`, `GET /admins`, `GET /candidates`, `GET /jobs`, `GET /applications` |

Full endpoint list, request/response shapes, and auth requirements: **[docs/TECHNICAL_DOCUMENTATION.md#6-api-documentation](docs/TECHNICAL_DOCUMENTATION.md#6-api-documentation)**.

---

## Scripts

| Command | Where | Description |
|---------|--------|-------------|
| `node start.js` | Root | Copy .env, setup venv + pip + npm, start backend + frontend, open browser |
| `npm run dev` | frontend | Vite dev server (port 5173) |
| `npm run build` | frontend | Production build → `frontend/dist` |
| `npm run preview` | frontend | Preview production build |
| `python app.py` | backend | Run Flask server (port 3000) |
| `npm run electron` | Root | Electron desktop window (bulk parser folder access) |

---

## Deployment

- **Frontend:** Build with `npm run build`; serve `frontend/dist` as a static SPA (configure fallback to `index.html` for client-side routing). Set `VITE_API_URL` to your backend URL.
- **Backend:** Run with Gunicorn (see `backend/gunicorn.conf.py`) or equivalent. Set `FRONTEND_URL`/`FRONTEND_URLS` for CORS. Use a strong `JWT_SECRET` and, in production, consider HttpOnly cookies for tokens (see technical doc).

---

## Bulk Resume Parser (Electron)

Browser file pickers may restrict folder access. For full folder access (e.g. bulk input/output), run the app in Electron:

1. Terminal 1: `cd frontend && npm run dev`
2. Terminal 2 (from root): `npm install && npm run electron`

Electron opens a window that loads the app and uses OS folder dialogs.

---

## Troubleshooting

- **Env validation failed:** Run `cd backend && python env_validator.py`; fix `DATABASE_URL` or `POSTGRES_*` in `backend/.env`.
- **Database connection failed:** Ensure PostgreSQL is running and credentials are correct. Test: `psql -h localhost -U postgres -d JobPortal -c "SELECT 1"`.
- **Port in use:** Stop process on 3000 (backend) or 5173 (frontend). On Windows: `Get-NetTCPConnection -LocalPort 3000 | Select-Object -ExpandProperty OwningProcess | Stop-Process -Force`.
- **Email not sending:** Set `MAIL_SUPPRESS_SEND=true` in `backend/.env` for testing.

More: [SETUP.md](SETUP.md). Performance notes: [PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md).

---

## Contributing

1. Create a feature branch from `main`.
2. Follow existing patterns (see [docs/TECHNICAL_DOCUMENTATION.md](docs/TECHNICAL_DOCUMENTATION.md) for architecture and patterns).
3. Ensure backend and frontend run cleanly; add tests where applicable.
4. Open a pull request with a clear description and reference to any issue.

---

## License

Proprietary. This project is owned by TechBerry InfoTech Pvt. Ltd. See [LICENSE](LICENSE) for full terms.

---

## Contact / Maintainers

For access, support, or contribution questions, contact the project maintainers or TechBerry InfoTech Pvt. Ltd.
