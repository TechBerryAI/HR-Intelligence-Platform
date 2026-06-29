# Non-Functional Requirements

**Document ID:** ARCH-10  
**Status:** Constitutional — all engineering decisions must meet these requirements  
**Related:** [01_PRODUCT_CONSTITUTION.md](01_PRODUCT_CONSTITUTION.md) · [07_SYSTEM_ARCHITECTURE.md](07_SYSTEM_ARCHITECTURE.md) · [09_SECURITY_MODEL.md](09_SECURITY_MODEL.md)

---

## Purpose

This document defines the **non-functional requirements (NFRs)** for the Human Capital Intelligence Platform. These requirements apply to all components — frontend, backend, AI runtime, and infrastructure — and must be validated before enterprise deployment.

NFRs are organized by category with current-state baseline and enterprise target.

---

## NFR Summary Matrix

| Category | Current (MVP) | Enterprise Target | Measurement |
|----------|--------------|-------------------|-------------|
| Performance | Best effort | Defined SLAs | Load testing |
| Availability | Single instance | 99.9% uptime | Uptime monitoring |
| Scalability | Vertical | Horizontal | Stress testing |
| Latency | Unmeasured | Defined P95/P99 | APM |
| Reliability | Manual recovery | Automated failover | Error rate tracking |
| Explainability | ATS reasoning | All AI outputs | Feature audit |
| Observability | Application logs | Full stack tracing | Monitoring platform |
| Accessibility | Partial | WCAG 2.1 AA | Automated + manual audit |
| Maintainability | Monolith | Modular monolith | Code metrics |
| Disaster recovery | Manual backup | RPO/RTO defined | DR drill |
| Backup | Manual | Automated + tested restore | Restore test |
| Versioning | Ad hoc | Semver + registry | Release process |

---

## Performance

### Response time targets

| Operation | Current | Enterprise P95 | Enterprise P99 |
|-----------|---------|-----------------|----------------|
| Page load (frontend) | < 3s | < 2s | < 4s |
| API read (simple) | < 500ms | < 200ms | < 500ms |
| API write (simple) | < 1s | < 500ms | < 1s |
| Single resume parse | < 30s | < 15s | < 30s |
| JD parse | < 30s | < 15s | < 30s |
| ATS matching (async) | < 60s | < 30s | < 60s |
| Bulk parse (per file) | < 30s | < 15s | < 30s |
| HR chat response | < 15s | < 10s | < 15s |
| Job search | < 1s | < 500ms | < 1s |
| Login/auth | < 2s | < 1s | < 2s |

### Throughput targets

| Operation | Enterprise target |
|-----------|-------------------|
| Concurrent users | 1,000 per tenant |
| API requests | 500 req/s (platform-wide) |
| Bulk resume parsing | 500 resumes/hour |
| AI inferences | 100 concurrent |
| Database connections | 100 pooled per backend instance |

### Performance design principles

| Principle | Implementation |
|-----------|---------------|
| **Pagination** | All list endpoints paginated (default 20, max 100) |
| **Lazy loading** | Frontend loads data on demand, not upfront |
| **Async AI** | Non-interactive AI runs in background threads/queue |
| **Connection pooling** | PostgreSQL pool (psycopg3) mandatory |
| **Caching** (future) | Redis for session, frequent reads, AI result cache |
| **CDN** (future) | Static assets served from CDN |
| **Index coverage** | All query patterns covered by database indexes |

---

## Availability

### Uptime targets

| Tier | Target | Downtime/month | Applies to |
|------|--------|---------------|------------|
| **Platform** | 99.9% | ≤ 43 minutes | Backend + Frontend + Database |
| **AI Runtime** | 99.5% | ≤ 3.6 hours | AI capabilities (graceful degradation) |
| **LLM Providers** | Provider SLA | N/A | External; fallback required |

### High availability design

| Component | Current | Enterprise |
|-----------|---------|------------|
| Backend | Single instance | N replicas behind load balancer |
| Frontend | Vite dev server | Static CDN + SSR fallback |
| Database | Single PostgreSQL | Primary + read replica |
| AI Runtime | Single process | N instances with health checks |
| LLM Providers | Primary + fallback | Multi-provider with automatic failover |

