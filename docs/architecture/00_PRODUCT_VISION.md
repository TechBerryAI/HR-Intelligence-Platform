# Product Vision

**Document ID:** ARCH-00  
**Status:** Constitutional — all future decisions derive from this document  
**Audience:** Executive leadership, product, engineering, AI, security, and enterprise customers  
**Related:** [01_PRODUCT_CONSTITUTION.md](01_PRODUCT_CONSTITUTION.md) · [11_PRODUCT_ROADMAP.md](11_PRODUCT_ROADMAP.md)

---

## Mission

Transform how organizations understand, acquire, develop, and retain human capital by delivering an **AI-native Human Capital Intelligence Platform** that turns unstructured workforce data into actionable intelligence across the complete employee lifecycle.

We exist to give HR leaders, recruiters, managers, and employees a single source of truth for human capital decisions — powered by governed AI, not bolted-on automation.

---

## Vision

By 2035, the Human Capital Intelligence Platform (HCIP) will be the operating system for workforce intelligence at Fortune 500 enterprises: from first candidate touchpoint through retirement, with AI capabilities that are explainable, auditable, and continuously improving.

Today the platform delivers **Recruitment Intelligence**. Tomorrow it delivers **Workforce Intelligence**.

---

## Product Philosophy

### AI-native, not AI-augmented

AI is not a feature layer on top of a traditional ATS. Intelligence is embedded in every workflow — parsing, matching, interviewing, onboarding, learning, performance, and planning. The platform is designed so that new AI capabilities plug into a governed runtime without rewriting business logic.

### Intelligence over automation

Automation executes tasks. Intelligence informs decisions. Every AI output must be traceable to inputs, models, and reasoning. HR professionals remain accountable; the platform makes them faster and better informed.

### Domain-first, technology-second

Business domains (Recruitment, Employee, Learning, Performance, Organization) own their entities and lifecycle rules. Technology serves domain boundaries — it does not define them.

### Progressive disclosure of complexity

Candidates see simplicity. HR sees depth. Administrators see governance. Enterprise architects see extensibility. The same platform scales from a 50-person startup to a 500,000-person global enterprise without architectural rewrites.

### Longevity over velocity

We optimize for clarity, maintainability, and extensibility over the next sprint. Every design decision must remain valid in ten years. See [01_PRODUCT_CONSTITUTION.md](01_PRODUCT_CONSTITUTION.md).

---

## Core Principles

| # | Principle | Meaning |
|---|-----------|---------|
| 1 | **Single platform, many domains** | One product surface; domains compose, never duplicate |
| 2 | **TOON as the intelligence wire format** | Structured human-capital data flows through TOON across all AI capabilities |
| 3 | **Capability isolation** | Each AI capability is independently versioned, evaluated, and deployable |
| 4 | **Governed AI** | Models, prompts, datasets, and deployments are registered, versioned, and auditable |
| 5 | **Tenant sovereignty** | Enterprise data is isolated, portable, and never commingled across tenants |
| 6 | **Human-in-the-loop by default** | AI recommends; humans decide — unless explicitly configured otherwise |
| 7 | **Explainability is non-negotiable** | Every score, match, and recommendation carries reasoning accessible to authorized users |
| 8 | **Open integration, closed core** | Standard APIs and event contracts; proprietary intelligence layer |

---

## Target Customers

### Primary (Current — Recruitment Intelligence)

| Segment | Profile | Primary need |
|---------|---------|--------------|
| **Mid-market enterprises** | 500–5,000 employees; dedicated HR/recruiting teams | Reduce time-to-hire; improve match quality; bulk resume processing |
| **Staffing and RPO firms** | High-volume candidate processing | Bulk parsing, ranking, and pipeline intelligence |
| **Enterprise HR departments** | 5,000+ employees; compliance requirements | Governed AI, audit trails, integration readiness |

### Secondary (Future — Workforce Intelligence)

| Segment | Profile | Primary need |
|---------|---------|--------------|
| **Global enterprises** | Multi-country, multi-entity | Organization intelligence, workforce planning, succession |
| **Learning & development teams** | L&D budget owners | Skill intelligence, learning paths, competency mapping |
| **People analytics teams** | Data-driven HR | Cross-domain analytics, organization graph, predictive workforce planning |

### Buyer personas

