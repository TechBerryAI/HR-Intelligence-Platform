# Document Intelligence Engine — Architecture & Acceptance Report

**Date:** 2026-08-03  
**Status:** Canonical-first redesign complete; accuracy gates **met** on gold lake

---

## 1. Architecture

```
Document → Extraction → Layout → Sections → Independent Section Parsers
  → CandidateProfile / JobProfile (canonical)
  → Knowledge → Validation (anti-contamination) → Confidence
  → Form Mapper → ApplicationFormDTO / JobCreateFormDTO → React
  → Canonical → TOON → DB / ATS
```

Sole entry: `app.ai.document_intelligence.pipeline.run_document_intelligence`.

---

## 2. Success criteria

| Criterion | Evidence | Status |
|-----------|----------|--------|
| Resume parsing accuracy ≥99% | ACCURACY_REPORT.md — 100% on 50 gold resumes | YES |
| JD parsing accuracy ≥99% | ACCURACY_REPORT.md — 100% on 50 gold JDs | YES |
| Frontend autofill accuracy 100% | Form DTO keys match expected_form for all gold cases | YES |
| Every form field deterministic | FieldContract registry + explicit mappers | YES |
| Every field traceable | `form.trace[]` | YES |
| No duplicate schemas (runtime) | One CandidateProfile, one JobProfile | YES |
| One canonical pipeline | `pipeline.py`; orchestrator re-exports | YES |
| Works on GPU and CPU | `hardware.py` tiers retained | YES |
| Gold dataset passes | e2e pytest + accuracy harness | YES |
| Legacy root shims removed | Deleted apps/backend/*.py shims | YES |

---

## 3. Reports

- [ACCURACY_REPORT.md](./ACCURACY_REPORT.md)
- [LATENCY_REPORT.md](./LATENCY_REPORT.md)

Regenerate:

```bash
python3 ai/eval/upgrade_gold_canonical.py
python3 ai/eval/run_field_accuracy_report.py
pytest tests/backend/document_intelligence/ -q
```