### Graceful degradation

| Failure | Platform behavior |
|---------|-------------------|
| AI runtime down | Applications created without scores; parsing queued |
| LLM provider down | Fallback provider; if all fail, explicit error |
| Database replica lag | Reads from primary; alert on lag > 5s |
| Email service down | OTP queued for retry; login unaffected for existing users |
| Bulk parser API down | Automatic local fallback |

---

## Scalability

### Scaling dimensions

| Dimension | Strategy | Trigger |
|-----------|----------|---------|
| **Users** | Horizontal backend replicas | CPU > 70% sustained |
| **Data volume** | Database partitioning + archival | Table > 10M rows |
| **AI inference** | Independent AI runtime scaling | Queue depth > 100 |
| **File storage** | Object storage (S3) migration | Storage > 100GB |
| **Tenants** | Row-level security + tenant middleware | Multi-tenant launch |

### Scalability limits (design targets)

| Resource | Single tenant | Platform-wide |
|----------|--------------|---------------|
| Candidates | 100,000 | 10,000,000 |
| Jobs (active) | 10,000 | 1,000,000 |
| Applications | 1,000,000 | 100,000,000 |
| Parsed resumes | 500,000 | 50,000,000 |
| Raw files | 500,000 | 50,000,000 |
| Concurrent bulk jobs | 5 | 50 |

### Scaling principles

| Principle | Rule |
|-----------|------|
| **Stateless backend** | No server-side session state; JWT-only auth |
| **Independent AI scaling** | AI runtime scales without backend scaling |
| **Database read scaling** | Read replicas for analytics and search |
| **Async by default** | Heavy operations (AI, bulk, export) are async |
| **Tenant isolation scaling** | Dedicated resources for enterprise tenants (optional) |

---

## Latency

### Latency budget (enterprise)

```
User action → Frontend render:     200ms
Frontend → Backend API:            50ms (network)
Backend auth + validation:         50ms
Backend business logic + DB:       100ms
Backend → AI runtime (if sync):    10,000ms (15s target)
AI runtime → Provider:             8,000ms
Provider inference:                7,000ms
Response serialization:            50ms
Backend → Frontend:                50ms
Frontend render update:            200ms
─────────────────────────────────────────
Total (non-AI request):            ~650ms
Total (AI request):                ~15,650ms
```

### Latency monitoring

| Metric | Alert threshold |
|--------|----------------|
| API P95 latency | > 2x target |
| API P99 latency | > 3x target |
| AI inference P95 | > 20s |
| Database query P95 | > 500ms |
| Frontend LCP | > 2.5s |

---

## Reliability

### Error rate targets

| Component | Target error rate |
|-----------|------------------|
| API endpoints | < 0.1% (5xx) |
| AI inference | < 1% (validation failure + provider failure) |
| Authentication | < 0.01% (false rejection) |
| Data persistence | < 0.001% (write failure) |
| Email delivery | < 1% (OTP delivery) |

### Reliability patterns

| Pattern | Implementation |
|---------|---------------|
| **Retry with backoff** | API client retries 5xx (frontend); provider retry (backend/AI) |
| **Circuit breaker** (future) | Provider circuit breaker after 5 consecutive failures |
| **Idempotency** | Application creation, file upload dedup by hash |
| **Transaction safety** | Critical mutations in database transactions |
| **Health checks** | `/health` endpoint on backend; provider health in AI runtime |
| **Dead letter queue** (future) | Failed async jobs queued for retry/investigation |

### Data integrity

| Requirement | Implementation |
|-------------|---------------|
| **No silent data loss** | Failed writes return error; never partial success without notification |
| **TOON validation gate** | Invalid TOON never persisted |
| **Deduplication** | Raw file hash prevents duplicate storage |
| **Audit trail** | All mutations logged (see [09_SECURITY_MODEL.md](09_SECURITY_MODEL.md)) |
| **Backup verification** | Regular restore tests (see Backup section) |

---

## Explainability

### Requirements

