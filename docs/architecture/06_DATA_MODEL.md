# Conceptual Data Model

**Document ID:** ARCH-06  
**Status:** Constitutional — all database schemas and APIs derive from this model  
**Related:** [02_DOMAIN_MODEL.md](02_DOMAIN_MODEL.md) · [05_TOON_ARCHITECTURE.md](05_TOON_ARCHITECTURE.md) · [07_SYSTEM_ARCHITECTURE.md](07_SYSTEM_ARCHITECTURE.md)

---

## Purpose

This document describes the **conceptual data model** for the Human Capital Intelligence Platform. It defines actors, entities, relationships, lifecycle states, and ownership — without prescribing SQL, ORM mappings, or API payloads.

Implementation reference: `backend/schema_pg/` (PostgreSQL DDL).

---

## Model Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ACTOR LAYER                                      │
│  Guest · Candidate · HR · Head HR · Super Admin · (future: Employee,   │
│  Manager, Learner, Workforce Planner)                                    │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ acts upon
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         ENTITY LAYER                                     │
│                                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  │
│  │ Identity &  │  │ Recruitment │  │  Intelligence│  │ Platform &   │  │
│  │ Auth        │  │ & Hiring    │  │  Artifacts   │  │ Governance   │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └──────────────┘  │
│                                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                     │
│  │ Employee    │  │ Learning &  │  │Organization │  (Future domains)   │
│  │ Lifecycle   │  │ Performance │  │ & Analytics │                     │
│  └─────────────┘  └─────────────┘  └─────────────┘                     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Actors

### Current actors

| Actor | Identity entity | Authentication | Primary domains |
|-------|----------------|---------------|-----------------|
| **Guest** | None | None | Recruitment (read-only jobs) |
| **Candidate** | Candidate Account | OTP signup + JWT | Recruitment |
| **HR** | HR Account | Email/password + JWT | Recruitment, Hiring, Administration |
| **Head HR** | HR Account (elevated) | Email/password + JWT | All HR domains + Administration |
| **Super Admin** | HR Account (super) | Email/password + JWT | All domains |

### Future actors

| Actor | Identity entity | Primary domains |
|-------|----------------|-----------------|
| **Employee** | Employee Record | SSO/JWT | Employee, Learning, Performance |
| **Manager** | HR Account or Employee (delegated) | SSO/JWT | Performance, Organization, Team views |
| **Learner** | Employee Record | SSO/JWT | Learning |
| **Workforce Planner** | HR Account (specialized) | SSO/JWT | Organization, Analytics |

### Actor hierarchy

```
Super Admin
  └── Head HR
        └── HR / Recruiter
              └── (future) Manager
                    └── (future) Employee / Learner

Candidate (independent branch)
Guest (unauthenticated)
```

---

## Entity Catalog

### Identity & Authentication

| Entity | Description | Key attributes | Owner |
|--------|-------------|---------------|-------|
| **HR Account** | Recruiter/admin user | hrid, email, company, role flags | Administration |
| **Candidate Account** | Job seeker user | cid, email, phone | Administration |
| **Auth Staging** | OTP verification record | email, otp, expiry | Administration |
| **Session** | Active login session | token, device, IP, expiry | Administration |
| **Login History** | Authentication audit | actor, success, IP, timestamp | Administration |

### Recruitment & Hiring

| Entity | Description | Key attributes | Owner |
|--------|-------------|---------------|-------|
| **Job** | Open position | jdid, title, company, location, salary, status | Recruitment |
| **Candidate Profile** | Applicant information | name, contact, preferences, completion status | Recruitment |
| **Application** | Candidate–Job link | status, match_score, shortlist, ATS data | Recruitment |
| **Saved Job** | Candidate bookmark | candidate, job, saved_at | Recruitment |

### Profile detail entities (projections from TOON)

| Entity | Description | Key attributes | Owner |
|--------|-------------|---------------|-------|
| **Education Record** | Academic credential | degree, institution, year | Recruitment |
| **Experience Record** | Work history item | title, company, duration | Recruitment |
| **Certification Record** | Professional credential | name, issuer, date | Recruitment |

### Intelligence artifacts

| Entity | Description | Key attributes | Owner |
|--------|-------------|---------------|-------|
| **Raw File** | Uploaded document | uuid, filename, hash, mime, size | Recruitment |
| **Parsed Resume** | AI-structured resume | toon, confidence, model_version, full_text | Recruitment |
| **Parsed JD** | AI-structured job description | toon, confidence, model_version | Recruitment |
| **ATS Analysis** | Match result envelope | score, reasoning, breakdown | Recruitment |

### Platform & governance

