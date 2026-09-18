# Phase 7 Step 1 — Location failure audit (no code changes)

Measured 10 September 2026 against the current venv / RapidOCR 195-resume corpus.

**Status:** AUDIT ONLY — no parser, scorer, association, Experience, Education, or Duties code was modified.

---

## Baseline (this audit run)

| Metric | Count |
| --- | ---: |
| Acceptable | **159/195** |
| Location fail / pass / n/a | **15 / 167 / 13** |
| Education fail | **0** |
| Experience fail | **2** |
| Duties (description) fail | **2** *(see note)* |

Phase 6 freeze baseline was **161/195** acceptable with Duties **0**. This audit run logged RapidOCR “no OCR engine available” on some pages and Duties fail **2**. Treat **159** as this-run snapshot; Location **15** matches the prior Phase 6 field tally. Reconfirm Duties on the implementation pass before attributing any Duties change to Location work.

All 15 Location fails share scorer reason: `location_supported_but_empty` (empty `currentLocation`, but `_LOC_CUE` fired on the extract).

Artifacts:

* `_forensic_tmp/phase7_location_audit/location_fails_audit.json`
* `_forensic_tmp/phase7_location_audit/location_fails_deep.json`
* `_forensic_tmp/phase7_location_audit/audit_location_fails.py`
* `_forensic_tmp/phase7_location_audit/deep_trace_location.py`

---

## Taxonomy legend

| Code | Meaning |
| --- | --- |
| **A** | Location exists but parser misses it |
| **B** | Location exists but OCR corrupts it |
| **C** | Extracted but assigned to wrong field |
| **D** | Extracted from wrong section |
| **E** | Multiple locations; wrong one selected |
| **F** | City/state/country in address/header/contact |
| **G** | Current vs permanent address ambiguity |
| **H** | Company/project/client/office location treated as candidate location |
| **I** | Employment-history location treated as candidate location |
| **J** | Location genuinely not stated |
| **K** | Scorer incorrectly expects a location |

---

## Executive finding

Of **15** Location fails:

| Refined bucket | Count | Meaning |
| --- | ---: | --- |
| **K (+ H/I)** — blank is correct; scorer false fail | **11** | City/remote tokens appear only as employer, job, education, or tech prose |
| **A (+ F)** — true candidate location missed | **4** | Explicit header/address evidence exists; form Location empty |

There are **no** cases in this set of populated-but-wrong Location (no C/E mis-selection failures among the 15). The dominant defect is **scorer support too broad** (`_LOC_CUE` matches bare city names and the word `remote` anywhere). Secondary defect is **parser miss on candidate-owned address/header forms**.

**Do not** “fix” the 11 K-cases by copying Mumbai/Bengaluru/Hyderabad/Pune from employment lines — that would violate Phase 7 Location semantics (CORRECT > BLANK > PLAUSIBLE BUT WRONG).

---

## Per-failure forensic table

| Resume | Expected (candidate-level) | Actual | Root cause | First bad stage | Action |
| --- | --- | --- | --- | --- | --- |
| AJAYPATIL | Jalgaon / Maharashtra (Permanent Address) | ∅ | **A + F** (+ weak section ownership) | Location parser (+ Permanent Address section polluted) | Parse labeled Permanent Address; do not invent |
| AswinSuresh.docx | Kottayam, Kerala (header contact pipe) | ∅ | **A + F** | Location parser — compact contact row | Extract trailing place from `email \| phone \| City – State` |
| AswinSuresh.pdf | Kottayam, Kerala (same) | ∅ | **A + F** | Location parser — compact contact row | Same generalized contact-row rule |
| GeetanjaliAnandraoMali | Mumbai address (Wadala … Mumbai) | ∅ | **A + F** (+ layout) | Layout/section + location parser | Recover address-like header line; avoid treating as hobby |
| AshishPandey | NOT_STATED | ∅ | **K (+ I)** | Scorer `_LOC_CUE` (“Mumbai zone” in duties) | Scorer: Experience-scoped cities ≠ candidate location |
| Ashok | NOT_STATED | ∅ | **K (+ H)** | Scorer (employer “Mumbai”; tech “Remote System”) | Scorer: drop bare `remote` / employer cities |
| AshokKumarRM | NOT_STATED (work-from Bengaluru only) | ∅ | **K (+ I)** | Scorer (job “from Bengaluru”) | Leave blank; scorer n/a |
| Ashvinishaligramjadhav | NOT_STATED | ∅ | **K (+ H)** | Scorer (“TCS Mumbai” title / Navi Mumbai projects) | Employer/project city ≠ candidate location |
| AshwinRameshGedekar.docx | NOT_STATED | ∅ | **K** | Scorer (institute “Pune” / “Nagpur”) | Education/training city ≠ candidate location |
| AshwinRameshGedekar.pdf | NOT_STATED | ∅ | **K** | Scorer (same family) | Same |
| BhaveshAshokJadhav | NOT_STATED | ∅ | **K** | Scorer matches **`Remote`** in “Server Remote Utilities” | Remove bare `remote` from `_LOC_CUE` or require location sense |
| ChandramauliJani | NOT_STATED | ∅ | **K (+ H)** | Scorer (employer “… Pune”) | Employer city ≠ candidate location |
| ChittiboyinaNageswari | NOT_STATED | ∅ | **K (+ I)** | Scorer (job “Hyderabad”) | Job city ≠ candidate location |
| DevidasGholap | NOT_STATED | ∅ | **K (+ H/I)** | Scorer (many “_ Mumbai” org lines; edu Pune) | Org/education cities ≠ candidate location |
| G.RAMESHBABU | NOT_STATED | ∅ | **K (+ H)** | Scorer (employer “(Hyderabad)/(Mumbai)”) | Employer city ≠ candidate location |

