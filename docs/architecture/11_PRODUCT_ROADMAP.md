# Product Roadmap

**Document ID:** ARCH-11  
**Status:** Constitutional — sequencing authority for all development  
**Related:** [00_PRODUCT_VISION.md](00_PRODUCT_VISION.md) · [02_DOMAIN_MODEL.md](02_DOMAIN_MODEL.md) · [04_AI_PLATFORM.md](04_AI_PLATFORM.md)

---

## Purpose

This document defines the **product roadmap** for the Human Capital Intelligence Platform — the sequencing of milestones from current state through enterprise workforce intelligence. Milestones are organized by product domain, AI platform, enterprise readiness, and training.

Roadmap principle: **each milestone delivers measurable value without blocking future milestones.**

---

## Roadmap Overview

```
2025 Q3-Q4          2026 Q1-Q2          2026 Q3-Q4          2027+
─────────────────────────────────────────────────────────────────────
│ RECRUITMENT   │ │ RECRUITMENT   │ │ EMPLOYEE      │ │ WORKFORCE     │
│ INTELLIGENCE  │ │ INTELLIGENCE  │ │ LIFECYCLE     │ │ PLATFORM      │
│ (Production)  │ │ (AI Platform) │ │ INTELLIGENCE  │ │ (Full HCIP)   │
│               │ │               │ │               │ │               │
│ M0: Current   │ │ M2-M9: AI     │ │ M10-M14:      │ │ M15+: Org     │
│ Production    │ │ Platform      │ │ Employee      │ │ Intelligence  │
│               │ │ Integration   │ │ Domains       │ │ + Agents      │
─────────────────────────────────────────────────────────────────────
```

---

## Current Milestone — M0: Production Recruitment Platform

**Status:** ✅ Active  
**Timeline:** Current  
**Theme:** Recruitment Intelligence in production

### Delivered

| Capability | Status | Component |
|-----------|--------|-----------|
| Candidate OTP signup/login | ✅ | backend + frontend |
| HR signup/login with roles | ✅ | backend + frontend |
| Job CRUD with enable/disable | ✅ | backend + frontend |
| Candidate profile + resume upload | ✅ | backend + frontend |
| Resume parsing (LLM → TOON) | ✅ | backend/llm_service.py |
| JD parsing (LLM → TOON) | ✅ | backend/llm_service.py |
| Job application with profile gate | ✅ | backend + frontend |
| ATS matching (weighted scoring) | ✅ | backend/ats_service.py |
| Bulk resume parsing | ✅ | backend + electron |
| Super admin dashboard | ✅ | backend + frontend |
| Support form + employee feedback | ✅ | backend + frontend |
| Session management + login history | ✅ | backend |
| TOON-v1 ontology | ✅ | ai/toon/v1/ |
| 7 AI capability packages | ✅ | ai/capabilities/ |
| AI runtime (M7) | ✅ | ai/runtime/ |
| Provider abstraction (Ollama + mock) | ✅ | ai/providers/ |
| Knowledge bases (6 packs) | ✅ | ai/knowledge/ |
| Dataset pipeline foundation | ✅ | ai/dataset/ |
| Registry structure | ✅ | ai/registry/ |
| Product Design System | ✅ | docs/architecture/ |

### Known gaps (addressed in next milestones)

- AI runtime not yet integrated with production HRMS
- No fine-tuned models deployed
- No evaluation benchmarks frozen
- Single-tenant only
- JWT in localStorage
- Candidate password reset not implemented

---

## AI Platform Milestones

These milestones build the governed AI infrastructure in `ai/`. They do not change HRMS routes or APIs until M9.

### M1 — AI Workspace Foundation ✅

**Status:** Complete  
**Deliverables:** `ai/` directory structure, configs, prompts, HRMS dependency map, ADRs  
**HRMS changes:** None

### M1.5 — Architecture Review ✅

