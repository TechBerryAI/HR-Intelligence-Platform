# Product Constitution

**Document ID:** ARCH-01  
**Status:** Constitutional — binding on all product, engineering, and AI decisions  
**Authority:** Second only to [00_PRODUCT_VISION.md](00_PRODUCT_VISION.md)  
**Related:** All ARCH-02 through ARCH-11 documents

---

## Purpose

This document defines the **immutable principles** governing the Human Capital Intelligence Platform. Every architectural decision, database schema, API design, AI capability, and UX pattern must derive from and comply with these principles.

When in doubt, consult this constitution before writing code.

---

## Product Principles

| ID | Principle | Rule |
|----|-----------|------|
| P-01 | **Domain sovereignty** | Each business domain owns its entities, lifecycle, and actors. No domain may directly mutate another domain's entities without an explicit integration contract. |
| P-02 | **Progressive lifecycle** | The platform supports the complete employee lifecycle. New lifecycle stages are added as domains — never as parallel products. |
| P-03 | **Role-based experience** | Every actor (Candidate, HR, Manager, Admin, Super Admin, future: Employee, Learner) receives an experience scoped to their responsibilities. |
| P-04 | **Intelligence everywhere** | Every domain workflow has a corresponding AI capability (current or planned). Workflows without intelligence are temporary. |
| P-05 | **Explainability by default** | Every AI-generated score, match, ranking, or recommendation must include human-readable reasoning accessible to authorized users. |
| P-06 | **Human authority** | AI recommends; humans decide. Automated actions require explicit enterprise configuration and audit trail. |
| P-07 | **Single product surface** | Candidates, HR, and administrators interact with one platform — not a collection of disconnected modules. |
| P-08 | **Enterprise readiness from day one** | Multi-tenancy, RBAC, audit logging, and data isolation are designed in — not retrofitted. |

---

## Architecture Principles

| ID | Principle | Rule |
|----|-----------|------|
| A-01 | **Repository structure is frozen** | The monorepo layout (`frontend/`, `backend/`, `electron/`, `ai/`) is immutable. New capabilities extend within existing boundaries. |
| A-02 | **Separation of concerns** | Frontend renders. Backend orchestrates business logic and persistence. AI runtime executes intelligence. Electron provides native OS integration only. |
| A-03 | **Backend as system of record** | PostgreSQL holds authoritative business state. AI runtime is stateless with respect to business entities. |
| A-04 | **TOON as interchange format** | All structured human-capital document data (resumes, JDs, ATS results, future: performance reviews, learning records) flows through TOON between AI and persistence. |
| A-05 | **Capability isolation** | Each AI capability is a self-contained package with its own prompt, schema, validation, and benchmarks. Capabilities do not share mutable state. |
| A-06 | **Integration boundary** | HRMS backend integrates with AI platform through a defined adapter (`llm_service.py` internals). Route handlers and API contracts remain stable. |
| A-07 | **Event-ready design** | Domain state changes are designed to emit events (future). Current synchronous flows must not preclude async event propagation. |
| A-08 | **No vendor lock-in at the domain layer** | Business domains depend on abstractions (TOON, capability contracts), not on specific LLM providers or cloud services. |

---

## Engineering Principles

| ID | Principle | Rule |
|----|-----------|------|
| E-01 | **Minimal diff discipline** | Changes solve one problem. No drive-by refactors. No scope expansion without explicit approval. |
| E-02 | **Convention over configuration** | Follow existing patterns in each layer before introducing new abstractions. |
| E-03 | **Raw SQL with schema migrations** | Backend persistence uses versioned SQL schema files (`schema_pg/`). ORM introduction requires constitutional amendment. |
| E-04 | **Colocated tests** | Tests live with their owner module (`ai/capabilities/*/tests/`, backend tests colocated). No monolithic test directory. |
| E-05 | **Environment-driven configuration** | Secrets, provider selection, and feature flags are environment variables — never hardcoded. |
| E-06 | **Backward-compatible APIs** | API changes are additive. Breaking changes require versioning (`/api/v2/`) and migration period. |
| E-07 | **Documentation as code** | Architecture decisions are recorded as ADRs in `ai/docs/adr/`. Product decisions are recorded in `docs/architecture/`. |
| E-08 | **No silent failures** | Every error path logs context. AI failures degrade gracefully with explicit fallback — never return fabricated data. |

---

## AI Principles

