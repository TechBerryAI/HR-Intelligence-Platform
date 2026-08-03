# Roadmap

## Contents

- [Product Roadmap](#product-roadmap)


---

## Product Roadmap

**Document ID:** HCIP-RM-001  
**Related:** [../01-Product-Constitution/Product-Constitution.md](01-Product-Constitution.md)

---

### Guiding rule

Ship phases **on top of** the existing recruitment foundation. Do not rewrite apply, auth, or parse contracts without versioned migration.

---

### Phases

```mermaid
gantt
  title HCIP Evolution (indicative)
  dateFormat  YYYY-Q
  section Foundation
  Phase1 Constitution           :done, 2026-Q3, 2026-Q3
  Phase2 Domain Model           :done, 2026-Q3, 2026-Q3
  section Intelligence
  Phase3 Ontology               :2026-Q4, 2027-Q1
  Phase4 Knowledge Repository   :2027-Q1, 2027-Q2
  Phase5 Parsing Intelligence   :2027-Q1, 2027-Q3
  Phase6 Matching Engine        :2027-Q2, 2027-Q4
  section Workforce
  Phase7 Interview Intelligence :2027-Q3, 2028-Q1
  Phase8 Employee Lifecycle     :2027-Q4, 2028-Q2
  Phase9 Analytics              :2028-Q1, 2028-Q3
  Phase10 HR Copilot            :2028-Q2, 2028-Q4
```

| Phase | Name | Outcome |
|-------|------|---------|
| **1** | Product Constitution | This documentation set; decision SoT |
| **2** | Domain Model | Shared language for org/recruitment/employee/intelligence |
| **3** | Ontology | Canonical Person/Job/Skill model |
| **4** | Knowledge Repository | Curated skills, titles, institutions, … |
| **5** | Parsing Intelligence | Ontology-aware parsers + eval harness |
| **6** | Matching Engine | Embeddings, rerank, fairness monitors |
| **7** | Interview Intelligence | Production interview APIs & UX |
| **8** | Employee Lifecycle | Onboarding, goals, performance, learning |
| **9** | Analytics | Executive workforce intelligence |
| **10** | HR Copilot | Grounded assistant over knowledge + org data |

---

### Already strong (do not regress)

- Public apply + parse + ATS
- Recruiter / Head HR / CEO portals
- Bulk resume parsing
- JWT staff auth

---

### Exit criteria examples

| Phase | Exit criterion |
|-------|----------------|
| 5 | Golden-set CI for resume/JD parse |
| 6 | Match v2 with documented weights + vector assist |
| 7 | Interview blueprint registered + audit trail |
| 10 | Copilot answers with citations; policy refusals tested |