- **Chief Human Resources Officer (CHRO)** — platform ROI, compliance, workforce strategy
- **VP Talent Acquisition** — recruitment velocity and quality
- **Head of People Analytics** — data integrity and cross-domain insights
- **IT / Enterprise Architecture** — security, integration, tenant isolation
- **AI / Data Governance** — model governance, explainability, audit

---

## Target Industries

| Industry | Recruitment focus | Future workforce focus |
|----------|--------------------|--------------------------|
| **Technology & SaaS** | High-volume technical hiring; skill matching | Skill intelligence; internal mobility |
| **Financial services** | Compliance-aware hiring; credential verification | Performance; succession planning |
| **Healthcare** | Credential and certification matching | Learning compliance; shift planning |
| **Manufacturing** | Blue-collar and skilled trade hiring | Workforce planning; safety training |
| **Professional services** | Consultant and specialist matching | Utilization; career intelligence |
| **Retail & hospitality** | High-volume seasonal hiring | Attendance; leave management |

Industry-specific knowledge packs (see [03_CAPABILITY_MAP.md](03_CAPABILITY_MAP.md)) extend base platform intelligence without forking the core product.

---

## Competitive Positioning

### What we are

An **AI-native Human Capital Intelligence Platform** that unifies recruitment intelligence today and workforce intelligence tomorrow — with a governed AI runtime, structured ontology (TOON), and enterprise-grade security.

### What we are not

| Category | Distinction |
|----------|-------------|
| **Traditional ATS** (Greenhouse, Lever, iCIMS) | We provide intelligence, not just workflow tracking |
| **HRMS** (Workday, SAP SuccessFactors) | We are intelligence-first; HRMS modules integrate with us |
| **Point AI tools** (resume parsers, chatbots) | We provide a governed capability platform, not isolated tools |
| **Generic LLM wrappers** | Every capability has schemas, benchmarks, and lineage |

### Positioning statement

> For enterprise HR and talent acquisition leaders who need to make faster, better-informed human capital decisions, HCIP is the AI-native intelligence platform that transforms unstructured workforce data into governed, explainable intelligence — unlike traditional ATS or bolt-on AI tools that lack ontology, governance, and lifecycle breadth.

---

## Long-Term Vision

### Phase 1 — Recruitment Intelligence (Current)

Recruitment, resume intelligence, job intelligence, candidate matching, bulk parsing, interview intelligence, offer intelligence, HR copilot for recruiting workflows.

**Status:** Production foundation deployed. AI platform runtime implemented (M7). HRMS integration planned (M9).

### Phase 2 — Employee Lifecycle Intelligence

Employee onboarding, learning intelligence, performance intelligence, career intelligence, internal mobility, succession planning.

### Phase 3 — Organization Intelligence

Organization graph, workforce planning, skill intelligence, analytics dashboards, predictive modeling.

### Phase 4 — Full Workforce Platform

Payroll intelligence, attendance, leave management, compensation intelligence, AI agents for autonomous HR workflows (always governed, always auditable).

### Platform evolution model

```
Recruitment Intelligence  →  Employee Intelligence  →  Organization Intelligence  →  Workforce Platform
        (Now)                      (Year 2–3)                (Year 3–5)                  (Year 5–10)
```

Each phase adds **domains** and **capabilities** — never replaces the foundation. See [02_DOMAIN_MODEL.md](02_DOMAIN_MODEL.md) and [11_PRODUCT_ROADMAP.md](11_PRODUCT_ROADMAP.md).

---

## AI Philosophy

### Intelligence as a service, not a model

We operate AI **capabilities** with measurable SLAs — not fine-tuned models in isolation. Every capability has defined inputs, outputs, schemas, benchmarks, and deployment lineage. See [04_AI_PLATFORM.md](04_AI_PLATFORM.md).

### Ontology before inference

Structured understanding (TOON) precedes reasoning. Raw LLM output is never stored as truth — it is validated, normalized, and projected into the ontology before persistence. See [05_TOON_ARCHITECTURE.md](05_TOON_ARCHITECTURE.md).

### Continuous improvement loop

Production corrections feed the dataset pipeline. Datasets feed training. Training feeds evaluation. Evaluation gates deployment. Deployment feeds production. See [04_AI_PLATFORM.md](04_AI_PLATFORM.md) § Model Lifecycle.

### Provider agnosticism

