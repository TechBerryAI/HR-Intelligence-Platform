# Phase 6 — Education record reconstruction

Measured 9 September 2026. Phase 3 / 4 / 5 / 5.2 frozen. Experience and Duties untouched except regression checks.

## A. Taxonomy of the prior 7 Education fails

| Resume | Class | First bad stage | Notes |
|---|---|---|---|
| ARNABROY | C + O | Degree recognition / OCR heal | Spaced `B T E C H` / `2 0 2 1`; institution-only row dropped from form |
| AshokKumarRM | C + M | Degree pattern | `B-Tech` not matched by `B.?\s?Tech` |
| AshishKavathekar | A | Section header | `Academic Profile` not mapped to Education; `Completed … from …` dropped as duty verb |
| BhaveshAshokJadhav | A | Section / labeled line | Education only under `Professional Qualification:-` inside Summary Of Qualifications |
| Ch.Bharati | A / N | Section pollution | Real Bachelor block **before** `Education` heading; Education span is skills (`AL HISTORY`) |
| DandgeAnjaliBaburao | Q | Scorer | No real education; `_DEGREE_CUE` matched prose `me` |
| Divyesh | Q | Scorer | Same `me` false positive |

Classes: **A** section ownership, **C** record construction, **M** missing pattern, **O** OCR spacing, **N** section noise, **Q** scorer hygiene.

## B. Scorer change

File: `ai/eval/apply_public_eval/score.py`

**Before:** `b\.?\s*[ea]\.?|m\.?\s*[ea]\.?` matched bare English `me` / `be`.

**After:** Require full degree words, `B-Tech` / `B.Tech`, or **dotted** abbreviations (`B.E.`, `M.A.`). No bare `me`/`be`/`ma`/`ba`.

Effect: Dandge + Divyesh → **n/a** (not parser failures).

## C. Parser / layout fixes (narrow)

1. **Hyphen + spaced B.Tech** — `B\.?\s*-?\s*Tech` / `BTECH` in degree patterns + validators.
2. **`Completed` / `Professional Qualification:-` lines** — do not treat as Experience duty when degree-like; strip status/qualification prefixes; peel mid-line `In 2022`; allow comma institutions in FROM-clauses.
3. **OCR heal in Education lines** — letter-spaced degrees (`B T E C H` → `B.Tech`) and digit-spaced years (`2 0 2 1` → `2021`).
4. **Header aliases** — `Academic Profile`, `Professional Qualification(s)` → Education (+ `pick_section`).
5. **Unlabeled recovery** — absorb `(FIELD)` lines and short institution wraps; single-line `Degree from Inst`; recover Ch.Bharati pre-heading Bachelor when Education span is polluted.
6. **Column-padded year** — `2018    B. Tech. from JNTU` peels leading year (AshokPandi).

## D. Goldens

`tests/backend/document_intelligence/test_education_layouts.py` — 9 synthetic layouts (no corpus PII).

## E. Metrics (195 corpus, in-process, semantic association on)

| Metric | Pre Phase 6 (after 5.2) | Phase 6 |
|---|---|---|
| Acceptable | **159/195** | **161/195** |
| Education fail | **7** | **0** |
| Education pass / n/a | 185 / 3 | **191 / 4** |
| Experience fail | 2 | 2 (unchanged) |
| Duties / description fail | 0 | 0 (unchanged) |

Prior-7 after fix: ARNAB, Ashish, AshokKumarRM, Bhavesh, Ch.Bharati → **pass**; Dandge, Divyesh → **n/a**.

Residual Ashok / AshokPandi (exposed by stricter scoring paths) also **pass** after `B. Tech` + column-year peel.

## F. What we did **not** do

* No Phase 3 association reopen
* No Phase 4 Experience recovery reopen
* No inventing employers / degrees / duties
* No Ankita OCR Experience chase / Ansari invention
* No full Education parser rewrite

## G. DI regression

* Education goldens: **9 passed**
* Experience layouts: **79 passed**
* Known pre-existing: Berlin `resume_009` location; short PROFESSIONAL OBJECTIVE summary length gate (`len >= 80`)

## H. Next bottleneck (recommended)

1. **Location** (~16 fails) — largest remaining Class B/C field after Education.
2. **Role** (~9) / company association residuals (Bipin-style misassociation).
3. **OCR / layout** for residual Experience (Ankita) — only if product priority, not invention.

## I. Artifacts

* Audit: `_forensic_tmp/phase6_education_audit/`
* Eval: `_forensic_tmp/phase6_education_eval/phase6_on.json`, `prior7.json`
* This report: `forensic_tmp/phase6_education_record_reconstruction_report.md`