| AI output | Explainability requirement |
|-----------|---------------------------|
| **Match score** | Score breakdown by dimension (skills, experience, education, location) |
| **Shortlist decision** | Threshold applied + score + reasoning text |
| **Parse confidence** | Confidence score displayed; fields below threshold flagged |
| **Interview questions** | Category and evaluation criteria per question |
| **HR chat** | Source attribution when referencing platform data (future) |
| **All AI outputs** | Capability ID, model version accessible to authorized users |

### Explainability implementation

| Feature | Status | Location |
|---------|--------|----------|
| ATS score breakdown | Active | `applications.ats_analysis` |
| ATS reasoning text | Active | `applications.ats_reasoning` |
| Parse confidence | Active | `parsed_resumes.confidence` |
| Model version tracking | Active | `parsed_resumes.model_version` |
| Capability version | Planned | Inference record |
| Prompt version | Planned | Inference record |

### Anti-patterns (forbidden)

- Black-box scores with no reasoning
- AI decisions with no human override path
- Confidence scores that are always 100%
- Hidden model or prompt versions

---

## Observability

### Current state

Application-level logging in backend (Flask). No centralized monitoring.

### Target observability stack

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   Metrics   │  │    Logs     │  │   Traces    │  │   Alerts    │
│ (Prometheus)│  │(structured) │  │  (OpenTel)  │  │ (PagerDuty) │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       └────────────────┴────────────────┴────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │    Dashboard      │
                    │   (Grafana)       │
                    └───────────────────┘