**Status:** Complete  
**Deliverables:** Data lake design, registry design, artifact lineage, versioning strategy, platform vision, AI engineering standards  
**HRMS changes:** None

### M2 — Data Contracts (Next)

**Status:** Next  
**Timeline:** 2026 Q1  
**Goal:** Formalize domain schemas before preprocessing

| Deliverable | Location |
|-------------|----------|
| Finalized data contracts | `ai/docs/DATA_CONTRACTS.md` |
| JSON Schema files | `ai/schemas/` |
| Contract → TOON projection mapping | Documentation |
| HRMS validation alignment | Review against `validate_toon_format()` |

**Exit criteria:** All entity contracts reviewed and approved; TOON mappings documented  
**HRMS changes:** None

### M3 — Dataset Engineering

**Status:** Planned  
**Timeline:** 2026 Q1  
**Goal:** First versioned datasets with artifact lineage

| Deliverable | Location |
|-------------|----------|
| HRMS read-only export script | `ai/dataset/` |
| Raw data in lake | `ai/dataset/lake/raw/` |
| Dataset registry entry | `ai/registry/datasets/DS-PARSE-v1.0.0.yaml` |
| Benchmark design | `ai/dataset/lake/benchmark/parsing/v1/` |

**Exit criteria:** ≥ 1,000 labeled resume records with full lineage  
**HRMS changes:** None

### M4 — Data Preprocessing Pipeline

**Status:** Planned  
**Timeline:** 2026 Q1–Q2  
**Goal:** Extract → clean → normalize → validate → split

| Deliverable | Location |
|-------------|----------|
| Stage scripts with manifest chain | `ai/dataset/factory/` |
| Validation gates (≥ 95% pass) | Pipeline gates |
| Training JSONL | `ai/dataset/lake/jsonl/parsing-v1/` |
| Frozen benchmark | `ai/registry/benchmarks/BENCH-PARSE-v1.yaml` |

**Exit criteria:** JSONL dataset produced; benchmark frozen; ≥ 95% validation pass rate  
**HRMS changes:** None

### M5 — QLoRA Training

**Status:** Planned  
**Timeline:** 2026 Q2  
**Goal:** First fine-tuned parsing model with full lineage

| Deliverable | Location |
|-------------|----------|
| Training experiment | `EXP-0001` |
| Config snapshot | `ai/training/configs/` |
| Model registry entry | `ai/registry/models/hrms-parsing-v1.yaml` |
| Adapter + merged weights | `ai/models/adapters/`, `ai/models/merged/` |

**Exit criteria:** Model trained; artifacts committed to registry; reproducible from config snapshot  
**HRMS changes:** None

### M6 — Evaluation & Benchmarking

**Status:** Planned  
**Timeline:** 2026 Q2  
**Goal:** Prove model quality; establish baselines

| Deliverable | Location |
|-------------|----------|
| Evaluation runs (Grok, Ollama, OpenAI, Claude) | `ai/registry/evaluations/` |
| Regression baseline | `ai/evaluation/regression/baseline.yaml` |
| Provider comparison | `ai/evaluation/comparisons/` |
| Promotion decision | Candidate → staging |

**Exit criteria:** Fine-tuned model passes BENCH-PARSE-v1; Grok baseline recorded  
**HRMS changes:** None

### M7 — Ollama Deployment ✅

**Status:** Complete (runtime); GGUF deployment planned  
**Timeline:** 2026 Q2  
**Goal:** Production-ready local inference

| Deliverable | Location | Status |
|-------------|----------|--------|
| AI runtime | `ai/runtime/` | ✅ Complete |
| GGUF artifact | `ai/models/gguf/` | Planned |
| Modelfile | `ai/exports/modelfiles/` | Planned |
| Deployment registry | `ai/registry/deployments/` | Planned |

**Exit criteria:** Runtime operational; GGUF model deployable to Ollama with health checks  
**HRMS changes:** None

### M8 — LLM Gateway