| ID | Principle | Rule |
|----|-----------|------|
| AI-01 | **Capability, not prompt** | Intelligence is delivered as versioned capabilities with schemas and benchmarks — not ad-hoc prompts in route handlers. |
| AI-02 | **Schema-first output** | Every capability defines an output schema (`schema.json`). LLM output is validated before acceptance. |
| AI-03 | **Ontology before storage** | LLM output is projected into TOON before persistence. Raw LLM text is never the system of record. |
| AI-04 | **Benchmark-gated deployment** | No model or prompt reaches production without passing frozen benchmark regression (BENCH-*). |
| AI-05 | **Lineage traceability** | Every inference records: capability ID, capability version, provider, model ID, prompt version, and input hash. |
| AI-06 | **Provider fallback** | Primary provider failure triggers retry on secondary provider. Fallback is logged and auditable. |
| AI-07 | **Continuous improvement** | Human corrections in production feed the dataset pipeline for retraining and evaluation. |
| AI-08 | **Knowledge pack separation** | Reference vocabularies (skills, titles, degrees) are curated knowledge bases — not embedded in prompts or model weights. |

---

## Security Principles

| ID | Principle | Rule |
|----|-----------|------|
| S-01 | **Defense in depth** | Authentication, authorization, input validation, output sanitization, and audit logging at every layer. |
| S-02 | **Least privilege** | Roles receive minimum permissions required. Super Admin is a break-glass role with enhanced audit. |
| S-03 | **Tenant isolation** | Enterprise tenant data is logically and physically isolated. Cross-tenant queries are architecturally impossible. |
| S-04 | **PII minimization** | Collect only necessary personal data. AI processing uses minimum required fields. PII is never logged in plaintext. |
| S-05 | **Secrets never in code** | API keys, JWT secrets, and provider credentials exist only in environment/secrets management. |
| S-06 | **Prompt injection defense** | User-provided content is sandboxed in prompt templates. System instructions are immutable at runtime. |
| S-07 | **Audit everything** | Authentication events, authorization decisions, data mutations, and AI inferences are logged with actor, timestamp, and context. |
| S-08 | **Secure by default** | New features ship with authentication required unless explicitly public (e.g., job listings, contact form). |

Full security model: [09_SECURITY_MODEL.md](09_SECURITY_MODEL.md).

---

## UX Principles

| ID | Principle | Rule |
|----|-----------|------|
| UX-01 | **Role-appropriate complexity** | Candidates see guided flows. HR sees operational dashboards. Admins see governance controls. |
| UX-02 | **Progressive disclosure** | Advanced features (bulk parsing, AI reasoning, admin settings) are revealed contextually — not on first visit. |
| UX-03 | **Trust through transparency** | AI match scores display reasoning. Parsing confidence is visible. Errors explain what happened and what to do next. |
| UX-04 | **Accessibility baseline** | WCAG 2.1 AA compliance for all public and employee-facing surfaces. |
| UX-05 | **Responsive-first** | Web experience works on desktop, tablet, and mobile. Electron extends desktop with native folder access only. |
| UX-06 | **Consistent design language** | Radix UI primitives, Tailwind tokens, and shared component patterns across all roles. |
| UX-07 | **Failure is informative** | Empty states, error states, and loading states communicate status and next actions — never blank screens. |
| UX-08 | **Performance perceived** | Optimistic UI where safe. Skeleton loaders for async content. No blocking spinners on navigation. |

---

## Scalability Principles

| ID | Principle | Rule |
|----|-----------|------|
| SC-01 | **Horizontal backend scaling** | Backend is stateless (JWT, connection pool). Multiple instances behind load balancer require no code change. |
| SC-02 | **Async intelligence** | AI inference runs asynchronously for non-blocking workflows (ATS matching, bulk parsing). Synchronous only for interactive flows (chat, single parse). |
| SC-03 | **Database as bottleneck awareness** | Query patterns are indexed. Large reads paginate. Bulk operations batch. Connection pooling is mandatory. |
| SC-04 | **AI runtime isolation** | AI runtime scales independently of backend. Provider rate limits are managed at the runtime layer. |
| SC-05 | **Tenant-scoped scaling** | Enterprise tenants may receive dedicated AI runtime instances without affecting shared tenants. |
| SC-06 | **Data lifecycle management** | Raw files, parsed artifacts, and audit logs have defined retention policies per tenant configuration. |

Full NFRs: [10_NON_FUNCTIONAL_REQUIREMENTS.md](10_NON_FUNCTIONAL_REQUIREMENTS.md).

---

## Governance Principles

| ID | Principle | Rule |
|----|-----------|------|
| G-01 | **Constitutional hierarchy** | Product Design System (ARCH-00–11) > ADRs > Technical Documentation > Code. Lower layers must conform to higher. |
| G-02 | **ADR for architectural decisions** | Significant technical decisions require an ADR in `ai/docs/adr/` before implementation. |
| G-03 | **Registry for AI artifacts** | Models, datasets, benchmarks, prompts, providers, evaluations, and deployments are registered in `ai/registry/`. |
| G-04 | **Change control for capabilities** | New or modified AI capabilities require: schema update, benchmark update, evaluation run, and registry entry before deployment. |
| G-05 | **Feature flags for integration** | AI platform integration with HRMS uses feature flags (`AI_USE_GATEWAY`). Rollback is instant. |
| G-06 | **Data governance** | Dataset creation, labeling, and usage follow artifact lineage documented in `ai/docs/ARTIFACT_LINEAGE.md`. |