The platform routes inference through a provider abstraction (Ollama, Grok, OpenAI, Anthropic, future providers) with fallback, retry, and cost governance. Business logic never depends on a single provider.

### Safety and governance first

Prompt injection defense, PII handling, model versioning, and audit logging are architectural requirements — not afterthoughts. See [09_SECURITY_MODEL.md](09_SECURITY_MODEL.md).

---

## Success Metrics

### Product metrics

| Metric | Definition | Target (Enterprise) |
|--------|------------|----------------------|
| **Time-to-parse** | Median latency from upload to structured TOON | < 15s (single resume) |
| **Parse accuracy** | Field-level F1 against benchmark (BENCH-PARSE) | ≥ 95% |
| **Match precision@shortlist** | % of shortlisted candidates passing HR review | ≥ 80% |
| **Bulk throughput** | Resumes processed per hour | ≥ 500/hr |
| **Application completion rate** | Candidates who complete profile and apply | ≥ 70% |
| **HR adoption rate** | Active HR users / licensed seats | ≥ 85% |

### Platform metrics

| Metric | Definition | Target |
|--------|------------|--------|
| **Capability uptime** | AI runtime availability | 99.9% |
| **Eval regression pass rate** | Benchmarks passing before deployment | 100% |
| **Model lineage coverage** | Production inferences traceable to registry ID | 100% |
| **Tenant isolation incidents** | Cross-tenant data exposure | 0 |

### Business metrics

| Metric | Definition | Target (Year 3) |
|--------|------------|-------------------|
| **Time-to-hire reduction** | vs. customer baseline | 30% |
| **Cost-per-hire reduction** | vs. customer baseline | 25% |
| **Enterprise NRR** | Net revenue retention | ≥ 120% |
| **Platform NPS** | HR leader satisfaction | ≥ 50 |

### AI maturity metrics

Aligned with platform maturity model in [04_AI_PLATFORM.md](04_AI_PLATFORM.md) and [11_PRODUCT_ROADMAP.md](11_PRODUCT_ROADMAP.md):

| Level | Milestone | Criteria |
|-------|-----------|----------|
| L1 | Foundation | Architecture documented, contracts defined |
| L2 | Data | Pipeline operational, artifacts traced |
| L3 | Model | Model trained, benchmark passed |
| L4 | Deploy | Ollama/local artifact production-ready |
| L5 | Gateway | Inference platform operational |
| L6 | Integration | HRMS integrated with feature flag |
| L7 | Multi-feature | Second+ capability on platform |
| L8 | Continuous | Monitoring and improvement loop closed |

---

## Document Authority

This document is the **highest authority** in the Product Design System. When conflicts arise:

1. **00_PRODUCT_VISION.md** (this document) — mission, vision, philosophy
2. **01_PRODUCT_CONSTITUTION.md** — principles and governance rules
3. **02–10** — domain, capability, architecture, security, and NFR specifications
4. **11_PRODUCT_ROADMAP.md** — sequencing and milestones
5. Implementation code and existing technical docs — must conform to 00–11

---

## Cross-References

| Topic | Document |
|-------|----------|
| Principles and governance | [01_PRODUCT_CONSTITUTION.md](01_PRODUCT_CONSTITUTION.md) |
| Business domains | [02_DOMAIN_MODEL.md](02_DOMAIN_MODEL.md) |
| AI capabilities | [03_CAPABILITY_MAP.md](03_CAPABILITY_MAP.md) |
| AI platform architecture | [04_AI_PLATFORM.md](04_AI_PLATFORM.md) |
| TOON ontology | [05_TOON_ARCHITECTURE.md](05_TOON_ARCHITECTURE.md) |
| Conceptual data model | [06_DATA_MODEL.md](06_DATA_MODEL.md) |
| System architecture | [07_SYSTEM_ARCHITECTURE.md](07_SYSTEM_ARCHITECTURE.md) |
| Workflow sequences | [08_DATA_FLOWS.md](08_DATA_FLOWS.md) |
| Security model | [09_SECURITY_MODEL.md](09_SECURITY_MODEL.md) |
| Non-functional requirements | [10_NON_FUNCTIONAL_REQUIREMENTS.md](10_NON_FUNCTIONAL_REQUIREMENTS.md) |
| Roadmap and milestones | [11_PRODUCT_ROADMAP.md](11_PRODUCT_ROADMAP.md) |