**Status:** Planned  
**Timeline:** 2026 Q2–Q3  
**Goal:** Provider routing and inference management

| Deliverable | Location |
|-------------|----------|
| Provider routing + caching + fallback | `ai/runtime/` (extend) |
| Additional providers (Grok, OpenAI, Claude, Gemini) | `ai/providers/` |
| Provider registry | `ai/registry/providers/` |
| Gateway tested against BENCH-PARSE | Evaluation record |

**Exit criteria:** Gateway serves all 7 capabilities via CLI without HRMS; fallback verified  
**HRMS changes:** None

### M9 — HRMS Integration

**Status:** Planned  
**Timeline:** 2026 Q3  
**Goal:** Non-breaking production integration

| Deliverable | Location |
|-------------|----------|
| `llm_service.py` adapter refactor | `backend/llm_service.py` |
| Feature flag | `AI_USE_GATEWAY=true` |
| Integration config bundle | `ai/exports/integration/` |
| Model version tracking | Deployment registry ID in `model_version` |

**Exit criteria:** Production parsing runs through AI gateway with feature flag; rollback verified  
**HRMS changes:** `llm_service.py` internals only

### M10 — Advanced HR AI

**Status:** Planned  
**Timeline:** 2026 Q3–Q4  
**Goal:** Second+ features on platform (matching, summarization, chat in production)

| Deliverable | Location |
|-------------|----------|
| BENCH-MATCH-v1 benchmark | `ai/registry/benchmarks/` |
| Matching model (optional fine-tune) | `ai/registry/models/hrms-matching-v1.yaml` |
| Production matching via gateway | Capability integration |
| HR chat with context (RAG foundation) | `hr_chat` capability enhancement |

**Exit criteria:** Matching and chat served through gateway in production; benchmarks passing  
**HRMS changes:** New feature endpoints or background jobs (scoped separately)

### M11 — Monitoring & Continuous Improvement

**Status:** Planned  
**Timeline:** 2026 Q4  
**Goal:** Closed-loop quality, cost, and drift monitoring

| Deliverable | Location |
|-------------|----------|
| Monitoring service | `ai/platform/monitoring/` |
| Scheduled benchmark regression | CI/automation |
| Human correction export → training pipeline | Dataset feedback loop |
| Model promotion automation | Registry workflow |

**Exit criteria:** Drift detected and alerted; correction loop operational; monthly regression automated  
**HRMS changes:** Observability hooks only

---

## Enterprise Milestones

These milestones prepare the platform for Fortune 500 deployment.

### E1 — Multi-Tenancy Foundation

**Timeline:** 2026 Q3  
**Depends on:** M9

| Deliverable | Description |
|-------------|-------------|
| Tenant entity + middleware | Row-level security on all tables |
| Tenant provisioning API | Self-service or admin-provisioned tenants |
| Tenant-scoped RBAC | Roles scoped to tenant |
| Data export per tenant | GDPR portability |

**Domains affected:** Administration, all business domains

### E2 — Enterprise Authentication

**Timeline:** 2026 Q3–Q4  
**Depends on:** E1

| Deliverable | Description |
|-------------|-------------|
| SSO/SAML integration | Enterprise identity provider |
| OIDC support | OAuth 2.0 / OpenID Connect |
| MFA (TOTP) | Multi-factor authentication |
| HttpOnly cookie tokens | Replace localStorage JWT |
| Candidate password reset | Backend routes + frontend flow |

**Domains affected:** Administration

### E3 — Enterprise Security & Compliance

**Timeline:** 2026 Q4  
**Depends on:** E2

| Deliverable | Description |
|-------------|-------------|
| Comprehensive audit logging | All mutations + AI inferences |
| PII encryption at rest | Sensitive column encryption |
| Data residency configuration | Region selection per tenant |
| GDPR endpoints | Erasure, portability, consent management |
| SOC 2 alignment | Control documentation |

**Domains affected:** Administration, Security

### E4 — Enterprise Integration Hub

