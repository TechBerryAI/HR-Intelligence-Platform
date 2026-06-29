# System Architecture

**Document ID:** ARCH-07  
**Status:** Constitutional — describes the system as designed, not as modified  
**Related:** [04_AI_PLATFORM.md](04_AI_PLATFORM.md) · [06_DATA_MODEL.md](06_DATA_MODEL.md) · [08_DATA_FLOWS.md](08_DATA_FLOWS.md)

---

## Purpose

This document describes the **system architecture** of the Human Capital Intelligence Platform — the major components, their responsibilities, interactions, and future evolution. The repository structure is frozen; this document describes what exists and what will be added within existing boundaries.

---

## System Context

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL SYSTEMS                                  │
│  Email (SMTP) · n8n (optional ATS) · Bulk Parser API · SSO (future)  │
└────────┬──────────────────┬──────────────────┬─────────────────────────┘
         │                  │                  │
         ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    HUMAN CAPITAL INTELLIGENCE PLATFORM                   │
│                                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │ Frontend │  │ Electron │  │ Backend  │  │    AI Platform       │  │
│  │ (React)  │  │ (Desktop)│  │ (Flask)  │  │    (ai/)             │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘  │
│       │              │             │                    │               │
│       └──────────────┴─────────────┴────────────────────┘               │
│                              │                                           │
│                              ▼                                           │
│                    ┌──────────────────┐                                  │
│                    │   PostgreSQL     │                                  │
│                    └──────────────────┘                                  │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        LLM PROVIDERS                                     │
│  X.AI Grok · OpenAI · Anthropic · Ollama (local) · (future providers)   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### Frontend (`frontend/`)

| Aspect | Detail |
|--------|--------|
| **Technology** | React 18, Vite 5, React Router 6, Tailwind CSS, Radix UI, Framer Motion |
| **Port** | 5173 (development) |
| **State management** | Single AppContext (auth, jobs, applicant state) |
| **API communication** | `utils/api.js` — Bearer JWT, retry on 5xx, refresh on 403 |
| **Auth storage** | localStorage + in-memory token service |
| **Route guards** | AdminGuard, CandidateGuard, SuperAdminGuard |

**Responsibilities:**
- Render role-appropriate UI for all actors
- Manage client-side auth state and token lifecycle
- Submit requests to backend API
- Display AI results (match scores, parsing results, reasoning)
- Never contain business logic or direct AI calls

**Structure:**

```
frontend/src/
├── AppContext.jsx           # Global state
├── components/              # Shared UI components
├── pages/                   # Route-level pages
│   ├── admin/               # HR dashboard, bulk parser, feedback
│   ├── applicant/           # Candidate profile, applications
│   ├── super-admin/         # System administration
│   └── public/              # Jobs, login, signup, support
├── guards/                  # Route authorization
└── utils/                   # API client, token service, helpers
```

**Future evolution:**
- Module federation for domain-specific UI packages
- Server-side rendering for SEO (public job pages)
- Real-time updates via WebSocket (application status, bulk parse progress)

---

### Electron (`electron/`)

| Aspect | Detail |
|--------|--------|
| **Technology** | Electron (Node.js) |
| **Role** | Desktop shell only — no business logic |
| **IPC** | Native folder dialog for bulk resume parser |

**Responsibilities:**
- Provide native OS folder selection for bulk resume parsing
- Wrap frontend in desktop window (optional deployment mode)
- Bridge native OS capabilities to frontend via preload script

**Structure:**

```
electron/
├── main.js          # Window management, IPC registration
├── preload.js       # Secure context bridge
└── ipc-handlers.js  # Native dialog handlers
```

**Future evolution:**
- Offline-capable bulk parsing (queue uploads when disconnected)
- System tray integration for parse job notifications
- Auto-update mechanism

---

### Backend (`backend/`)

| Aspect | Detail |
|--------|--------|
| **Technology** | Python 3.8+, Flask, PostgreSQL (psycopg3), JWT (PyJWT), bcrypt |
| **Port** | 3000 |
| **Database** | PostgreSQL with connection pooling; raw SQL via db_run/db_get/db_all |
| **Auth** | JWT access (1hr) + refresh (30d); OTP email verification |