```

### Metrics to collect

| Category | Metrics |
|----------|---------|
| **API** | Request count, latency (P50/P95/P99), error rate by endpoint |
| **AI** | Inference count, latency, validation pass rate, provider distribution, fallback rate |
| **Database** | Query count, latency, connection pool utilization, replication lag |
| **Auth** | Login success/failure rate, token refresh rate, active sessions |
| **Business** | Applications/day, parse success rate, bulk job throughput |

### Logging standards

| Rule | Requirement |
|------|------------|
| **Structured JSON** | All logs in JSON format with standard fields |
| **Correlation ID** | Every request gets a trace ID propagated across services |
| **No PII** | Never log names, emails, phones, resume content |
| **Log levels** | ERROR (action needed), WARN (investigate), INFO (business events), DEBUG (dev only) |
| **Retention** | 30 days hot; 1 year cold archive |

### Alerting

| Alert | Condition | Severity |
|-------|-----------|----------|
| API error spike | 5xx > 1% for 5 min | Critical |
| AI inference failure | Error > 5% for 10 min | High |
| Database connection exhaustion | Pool > 90% for 5 min | Critical |
| Latency degradation | P95 > 2x target for 10 min | High |
| Disk space | > 85% utilization | High |
| Auth failure spike | Failed logins > 10x baseline | Medium |

---

## Accessibility

### Standard

**WCAG 2.1 Level AA** compliance for all user-facing surfaces.

### Requirements

| Criterion | Requirement |
|-----------|------------|
| **Perceivable** | Text alternatives for images; color contrast ≥ 4.5:1; resizable text |
| **Operable** | Keyboard navigation for all interactions; no seizure-inducing content |
| **Understandable** | Consistent navigation; input error identification; readable language |
| **Robust** | Valid HTML; compatible with assistive technologies |

### Implementation

| Aspect | Approach |
|--------|----------|
| **Component library** | Radix UI (accessible primitives) |
| **Focus management** | Visible focus indicators; logical tab order |
| **Screen reader** | ARIA labels on interactive elements |
| **Forms** | Label association; error messages linked to fields |
| **Modals** | Focus trap; escape to close |
| **Testing** | axe-core automated checks in CI; manual audit quarterly |

---

## Maintainability

### Code quality targets

| Metric | Target |
|--------|--------|
| Test coverage (AI capabilities) | ≥ 80% |
| Test coverage (backend critical paths) | ≥ 70% |
| Documentation coverage | All public APIs documented |
| ADR coverage | All significant decisions recorded |
| Dependency freshness | No critical CVEs; major deps updated within 6 months |

### Architecture maintainability

| Principle | Implementation |
|-----------|---------------|
| **Modular monolith** | Backend blueprints isolate domains; AI capabilities are independent packages |
| **Convention over configuration** | Standard patterns for routes, services, capabilities |
| **Colocated tests** | Tests live with their module |
| **Schema migrations** | Versioned SQL files; never modify deployed schema in place |
| **Feature flags** | New features deployable without activation |
| **Documentation hierarchy** | Product Design System > ADRs > Technical docs > Code |

### Technical debt management

| Practice | Frequency |
|----------|-----------|
| Architecture review | Quarterly |
| Dependency audit | Monthly |
| Performance baseline | Per release |
| Security scan | Per commit (CI) + quarterly deep scan |
| Documentation review | Per milestone |

---

## Disaster Recovery

### Recovery objectives

| Metric | Target | Definition |
|--------|--------|------------|
| **RPO** (Recovery Point Objective) | ≤ 1 hour | Maximum data loss in disaster |
| **RTO** (Recovery Time Objective) | ≤ 4 hours | Maximum downtime in disaster |

### Disaster scenarios

| Scenario | Impact | Recovery procedure |
|----------|--------|-------------------|
| **Database failure** | Full outage | Failover to replica; restore from backup if needed |
| **Backend failure** | API unavailable | Load balancer routes to healthy replicas |
| **AI runtime failure** | AI features degraded | Graceful degradation; restart/redeploy |
| **LLM provider outage** | Parsing/matching degraded | Automatic fallback provider |
| **Region outage** | Full platform outage | Failover to DR region (future) |
| **Data corruption** | Partial data loss | Point-in-time recovery from backup |

### DR testing

| Test | Frequency | Success criteria |
|------|-----------|-----------------|
| Backup restore | Monthly | Data integrity verified |
| Failover drill | Quarterly | RTO met; no data loss beyond RPO |
| Full DR simulation | Annually | Platform operational in DR region |

---

## Backup

### Backup strategy

| Data | Method | Frequency | Retention |
|------|--------|-----------|-----------|
| **PostgreSQL** | Automated snapshot + WAL | Continuous WAL; daily snapshot | 30 days snapshots; 7 days WAL |
| **Raw files** | Object storage replication | On upload | Tenant-configurable |
| **AI registry** | Git (YAML committed) | Every commit | Permanent (git history) |
| **AI model weights** | Object storage | On deployment | All versions |
| **Configuration** | Git + secrets manager | Every change | Permanent |
| **Audit logs** | Database + archive | Continuous | 7 years |

### Backup verification

| Check | Frequency |
|-------|-----------|
| Restore test (database) | Monthly |
| Checksum verification | Weekly |
| Cross-region replication lag | Continuous monitoring |

---

## Versioning

### Versioning requirements

| Artifact | Version scheme | Change control |
|----------|---------------|----------------|
| **Platform** | Semver (MAJOR.MINOR.PATCH) | Release notes; migration guide for MAJOR |
| **API** | URL versioning (/api/v2/) | 12-month overlap for breaking changes |
| **TOON** | TOON-vN (independent semver) | Projection layer for migration |
| **AI capabilities** | Per capability.yaml semver | Benchmark gate on changes |
| **AI models** | hrms-{feature}-vN | Evaluation gate on deployment |
| **Database schema** | Sequential SQL files | Forward-only migrations |
| **Prompts** | PROMPT-NNNN registry | Evaluation gate on changes |

Full versioning philosophy: [01_PRODUCT_CONSTITUTION.md](01_PRODUCT_CONSTITUTION.md) § Versioning Philosophy.

---

## Cross-References

| Topic | Document |
|-------|----------|
| Principles | [01_PRODUCT_CONSTITUTION.md](01_PRODUCT_CONSTITUTION.md) |
| Success metrics | [00_PRODUCT_VISION.md](00_PRODUCT_VISION.md) |
| System architecture | [07_SYSTEM_ARCHITECTURE.md](07_SYSTEM_ARCHITECTURE.md) |
| Security | [09_SECURITY_MODEL.md](09_SECURITY_MODEL.md) |
| AI platform reliability | [04_AI_PLATFORM.md](04_AI_PLATFORM.md) |
| Roadmap milestones | [11_PRODUCT_ROADMAP.md](11_PRODUCT_ROADMAP.md) |