**Timeline:** 2027 Q1  
**Depends on:** E1

| Deliverable | Description |
|-------------|-------------|
| Webhook event system | Domain events to external systems |
| REST API v2 | Versioned, documented, rate-limited |
| Calendar integration | Interview scheduling |
| HRIS sync adapter | Employee data bidirectional sync |
| E-signature integration | Offer letter signing |

**Domains affected:** Hiring, Employee, Integration

### E5 — Enterprise Operations

**Timeline:** 2027 Q1–Q2  
**Depends on:** E3

| Deliverable | Description |
|-------------|-------------|
| High availability deployment | Multi-instance, load balanced |
| Automated backup + DR | RPO ≤ 1hr, RTO ≤ 4hr |
| Observability stack | Metrics, logs, traces, alerts |
| SLA monitoring + reporting | Customer-facing SLA dashboard |
| Tenant admin portal | Self-service configuration |

**Domains affected:** Administration, all (operational)

---

## Product Domain Milestones

These milestones extend the platform beyond recruitment into the full employee lifecycle.

### P1 — Hiring Intelligence

**Timeline:** 2027 Q1  
**Depends on:** M10, E1

| Feature | Capability | Domain |
|---------|-----------|--------|
| Interview scheduling + feedback | `interview_intelligence` | Hiring |
| Offer management + generation | `offer_intelligence` | Hiring |
| Hire confirmation workflow | (workflow) | Hiring → Employee |
| TOON-v2: interview, offer types | TOON extension | AI |

**Exit criteria:** End-to-end flow: application → interview → offer → hire

### P2 — Employee Lifecycle

**Timeline:** 2027 Q2  
**Depends on:** P1

| Feature | Capability | Domain |
|---------|-----------|--------|
| Employee records | `employee_intelligence` | Employee |
| Onboarding plans | `onboarding_intelligence` | Employee |
| Employee self-service portal | (frontend) | Employee |
| TOON-v2: employee, onboarding types | TOON extension | AI |

**Exit criteria:** Hired candidate becomes active employee with onboarding plan

### P3 — Learning Intelligence

**Timeline:** 2027 Q3  
**Depends on:** P2

| Feature | Capability | Domain |
|---------|-----------|--------|
| Learning catalog + enrollment | `learning_intelligence` | Learning |
| Skill assessments | `skill_intelligence` | Learning |
| AI-recommended learning paths | `learning_intelligence` | Learning |
| LMS integration (SCORM) | (integration) | Learning |

**Exit criteria:** Employee completes AI-recommended learning path; skill profile updated

### P4 — Performance Intelligence

**Timeline:** 2027 Q4  
**Depends on:** P2

| Feature | Capability | Domain |
|---------|-----------|--------|
| Review cycles + goals | `performance_intelligence` | Performance |
| AI-assisted review writing | `performance_intelligence` | Performance |
| 360-degree feedback | (workflow) | Performance |
| Development plan generation | `performance_intelligence` | Performance |

**Exit criteria:** Complete review cycle with AI-assisted reviews and development plans

### P5 — Organization Intelligence

**Timeline:** 2028 Q1  
**Depends on:** P2, P3, P4

| Feature | Capability | Domain |
|---------|-----------|--------|
| Organization graph | `organization_intelligence` | Organization |
| Workforce planning | `workforce_planning` | Organization |
| Succession planning | `succession_intelligence` | Organization |
| Internal mobility matching | `career_intelligence` | Employee |
| Analytics dashboards | `analytics_intelligence` | Analytics |

**Exit criteria:** CHRO dashboard with workforce planning and succession visibility

### P6 — Workforce Platform

**Timeline:** 2028+  
**Depends on:** P5

| Feature | Domain |
|---------|--------|
| Payroll intelligence | Compensation |
| Attendance management | Time & Attendance |
| Leave management | Leave |
| AI agents (governed, auditable) | AI |
| Predictive workforce analytics | Analytics |

---