**Responsibilities:**
- System of record for all business entities
- Authentication and authorization
- Business logic orchestration
- AI invocation (via llm_service.py)
- File upload handling and storage
- Email delivery (Flask-Mail)

**Blueprint structure:**

| Blueprint | Routes | Domain |
|-----------|--------|--------|
| `auth_routes` | HR/candidate signup, login, OTP, refresh | Administration |
| `jobs_routes` | Job CRUD, search, enable/disable | Recruitment |
| `candidate_routes` | Profile, resume upload, education/experience | Recruitment |
| `applications_routes` | Apply, status, ATS callback | Recruitment |
| `parsing_routes` | Resume/JD parsing endpoints | Recruitment + AI |
| `sessions_routes` | Session management, login history | Administration |
| `support_routes` | Contact form | Administration |
| `feedback_routes` | Employee feedback | Administration |
| `admin_routes` | Bulk parser, HR feedback admin | Administration |
| `super_admin_routes` | System-wide CRUD, stats | Administration |

**Key services:**

| Service | Path | Purpose |
|---------|------|---------|
| `llm_service.py` | Root | Production LLM parsing (Grok/OpenAI/Anthropic) |
| `llm_key_manager.py` | Root | Multi-key rotation and failover |
| `toon.py` | Root | TOON serialize/deserialize |
| `parsing_utils.py` | Root | TOON validation, text extraction |
| `ats_service.py` | services/ | In-process ATS matching |
| `bulk_parser_service.py` | services/ | Bulk resume processing |
| `notification_service.py` | services/ | Email notifications |

**Future evolution:**
- Event emission on state changes (for async workflows)
- Tenant middleware for multi-tenancy
- API versioning (`/api/v2/`)
- Background job queue (Celery/RQ) for async AI tasks

---

### AI Platform (`ai/`)

See [04_AI_PLATFORM.md](04_AI_PLATFORM.md) for full specification.

| Layer | Directory | Status |
|-------|-----------|--------|
| Runtime | `ai/runtime/` | Implemented (M7) |
| Providers | `ai/providers/` | Ollama + mock |
| Capabilities | `ai/capabilities/` | 7 capabilities defined |
| TOON | `ai/toon/v1/` | TOON-v1 active |
| Contracts | `ai/contracts/` | Domain contracts |
| Schemas | `ai/schemas/` | Document schemas |
| Knowledge | `ai/knowledge/` | 6 reference bases |
| Dataset | `ai/dataset/` | Factory, lake, extraction, proposals |
| Registry | `ai/registry/` | 7 sub-registries |
| Configs | `ai/configs/` | Platform configuration |

**Integration point (M9):**

```
backend/llm_service.py
    └── [AI_USE_GATEWAY=true]
        └── ai/runtime/ adapter
            └── Provider Manager → Capability → TOON output
```

---

### Database (PostgreSQL)

| Aspect | Detail |
|--------|--------|
| **Engine** | PostgreSQL 12+ |
| **Driver** | psycopg3 with connection pooling |
| **Schema management** | Versioned SQL files in `backend/schema_pg/` |
| **Query pattern** | Raw SQL via helper functions (no ORM) |

**Schema files:**

| File | Contents |
|------|----------|
| `01_schema.sql` | Core tables (auth, jobs, profiles, applications, parsing) |
| `02_seed.sql` | Seed data |
| `03_employee_feedback.sql` | Feedback table |

**Storage patterns:**

| Data type | Storage | Example |
|-----------|---------|---------|
| Structured business data | Relational columns | jobs.title, applications.status |
| AI artifacts | TOON text columns | parsed_resumes.toon |
| Binary files | BYTEA or file system | candidate_profiles.resume |
| Audit data | Dedicated tables | login_history |
| Deduplication | Content hash | raw_files.hash |

**Future evolution:**
- Row-level security for multi-tenancy
- Read replicas for analytics queries
- Partitioning for audit logs and raw files
- Encrypted columns for PII

---

### Knowledge Infrastructure (`ai/knowledge/`)