---

## Case dossiers (evidence)

### True misses (implement later)

**AJAYPATIL** — Explicit:

`Permanent Address: At.Post. Hingone Tal. Chopda Dist. Jalgaon, Maharashtra, 425108`

Also appears as a `Permanent Address` section whose body was polluted (`English, Hindi, Marathi`). Extractors `extract_simple_location` / `extract_location_from_text` both return empty. First bad stage: **location parser** (labeled permanent address), with contributing **section detection** noise.

**AswinSuresh (docx + pdf)** — Header contact:

`email | LinkedIn | +91 … | Kottayam – Kerala`

Candidate-owned. Job line separately has `Bengaluru Karnataka` (must **not** be preferred over header). First bad stage: **location parser** missing trailing place on pipe contact rows. OCR glyph `?` for en-dash is minor (**B**-adjacent), not the primary miss.

**GeetanjaliAnandraoMali** — Header/sidebar address:

`Wadala Shiwadhi Cross Road,Mumbai No : 31`

Landed under Unclassified/Hobbies due to two-column layout. Personal Details has no city. First bad stage: **layout/section ownership**, then **location parser** not recovering address-like lines near contact.

### Scorer false fails (blank is correct)

**BhaveshAshokJadhav** — `_LOC_CUE` hits **`Remote`** inside `Server Remote Utilities` (not geography).

**Ashok** — Employer `… Mumbai` + tech `Remote System`.

**AshokKumarRM / Ashvini / Chandramauli / Chittiboyina / Devidas / Rameshbabu / Ashwin*** — city tokens only beside employers, projects, institutes, or education boards.

**AshishPandey** — `Hubs Mumbai zone` inside HR duties.

Phase 7 semantics: these must remain **blank** unless a separate candidate address appears. Fix is **scorer hygiene** (mirror Phase 5.2 duties / Phase 6 degree cues), not inventing Location from jobs.

---

## First-bad-stage summary

| First bad stage | Count | Cases |
| --- | ---: | --- |
| Scorer `_LOC_CUE` too broad | 11 | AshishPandey, Ashok, AshokKumarRM, Ashvini, Ashwin×2, Bhavesh, Chandramauli, Chittiboyina, Devidas, Rameshbabu |
| Location parser (header/labeled address) | 3 | Aswin×2, AJAYPATIL |
| Layout/section + location parser | 1 | Geetanjali |

No Phase 3 association defect identified for Location in this set.  
No evidence that Experience reconstruction should change.  
Do **not** reopen frozen association to “fix” Location.

---

## Location semantics (locked for implementation)

Candidate Location may use:

1. Explicit address/location labels (including Permanent/Present/Current Address)
2. Clearly candidate-owned header/contact places (`City – State` on contact pipe rows)
3. Other strong candidate-level address evidence

Must **not** auto-use:

* Employer / office / client / project cities
* “Working from Bengaluru” employment lines alone
* College/board cities
* Bare `remote` in technical skills
* Arbitrary city tokens in prose

Priority: **CORRECT > BLANK/NOT_STATED > PLAUSIBLE BUT WRONG**.

---

## Recommended implementation order (Step 2+, not started)

1. **Scorer hygiene** — candidate-owned location evidence only (labeled address / header contact place); stop bare city/`remote` extract-wide cues. Expected: ~11 fails → **n/a**.
2. **Compact contact-row place** — trailing `City – State` after phone/email/LinkedIn pipes (Aswin).
3. **Labeled Permanent/Present Address** — including multi-token Indian address with Dist./PIN (AJAYPATIL).
4. **Address-like header lines** near email/phone despite weak section labels (Geetanjali) — generalized, no resume-specific strings.
5. Goldens + full DI + Phase 3–6 regression + 195 corpus.
6. Write final `forensic_tmp/phase7_location_accuracy_report.md` after before/after metrics.

---

## Decision gate (Step 1)

| Question | Answer |
| --- | --- |
| Code changed? | **No** |
| Ready to implement? | **Yes** — after this audit |
| Dominant root cause? | **Scorer false positives (K)** |
| Real parser work? | **4 resumes (A/F)** |
| Blocked by OCR? | **No** (Aswin dash glyph secondary) |
| Blocked by association? | **No** |

**Phase 7 status after Step 1:** AUDIT COMPLETE — awaiting implementation Steps 2–10.
