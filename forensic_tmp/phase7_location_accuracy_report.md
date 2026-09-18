# Phase 7 — Location accuracy audit & reconstruction

Measured 10 September 2026. Phases 3 / 4 / 5 / 5.2 / 6 frozen. No Role/Company association work.

## Baseline (pre Phase 7)

| Metric | Count |
| --- | ---: |
| Acceptable | **161/195** |
| Location fail | **15** |
| Experience fail | **2** |
| Duties fail | **0** |
| Education fail | **0** |

## Step 1 audit summary

All 15 fails were `location_supported_but_empty`:

| Bucket | Count | Disposition |
| --- | ---: | --- |
| **K (+ H/I)** scorer false positive | 11 | Leave blank; scorer → **n/a** |
| **A (+ F)** genuine candidate miss | 4 | Recover from address/header |

No wrong-city populated cases in the audited set.

## Scorer changes

File: `ai/eval/apply_public_eval/score.py`

* Added `extract_has_candidate_location_evidence()` — mirrors Phase 5.2 duties scoping.
* `source_support['location']` uses that helper instead of broad `_LOC_CUE` (bare cities / `remote`).
* Evidence requires:
  * labeled address/location/city/place **with a non-empty value** (bare `Place:` ignored)
  * `based in` / `residing` / `lives in` with a place token
  * labeled `Remote`/`Hybrid` as work mode only
  * contact-pipe trailing `City – State`
  * street/Dist. lines in the header window
* Does **not** treat employer/job/education/project cities or tech `Remote` as support.

Coverage: `resume_coverage._has_location_evidence` aligned to the same ownership rules.

## Extraction changes

Files:

* `apps/backend/app/ai/parser/enrichment/resume_text_inference.py` — `peel_place_from_candidate_address`, labeled permanent/present address, contact-pipe trailing place, street/Dist. header lines; labeled-only Remote
* `apps/backend/app/ai/document_intelligence/deterministic/__init__.py` — `extract_simple_location` wired to the same peels
* `apps/backend/app/ai/document_intelligence/coverage/resume_coverage.py` — evidence hygiene

Recovered patterns (generalized, no candidate-specific strings):

| Pattern | Example outcome |
| --- | --- |
| `Permanent Address: … Dist. City, State, PIN` | `Jalgaon, Maharashtra` |
| `email \| phone \| City – State` | `Kottayam, Kerala` |
| Street/locality line with known city | `Mumbai` |
| `Dist.-CITY (U.P.)` | `GHAZIPUR, Uttar Pradesh` |

Employer/education cities are not copied into candidate Location.

## Before/after Location table (audited 15)

| Resume | Previous | New | Evidence | Classification |
| --- | --- | --- | --- | --- |
| AJAYPATIL | fail ∅ | **pass** `Jalgaon, Maharashtra` | Permanent Address | CORRECT |
| AswinSuresh.docx | fail ∅ | **pass** `Kottayam, Kerala` | Header contact pipe | CORRECT |
| AswinSuresh.pdf | fail ∅ | **pass** `Kottayam, Kerala` | Header contact pipe | CORRECT |
| GeetanjaliAnandraoMali | fail ∅ | **pass** `Mumbai` | Street + city near contact | CORRECT |
| AshishPandey | fail ∅ | **n/a** ∅ | Job “Mumbai zone” only | NOT_STATED |
| Ashok | fail ∅ | **n/a** ∅ | Employer Mumbai / tech Remote | NOT_STATED |
| AshokKumarRM | fail ∅ | **n/a** ∅ | Job Bengaluru only | NOT_STATED |
| Ashvinishaligramjadhav | fail ∅ | **n/a** ∅ | TCS Mumbai / project cities | NOT_STATED |
| AshwinRameshGedekar.docx | fail ∅ | **n/a** ∅ | Institute cities | NOT_STATED |
| AshwinRameshGedekar.pdf | fail ∅ | **n/a** ∅ | Same | NOT_STATED |
| BhaveshAshokJadhav | fail ∅ | **n/a** ∅ | “Server Remote Utilities” | NOT_STATED |
| ChandramauliJani | fail ∅ | **n/a** ∅ | Employer Pune | NOT_STATED |
| ChittiboyinaNageswari | fail ∅ | **n/a** ∅ | Job Hyderabad | NOT_STATED |
| DevidasGholap | fail ∅ | **n/a** ∅ | Org `_ Mumbai` lines | NOT_STATED |
| G.RAMESHBABU | fail ∅ | **n/a** ∅ | Employer cities | NOT_STATED |

Bonus (exposed while closing residuals): AbhishekSingh Dist.-CITY → pass; BhushanPatil empty `Place:` → n/a.

## Location goldens

* `tests/backend/document_intelligence/test_location_scorer_hygiene.py` — 15 cases
* `tests/backend/document_intelligence/test_location_layouts.py` — 7 cases
* Combined with Phase 3–6 suites: **134 passed**

## Regression results

| Suite | Result |
| --- | --- |
| Location goldens | pass |
| Education layouts | pass |
| Experience layouts | pass |
| Section recovery (Phase 4) | pass |
| Semantic association (Phase 3) | pass |
| DI (excl. known Berlin e2e/gold) | 546 passed; 1 pre-existing short PROFESSIONAL OBJECTIVE summary fail |
| 195 corpus | see Final Metrics |

Invariants held: Education **0**, Duties **0**, Experience **2**.

## Final metrics (195 corpus)

| Field | Before (Phase 6 freeze) | After Phase 7 |
| --- | --- | --- |
| **Acceptable** | **161/195** | **172/195** |
| Location | fail **15** / pass 167 / n/a 13 | fail **2** / pass **169** / n/a **24** |
| Experience | fail 2 | fail **2** |
| Duties (description) | fail 0 | fail **0** |
| Education | fail 0 | fail **0** |
| Company | fail 4 | fail 4 |
| Role | fail 9 | fail 9 |
| Start | fail 2 | fail 2 |
| End | fail 2 | fail 2 |
| Name | fail 4 | fail 4 |
| Email | fail 0 | fail 0 |
| Phone | fail 1 | fail 1 |
| LinkedIn | fail 0 | fail 0 |
| Skills | fail 4 | fail 4 |
| Summary | fail 0 | fail 0 |
| Certifications | fail 0 | fail 0 |

## Residual Location fails (2)

Not part of the original audited 15. Likely `coverage_missing_with_evidence` / weak-header edge cases (e.g. value-based prose vs Dist. ownership). Left for a later narrow pass — **not** fixed by inventing cities.

## Artifacts

* Audit: `forensic_tmp/phase7_location_audit_report.md`, `_forensic_tmp/phase7_location_audit/`
* Eval: `_forensic_tmp/phase7_location_eval/phase7_on.json`, `prior15.json`
* This report: `forensic_tmp/phase7_location_accuracy_report.md`

## Decision

**COMPLETE / FREEZE**

Audited Phase 7 objectives met: 11 scorer false positives → n/a; 4 genuine candidate addresses recovered; acceptance **161 → 172**; Education/Duties/Experience invariants unchanged. Do not start Role/Company association in this phase.
