# Phase 3 — Semantic association & field accuracy

Measured 9 September 2026. Parser extractors, section detection, and OCR were not rewritten.

## Baseline

Frozen Apply eval (HTTP, prior environment):

```text
195 resumes
142 accepted
72.82%
```

Same 195-file corpus, **this machine, in-process, OCR unavailable**:

| Run | Accepted | Rate |
|---|---:|---:|
| Association **off** | 130 / 195 | 66.67% |
| Association **on** (this phase) | **131 / 195** | **67.18%** |

The 142 vs 131 gap is **not** this layer. Location fails 2 → 17 in both on/off runs here because RapidOCR/Tesseract are not installed. Class D = 0.

## New results (association on, this environment)

| Category | Pass | Fail | vs association off |
|---|---:|---:|---|
| Acceptance | 131 | 64 | **+1 resume** |
| Company | 171 | 11 | **+2 pass, −2 fail** |
| Duties / description | 154 | 14 | **+1 pass, −1 fail** |
| Role | 167 | 20 | same |
| Start date | 170 | 5 | same |
| End date | 148 | 5 | −1 pass (n/a shift) |
| Education (row) | 184 | 7 | same |
| Skills | 185 | 4 | same |
| Summary | 180 | 0 | same |
| Certifications | 105 | 0 | same |
| Experience (section) | 176 | 17 | −1 pass |
| Location | 164 | 17 | same (OCR, not this layer) |

Association accuracy (golden tests): duty leak and education date mix are classified as `misassociated` and now fail the new tests if they regress.

## Regression

Worse vs association-off in this environment:

* **Experience section:** 177 → 176 pass (one extra section-level fail)
* **End date:** 149 → 148 pass

Worse vs the frozen **142/195 HTTP** number: overall acceptance 142 → 131. Treat that as **environment/OCR**, confirmed by association-off also scoring 130 here.

Pre-existing tests (unchanged with this layer skipped): gold-lake Berlin location; `test_heading_plus_body_keeps_body_only` (`parse_summary` requires ≥80 characters).

## Improvements

* Company association on the 195 corpus (−2 fails)
* Duties / job description (−1 fail)
* Overall acceptance +1 vs the same-environment baseline
* Golden layouts: duties stay on the owning job; MBA dates do not take the B.Tech year; university-only rows do not invent a bachelor’s degree; `AWS` is not a certification; summary strips email/phone/LinkedIn

## Remaining failures (195 corpus, association on)

Grouped by eval class / field (Class B = 64 resumes). Typical leftover modes:

| Kind | Where it still shows |
|---|---|
| Missing | Empty company/role/duties on compact or two-column jobs; education 7 |
| Incorrect | Role still 20 fails |
| Misassociated | Some duties/company still on the wrong row (corpus, not the golden two-job case) |
| Partial | Education rows with degree or institution only |
| Unsupported inference | Blocked for generic “Bachelor’s Degree” from university-only text; not eliminated for every weak cue |
| OCR / layout | Location 17 fails here; two-column / scanned PDFs without RapidOCR |

Taxonomy used internally: `CROSS_RECORD_LEAK`, `ENTITY_MISASSOCIATION`, `SECTION_MISCLASSIFICATION`, `UNSUPPORTED_INFERENCE`, `FIELD_CONTAMINATION`, plus the rest in `association/taxonomy.py`.

## Representative examples

From `tests/backend/fixtures/association_gold/` (Apply parse tail):

1. **Two jobs / duty isolation** — ABC duties no longer include XYZ “Led engineering team”.
2. **Education dates** — MBA stays 2018; B.Tech/University B stays 2014.
3. **University only** — `ABC University` does not become “Bachelor’s Degree”.
4. **Cert vs skill** — `AWS Certified Solutions Architect` kept; bare `AWS` is not a cert; `PMP` kept.
5. **Summary boundary** — “Seeking a challenging role…” kept; email/phone/LinkedIn dropped from summary.

## Tests

```text
tests/backend/document_intelligence/test_semantic_association.py  (11 tests)
tests/backend/document_intelligence/association_gold.py         (field scorer)
tests/backend/fixtures/association_gold/*.txt + *.expected.json
```

Also re-run: apply e2e, phase 2 patterns, real resume patterns, hardening gold — 137 passed in that group.

Full `tests/backend/document_intelligence/`: 574 passed, 4 skipped, 5 failed (same 5 with association skipped).

## Next phase (only after this measurement)

Do not add resume-specific rules. Next work should be: layout/OCR location recall (restore the 142-class environment), then generalized two-column job-row recovery — still association, not keyword lists.