| Base | Purpose | Used by |
|------|---------|---------|
| Skills | Skill alias normalization | Parsing, matching |
| Job Titles | Title standardization | Parsing, interview gen |
| Degrees | Education credential mapping | Parsing |
| Certifications | Certification name mapping | Parsing |
| Companies | Employer normalization | Parsing |
| Locations | Geographic alias resolution | Parsing, matching |

Knowledge bases are curated vocabularies — not RAG stores. See [05_TOON_ARCHITECTURE.md](05_TOON_ARCHITECTURE.md) § Relationship with Knowledge Packs.

---

### Models & Registry (`ai/models/`, `ai/registry/`)

| Component | Purpose | Status |
|-----------|---------|--------|
| `models/adapters/` | LoRA adapter weights | Planned (M5) |
| `models/merged/` | Full merged model weights | Planned (M5) |
| `models/gguf/` | Quantized deployment artifacts | Planned (M7) |
| `registry/models/` | Model lineage metadata | Active |
| `registry/deployments/` | Deployment snapshots | Planned (M7) |
| `registry/evaluations/` | Evaluation run records | Planned (M6) |

Weights are gitignored; registry YAML is committed. See [04_AI_PLATFORM.md](04_AI_PLATFORM.md) § Registry.

---

## Integration Architecture

### Current integrations

| Integration | Direction | Protocol | Purpose |
|------------|-----------|----------|---------|
| **LLM Providers** | Backend → External | HTTPS API | Resume/JD parsing, ATS |
| **SMTP** | Backend → External | SMTP/TLS | OTP emails, notifications |
| **n8n** (optional) | Backend ↔ External | Webhook + callback | ATS workflow automation |
| **Bulk Parser API** (optional) | Backend → External | HTTPS API | High-volume resume parsing |
| **Electron IPC** | Frontend ↔ Electron | IPC | Native folder dialogs |

### Future integrations

| Integration | Direction | Protocol | Purpose |
|------------|-----------|----------|---------|
| **SSO/SAML** | External → Backend | SAML 2.0 / OIDC | Enterprise authentication |
| **Calendar** | Backend ↔ External | CalDAV / Google API | Interview scheduling |
| **E-signature** | Backend → External | REST API | Offer letter signing |
| **LMS** | Backend ↔ External | SCORM / xAPI | Learning content |
| **HRIS** | Backend ↔ External | REST / SFTP | Employee data sync |
| **Data warehouse** | Backend → External | ETL / CDC | Analytics pipeline |
| **Identity provider** | External → Backend | OIDC | Employee SSO |

### Integration principles

1. All integrations go through backend — frontend and AI platform never call external systems directly
2. Integration adapters are isolated modules — swappable without domain logic changes
3. Webhook callbacks require shared secrets (`N8N_CALLBACK_SECRET` pattern)
4. External system failures degrade gracefully — never block core workflows

---

## Interaction Diagrams

### Production request flow

```
┌────────┐     HTTPS/JWT     ┌─────────┐     SQL      ┌────────────┐
│Browser │ ────────────────► │ Backend │ ───────────► │ PostgreSQL │
│(React) │ ◄──────────────── │ (Flask) │ ◄─────────── │            │
└────────┘     JSON response └────┬────┘              └────────────┘
                                  │
                                  │ LLM API call
                                  ▼
                           ┌─────────────┐
                           │ LLM Provider│
                           │ (Grok/etc.) │
                           └─────────────┘
```

### Future integrated flow (M9+)

```
┌────────┐     HTTPS/JWT     ┌─────────┐                    ┌────────────┐
│Browser │ ────────────────► │ Backend │ ──── SQL ──────► │ PostgreSQL │
│(React) │ ◄──────────────── │ (Flask) │ ◄──────────────── │            │
└────────┘                   └────┬────┘                    └────────────┘
                                  │
                                  │ adapter call
                                  ▼
                           ┌─────────────┐     ┌──────────┐
                           │ AI Runtime  │ ──► │ Provider │
                           │ (ai/runtime)│ ◄── │ Manager  │
                           └──────┬──────┘     └────┬─────┘
                                  │                  │
                                  │ TOON output      │ LLM call
                                  ▼                  ▼
                           ┌─────────────┐   ┌─────────────┐
                           │   Backend   │   │ Ollama/Grok │
                           │ (persist)   │   │ /OpenAI/etc │
                           └─────────────┘   └─────────────┘
```

