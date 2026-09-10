# Apply Resume Parser — Trainer Summary

**Open this file only.** This is the current frozen baseline. Extra CSVs and a chart sit in the same folder if you need them; you do not need them to explain the result.

The parser is **frozen**. Do not treat this as a request to change parser code.

---

## The headline (start here)

We scored **195** resumes.

| | Score | Rate |
|---|---|---|
| **Original parser** | **69 / 195** | **35.38%** |
| **Final frozen parser** | **142 / 195** | **72.82%** |

What that means in one line:

- **+73** more resumes accepted
- **+37.44** percentage points
- **+105.8%** relative increase (accepted resumes more than doubled)

**Say this:** the parser went from about one-third accepted to about three-quarters accepted.

---

## How the score moved

69 → 82 → 94 → 117 → 131 → 141 → 142

| Version | Score | Rate |
|---|---|---|
| Original | 69/195 | 35.38% |
| Phase 2 | 82/195 | 42.05% |
| Phase 2F | 94/195 | 48.21% |
| Phase 2G | 117/195 | 60.00% |
| Phase 2H | 131/195 | 67.18% |
| Forensic | 141/195 | 72.31% |
| **Final (frozen)** | **142/195** | **72.82%** |

---

## What improved, what stayed the same, what is resolved

A **miss** means the evaluation expected that field and the parser did not get it right.

### Strongly / clearly improved

| Field | Before | After | Change |
|---|---:|---:|---|
| Start Date | 30 | 5 | 25 fewer misses (**83.3%** reduction) |
| End Date | 30 | 5 | 25 fewer misses (**83.3%** reduction) |
| Role | 19 | 6 | 13 fewer misses (**68.4%** reduction) |
| Duties | 31 | 15 | 16 fewer misses (**51.6%** reduction) |
| Company | 22 | 15 | 7 fewer misses (**31.8%** reduction) |

### Slight improvement or no change

| Field | Before | After | Note |
|---|---:|---:|---|
| Name | 5 | 4 | Slight improvement |
| Phone | 2 | 1 | Improved |
| Skills | 4 | 4 | **No change** |
| Education | 7 | 7 | **No change** |

### Resolved in this evaluation

Zero misses on the evaluation metric. That does **not** mean the parser is perfect on every resume in the world.

| Field | Before | After |
|---|---:|---:|
| Email | 1 | 0 |
| Certifications | 1 | 0 |
| LinkedIn | 1 | 0 |

---

## What we actually improved (keep this short)

- Employment **start and end dates** are extracted better and attached to the correct job.
- **Company and role** are paired more consistently.
- **Duties** are more often kept with the matching job row.
- Compact / one-line and mixed layouts are handled more often.
- Employer and tenure lines are used more reliably.
- Education, project, and client text is more often kept out of employment rows.
- More title/company formats are recognized (labels, pipes, “working as … in …”).
- HTTP parse now matches in-process parse: **195/195**.

---

## What is still inaccurate or missing

These misses remain on the frozen baseline:

| Field | Remaining misses |
|---|---:|
| Duties | 15 |
| Company | 15 |
| Education | 7 |
| Role | 6 |
| Start Date | 5 |
| End Date | 5 |
| Skills | 4 |
| Name | 4 |
| Phone | 1 |

**Say this:** most leftover errors are **association** problems — the text is there, but it is not attached to the correct field or job row.

Also still hard:

- compact one-line jobs
- two-column layouts
- unclear employment lines
- project / client names that are not the employer
- resumes that simply do not state the field clearly

Unclear source text is **not** a parser bug.

---

## Forensic check (one table)

From the `resume testing` files:

| Finding | Result |
|---|---|
| Fields analyzed | 2,251 |
| Genuine parser-related misses | 66 |
| Those 66 | all **association** failures |
| Source ambiguity | 8 |
| API / DTO failures | 0 |
| Class D | 0 |
| HTTP / in-process match | 195/195 |

---

## Full metrics (if asked)

| Metric | Result |
|---|---|
| Overall parser score | 142/195 |
| Acceptance rate | 72.82% |
| Improvement | +73 resumes |
| Percentage-point gain | +37.44 pp |
| Relative improvement | +105.8% |
| HTTP success | 195/195 |
| HTTP / in-process parity | 195/195 |
| Class D | 0 |
| Tests passed | 660 |
| Tests skipped | 4 |
| Start-date miss reduction | 83.3% |
| End-date miss reduction | 83.3% |
| Role miss reduction | 68.4% |
| Duties miss reduction | 51.6% |
| Company miss reduction | 31.8% |

---

## Before vs after (one slide)

| Field | Before | After | Status |
|---|---|---|---|
| Duties | 31 misses | 15 misses | Improved |
| Start Date | 30 | 5 | Strongly improved |
| End Date | 30 | 5 | Strongly improved |
| Company | 22 | 15 | Improved |
| Role | 19 | 6 | Strongly improved |
| Skills | 4 | 4 | No change |
| Name | 5 | 4 | Slight improvement |
| Phone | 2 | 1 | Improved |
| Email | 1 | 0 | Resolved |
| Education | 7 | 7 | No change |
| Certifications | 1 | 0 | Resolved |
| LinkedIn | 1 | 0 | Resolved |

---

## Closing lines for the trainer

The parser improved a lot from the original baseline: **69/195 → 142/195**. The biggest gains were employment dates, role, duties, and company. Email, certifications, and LinkedIn reached zero misses on this metric. Skills and education did not move. What is left is mainly association and difficult layouts. This baseline is **frozen**. Future work should be generalized association patterns, not resume-specific rules.

---

## Other files in this folder (optional)

| File | If you need |
|---|---|
| `apply_parser_simple_field_comparison.csv` | Spreadsheet of field misses |
| `apply_parser_simple_metrics.csv` | Spreadsheet of the metrics table |
| `apply_parser_simple_comparison.png` | Chart of score and field misses |