## Training Milestones

Fine-tuned model development milestones aligned with AI platform milestones.

| Milestone | Model | Dataset | Benchmark | Platform milestone |
|-----------|-------|---------|-----------|-------------------|
| T1 | `hrms-parsing-v1` | DS-PARSE-v1.0.0 | BENCH-PARSE-v1 | M5–M7 |
| T2 | `hrms-matching-v1` | DS-MATCH-v1.0.0 | BENCH-MATCH-v1 | M10 |
| T3 | `hrms-summary-v1` | DS-SUMMARY-v1.0.0 | BENCH-SUMMARY-v1 | M10 |
| T4 | `hrms-interview-v1` | DS-INTERVIEW-v1.0.0 | BENCH-GEN-v1 | P1 |
| T5 | `hrms-employee-v1` | DS-EMPLOYEE-v1.0.0 | BENCH-PARSE-v2 | P2 |
| T6 | `hrms-performance-v1` | DS-PERF-v1.0.0 | BENCH-GEN-v2 | P4 |

Training ordering principle: **contracts → data → preprocess → train → eval → deploy**. Never train on unvalidated data. See [04_AI_PLATFORM.md](04_AI_PLATFORM.md).

---

## Milestone Dependency Graph

```
M0 (Current) ──► M2 ──► M3 ──► M4 ──► M5 ──► M6 ──► M7 ──► M8 ──► M9 ──► M10 ──► M11
                                      │                              │
                                      T1 (parsing model)               │
                                                                     ▼
                                                              E1 (multi-tenant)
                                                                     │
                                                              E2 (SSO/MFA)
                                                                     │
                                                              E3 (compliance)
                                                                     │
                    ┌────────────────────────────────────────────────┤
                    │                                                │
                    ▼                                                ▼
             P1 (Hiring)                                      E4 (integrations)
                    │                                                │
                    ▼                                                ▼
             P2 (Employee)                                    E5 (operations)
                    │
          ┌────────┼────────┐
          ▼        ▼        ▼
     P3 (Learn) P4 (Perf)  │
          │        │        │
          └────────┼────────┘
                   ▼
            P5 (Organization)
                   │
                   ▼
            P6 (Workforce Platform)
```

---

## Prioritization Framework

When milestones compete for resources, prioritize by:

1. **Safety and security** — E3 before feature expansion
2. **Platform foundation** — M2–M9 before product domains
3. **Customer value** — M9 (HRMS integration) before P1 (hiring)
4. **Dependency order** — Never skip a dependency milestone
5. **Revenue impact** — Enterprise milestones (E*) unlock revenue; prioritize when sales pipeline demands

---

## Roadmap Governance

| Activity | Frequency | Owner |
|----------|-----------|-------|
| Milestone review | Monthly | Product + Architecture |
| Roadmap amendment | Quarterly | Executive team |
| AI platform progress | Per milestone | AI Architect |
| Enterprise readiness assessment | Quarterly | Security + Architecture |
| Customer-driven reprioritization | As needed | Product (with architecture review) |

Roadmap amendments require update to this document and review of affected ARCH documents for consistency.

---

## Cross-References

| Topic | Document |
|-------|----------|
| Vision and long-term goals | [00_PRODUCT_VISION.md](00_PRODUCT_VISION.md) |
| Domain definitions | [02_DOMAIN_MODEL.md](02_DOMAIN_MODEL.md) |
| AI capabilities | [03_CAPABILITY_MAP.md](03_CAPABILITY_MAP.md) |
| AI platform architecture | [04_AI_PLATFORM.md](04_AI_PLATFORM.md) |
| NFRs and SLAs | [10_NON_FUNCTIONAL_REQUIREMENTS.md](10_NON_FUNCTIONAL_REQUIREMENTS.md) |
| AI platform roadmap (implementation detail) | `ai/docs/ROADMAP.md` |
| AI platform vision | `ai/docs/PLATFORM_VISION.md` |