### Bulk parsing flow

```
┌──────────┐  folder path  ┌──────────┐   IPC    ┌──────────┐
│ Electron │ ◄──────────── │ Frontend │ ───────► │ Electron │
│ (native) │ ────────────► │ (React)  │          │ (dialog) │
└──────────┘  selected dir └────┬─────┘          └──────────┘
                                │
                                │ upload batch
                                ▼
                         ┌─────────────┐     ┌──────────────┐
                         │   Backend   │ ──► │ Bulk Parser  │
                         │ (Flask)     │ ◄── │ API / local  │
                         └──────┬──────┘     └──────────────┘
                                │
                                │ poll progress
                                ▼
                         ┌─────────────┐
                         │  Frontend   │
                         │ (progress)  │
                         └─────────────┘
```

---

## Deployment Architecture

### Current (development/single-instance)

```
┌─────────────────────────────────────────┐
│              Single Host                 │
│  ┌─────────┐  ┌─────────┐  ┌────────┐  │
│  │ Frontend│  │ Backend │  │Postgres│  │
│  │ :5173   │  │ :3000   │  │ :5432  │  │
│  └─────────┘  └─────────┘  └────────┘  │
│  start.js orchestrates all three        │
└─────────────────────────────────────────┘
```

### Target (enterprise production)

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   CDN /      │     │  Load        │     │  Backend     │
│   Static     │     │  Balancer    │     │  Instances   │
│   Assets     │     │  (TLS)       │     │  (N replicas)│
└──────────────┘     └──────┬───────┘     └──────┬───────┘
                            │                     │
                            ▼                     ▼
                     ┌──────────────┐     ┌──────────────┐
                     │  Frontend    │     │  PostgreSQL  │
                     │  (SSR/static)│     │  (primary +  │
                     └──────────────┘     │   replica)   │
                                          └──────────────┘
                                                 │
                     ┌──────────────┐            │
                     │  AI Runtime  │ ◄──────────┘
                     │  (scaled)    │
                     └──────┬───────┘
                            │
                     ┌──────┴───────┐
                     │ Ollama / LLM │
                     │  Providers   │
                     └──────────────┘
```

---

## Future Services

Services to be added within existing repository boundaries:

| Service | Location | Domain | Milestone |
|---------|----------|--------|-----------|
| **Event Bus** | `backend/services/events/` | Cross-domain | Enterprise M2 |
| **Notification Service** | `backend/services/notifications/` (extend) | Administration | Enterprise M1 |
| **Tenant Service** | `backend/services/tenant/` | Administration | Enterprise M1 |
| **Analytics Engine** | `backend/services/analytics/` | Analytics | Enterprise M3 |
| **Integration Hub** | `backend/services/integrations/` | Cross-domain | Enterprise M2 |
| **Background Worker** | `backend/workers/` | Cross-domain | Platform M9 |
| **Monitoring Service** | `ai/platform/monitoring/` | AI | Platform M11 |
| **Agent Orchestrator** | `ai/platform/agents/` | AI | Future |

---

## Cross-References

| Topic | Document |
|-------|----------|
| AI platform detail | [04_AI_PLATFORM.md](04_AI_PLATFORM.md) |
| Data model | [06_DATA_MODEL.md](06_DATA_MODEL.md) |
| Workflow sequences | [08_DATA_FLOWS.md](08_DATA_FLOWS.md) |
| Security architecture | [09_SECURITY_MODEL.md](09_SECURITY_MODEL.md) |
| NFRs | [10_NON_FUNCTIONAL_REQUIREMENTS.md](10_NON_FUNCTIONAL_REQUIREMENTS.md) |
| Technical documentation | `docs/TECHNICAL_DOCUMENTATION.md` |
| Backend documentation | `docs/BACKEND_DOCUMENTATION.md` |
| Frontend documentation | `docs/FRONTEND_DOCUMENTATION.md` |