| Entity | Description | Key attributes | Owner |
|--------|-------------|---------------|-------|
| **Support Request** | Contact form ticket | name, email, message, status | Administration |
| **Employee Feedback** | Internal testing feedback | category, description, screenshot | Administration |
| **System Settings** | Tenant configuration | key, value, scope | Administration |

### Future entities (designed, not implemented)

| Entity | Domain | Description |
|--------|--------|-------------|
| **Employee** | Employee | Core employment record |
| **Employment Record** | Employee | Job title, department, status |
| **Interview** | Hiring | Scheduled interview session |
| **Offer** | Hiring | Compensation package |
| **Onboarding Plan** | Employee | New hire task list |
| **Learning Program** | Learning | Training curriculum |
| **Course** | Learning | Individual learning unit |
| **Enrollment** | Learning | Employee–Course link |
| **Review Cycle** | Performance | Evaluation period |
| **Performance Review** | Performance | Structured evaluation |
| **Goal** | Performance | Measurable objective |
| **Department** | Organization | Functional unit |
| **Position** | Organization | Defined role |
| **Headcount Plan** | Organization | Workforce plan |

---

## Relationships

### Core relationship diagram

```
                    ┌──────────────┐
                    │  HR Account  │
                    └──────┬───────┘
                           │ creates
                           ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Candidate   │───►│     Job      │◄───│  Parsed JD   │
│   Account    │    │              │    └──────┬───────┘
└──────┬───────┘    └──────┬───────┘           │
       │                   │                   │
       │ has               │ receives          │ derived from
       ▼                   ▼                   │
┌──────────────┐    ┌──────────────┐    ┌──────┴───────┐
│  Candidate   │    │ Application  │    │   Raw File   │
│   Profile    │    │              │    └──────────────┘
└──────┬───────┘    └──────┬───────┘
       │                   │
       │ has               │ uses
       ▼                   ▼
┌──────────────┐    ┌──────────────┐
│  Parsed      │    │ ATS Analysis │
│  Resume      │    └──────────────┘
└──────┬───────┘
       │ derived from
       ▼
┌──────────────┐
│  Raw File    │
└──────────────┘
```

### Relationship matrix

| From | Relationship | To | Cardinality | Notes |
|------|-------------|-----|-------------|-------|
| Candidate Account | has | Candidate Profile | 1:1 | Created on first profile update |
| Candidate Profile | has | Raw File | 1:N | Resume uploads |
| Raw File | produces | Parsed Resume | 1:1 | Via AI parsing |
| Raw File | produces | Parsed JD | 1:1 | Via AI parsing |
| HR Account | creates | Job | 1:N | |
| Job | has | Parsed JD | 0:1 | Via JD upload + parsing |
| Candidate Account | applies to | Job | N:M | Via Application |
| Application | references | Parsed Resume | N:1 | Latest at time of apply |
| Application | references | Parsed JD | N:1 | JD at time of apply |
| Application | has | ATS Analysis | 0:1 | Generated async after apply |
| Candidate Profile | projects | Education Record | 1:N | From TOON or manual entry |
| Candidate Profile | projects | Experience Record | 1:N | From TOON or manual entry |
| Candidate Profile | projects | Certification Record | 1:N | From TOON or manual entry |
| HR Account | has | Session | 1:N | |
| HR Account | has | Login History | 1:N | |
| Candidate Account | has | Session | 1:N | |
| Candidate Account | has | Login History | 1:N | |

### Future relationship extensions

| From | Relationship | To | Trigger |
|------|-------------|-----|---------|
| Application (accepted) | triggers | Hire Record | Offer acceptance |
| Hire Record | creates | Employee | Confirmed hire |
| Employee | has | Employment Record | 1:N |
| Employee | assigned to | Department | Org assignment |
| Employee | enrolls in | Course | Via Enrollment |
| Employee | receives | Performance Review | 1:N per cycle |
| Performance Review | references | Goal | 1:N |

---

## Entity Lifecycle

### Candidate Account

```
[Guest] ──signup──► [Pending OTP] ──verify──► [Active] ──deactivate──► [Inactive]
                         │
                         └── expire ──► [Expired] ──resend──► [Pending OTP]
```

| State | Transitions | Actor |
|-------|------------|-------|
| Pending OTP | → Active (verify), → Expired (timeout) | Candidate |
| Active | → Inactive (admin action) | Candidate, Admin |
| Inactive | → Active (reactivation) | Admin |

### Job

```
[Draft] ──publish──► [Active/Enabled] ──disable──► [Disabled] ──enable──► [Active]
                         │
                         └── archive ──► [Archived]
```

| State | Visible to candidates | Applications accepted |
|-------|----------------------|----------------------|
| Draft | No | No |
| Active | Yes | Yes |
| Disabled | No | No |
| Archived | No | No (existing preserved) |

### Application