---

## Versioning Philosophy

### Product versioning

Semantic versioning for the platform: `MAJOR.MINOR.PATCH`.

- **MAJOR:** Breaking domain model or API changes
- **MINOR:** New domains, capabilities, or features (backward compatible)
- **PATCH:** Bug fixes, performance improvements, prompt tuning

### TOON versioning

TOON follows independent semver (`TOON-v1`, `TOON-v2`). Breaking ontology changes require a new major version with migration projections. See [05_TOON_ARCHITECTURE.md](05_TOON_ARCHITECTURE.md).

### AI artifact versioning

| Artifact | ID pattern | Example |
|----------|-----------|---------|
| Capability | `{name}` in `capabilities/` | `resume_parsing` |
| Model | `hrms-{feature}-v{N}` | `hrms-parsing-v1` |
| Dataset | `DS-{FEATURE}-v{semver}` | `DS-PARSE-v1.0.0` |
| Benchmark | `BENCH-{FEATURE}-v{N}` | `BENCH-PARSE-v1` |
| Prompt | `PROMPT-{NNNN}` | `PROMPT-0001` |
| Deployment | `DEPLOY-{feature}-v{N}-{target}` | `DEPLOY-parsing-v1-ollama` |
| Evaluation | `EVAL-{FEATURE}-{run}` | `EVAL-PARSE-001` |

Full versioning strategy: `ai/docs/VERSIONING.md`.

### API versioning

Current API is unversioned (`/api/`). Breaking changes introduce `/api/v2/` with minimum 12-month overlap.

---

## Decision-Making Principles

### When to decide

| Decision type | Authority | Process |
|---------------|-----------|---------|
| Product vision change | Executive team | Amend ARCH-00; all downstream docs reviewed |
| New business domain | Product + Architecture | Add to ARCH-02; assess capability and data model impact |
| New AI capability | AI Architect + Product | Add to ARCH-03; create capability package; benchmark before deploy |
| Breaking API change | Principal Engineer + Product | ADR required; versioned endpoint; migration guide |
| Security model change | Security Architect | Amend ARCH-09; threat model review |
| Repository structure change | **Forbidden** | Requires constitutional amendment and executive approval |

### Decision framework

Every significant decision must answer:

1. **Which domain owns this?** → See [02_DOMAIN_MODEL.md](02_DOMAIN_MODEL.md)
2. **Which capability serves this?** → See [03_CAPABILITY_MAP.md](03_CAPABILITY_MAP.md)
3. **What entities are affected?** → See [06_DATA_MODEL.md](06_DATA_MODEL.md)
4. **What are the security implications?** → See [09_SECURITY_MODEL.md](09_SECURITY_MODEL.md)
5. **Does this scale for 10 years?** → See [10_NON_FUNCTIONAL_REQUIREMENTS.md](10_NON_FUNCTIONAL_REQUIREMENTS.md)
6. **Where does this sit in the roadmap?** → See [11_PRODUCT_ROADMAP.md](11_PRODUCT_ROADMAP.md)

### Conflict resolution

When principles conflict, resolve in this order:

1. **Security** (S-*) always wins over convenience
2. **Domain sovereignty** (P-01) wins over implementation speed
3. **Backward compatibility** (E-06) wins over clean design
4. **Longevity** (Vision) wins over velocity

---

## Amendment Process

This constitution may be amended by:

1. Proposed change documented with rationale and impact analysis
2. Review by architecture team (CTO, Principal Architect, Security Architect, AI Architect)
3. Update to affected ARCH documents (00–11) for consistency
4. ADR recorded if the change affects implementation patterns
5. Version increment on this document

---

## Cross-References

| Topic | Document |
|-------|----------|
| Vision and mission | [00_PRODUCT_VISION.md](00_PRODUCT_VISION.md) |
| Business domains | [02_DOMAIN_MODEL.md](02_DOMAIN_MODEL.md) |
| AI capabilities | [03_CAPABILITY_MAP.md](03_CAPABILITY_MAP.md) |
| AI platform | [04_AI_PLATFORM.md](04_AI_PLATFORM.md) |
| TOON ontology | [05_TOON_ARCHITECTURE.md](05_TOON_ARCHITECTURE.md) |
| Data model | [06_DATA_MODEL.md](06_DATA_MODEL.md) |
| System architecture | [07_SYSTEM_ARCHITECTURE.md](07_SYSTEM_ARCHITECTURE.md) |
| Security | [09_SECURITY_MODEL.md](09_SECURITY_MODEL.md) |
| NFRs | [10_NON_FUNCTIONAL_REQUIREMENTS.md](10_NON_FUNCTIONAL_REQUIREMENTS.md) |
| Roadmap | [11_PRODUCT_ROADMAP.md](11_PRODUCT_ROADMAP.md) |