```
[Submitted] ──ATS──► [Scored] ──HR review──► [Shortlisted / Not Shortlisted]
                                                      │
                                              ┌───────┼───────┐
                                              ▼       ▼       ▼
                                         [Interview] [Rejected] [On Hold]
                                              │
                                              ▼
                                    (future: [Offer] → [Hired])
```

| State | Description | Set by |
|-------|-------------|--------|
| Submitted | Application created, ATS pending | System |
| Scored | ATS complete, match_score available | System (AI) |
| Shortlisted | HR marked or auto-shortlisted (score ≥ 75) | HR or System |
| Not Shortlisted | Score below threshold or HR decision | HR or System |
| Interview | Interview scheduled (future) | HR |
| Rejected | HR rejected candidate | HR |
| On Hold | Pipeline paused | HR |

### Parsed Resume / Parsed JD

```
[Upload] ──extract──► [Text Extracted] ──parse──► [Parsed] ──reparse──► [Parsed (new version)]
                                                          │
                                                          └── fail ──► [Parse Failed]
```

| State | Description | Stored |
|-------|-------------|--------|
| Text Extracted | Raw text available, AI pending | full_text |
| Parsed | TOON validated and stored | toon, confidence, model_version |
| Parse Failed | AI could not produce valid TOON | error logged; no toon stored |

Previous parsed versions are superseded, not deleted. Latest is authoritative.

### Raw File

```
[Uploaded] ──dedup check──► [Stored (new)] or [Stored (duplicate ref)]
                                │
                                └── delete ──► [Deleted] (future: soft delete)
```

Deduplication by content hash prevents redundant storage and re-parsing.

---

## Ownership Model

### Entity ownership by domain

| Domain | Owns | Reads (does not own) |
|--------|------|---------------------|
| **Administration** | HR Account, Candidate Account, Session, Login History, Support Request, Employee Feedback, System Settings | All (for management) |
| **Recruitment** | Job, Candidate Profile, Application, Saved Job, Raw File, Parsed Resume, Parsed JD, ATS Analysis, profile detail entities | HR Account (for auth) |
| **Hiring** (future) | Interview, Offer, Hire Record | Application, Parsed Resume, Parsed JD |
| **Employee** (future) | Employee, Employment Record, Onboarding Plan, Lifecycle Event | Candidate Account (historical link) |
| **AI** | Capability, Provider, Model, Dataset, Benchmark, Inference Record | TOON documents (format only) |
| **Analytics** (future) | Metric, Dashboard, Report, Insight | All domain entities (read-only) |

### Ownership rules

1. **Write authority:** Only the owning domain may create, update, or delete its entities.
2. **Read authority:** Any domain may read entities from other domains via explicit reference (ID lookup).
3. **AI enrichment:** AI domain produces artifacts (TOON); owning domain persists them.
4. **Projections:** Derived entities (Education Record from TOON) are owned by the same domain as the source entity.
5. **Audit:** Administration domain logs all mutations regardless of owning domain.

---

## Data Classification

| Classification | Examples | Handling |
|---------------|----------|----------|
| **Public** | Job listings, company name | No auth required |
| **Internal** | Application status, match scores | Authenticated access, role-scoped |
| **Confidential** | Resume content, salary, personal contact | Owner + authorized HR only |
| **Restricted** | Auth tokens, API keys, audit logs | System access only; never exposed to UI |
| **PII** | Name, email, phone, address | Encrypted at rest (future); masked in logs; GDPR subject to erasure |

Full security model: [09_SECURITY_MODEL.md](09_SECURITY_MODEL.md).

---

## Multi-Tenancy Model (Future)

Current implementation is single-tenant (company field on HR Account). Enterprise multi-tenancy design:

| Aspect | Design |
|--------|--------|
| **Tenant entity** | Organization (top-level) |
| **Isolation** | Row-level security by tenant_id on all entities |
| **Data residency** | Tenant-configurable region (future) |
| **Shared resources** | Knowledge packs (read-only), AI models (shared inference) |
| **Tenant-specific** | All business entities, configurations, audit logs |
| **Cross-tenant** | Architecturally impossible (enforced at query layer) |

---

## Cross-References

| Topic | Document |
|-------|----------|
| Domain definitions | [02_DOMAIN_MODEL.md](02_DOMAIN_MODEL.md) |
| TOON format | [05_TOON_ARCHITECTURE.md](05_TOON_ARCHITECTURE.md) |
| System components | [07_SYSTEM_ARCHITECTURE.md](07_SYSTEM_ARCHITECTURE.md) |
| Workflow sequences | [08_DATA_FLOWS.md](08_DATA_FLOWS.md) |
| Security & PII | [09_SECURITY_MODEL.md](09_SECURITY_MODEL.md) |
| PostgreSQL DDL | `backend/schema_pg/` |
