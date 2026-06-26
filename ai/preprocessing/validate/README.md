# Validate

**Stage 4** — quality gates before data enters training or benchmark sets.

## Inputs

| Source | Format |
|--------|--------|
| `datasets/normalized/` | JSON with `toon` dict |

## Outputs

| Destination | Format |
|-------------|--------|
| `datasets/normalized/_reports/{batch_id}/` | Validation report JSON |
| Pass records | Forwarded to `preprocessing/split/` |
| Fail records | `datasets/normalized/_quarantine/` (gitignored) |

## Responsibilities

1. TOON schema validation (required fields per `doc_type`).
2. Cross-field consistency (e.g. `total_experience_years` vs experience entries).
3. Duplicate detection via `source_hash`.
4. PII policy checks (optional redaction flags).
5. Compute dataset-level statistics: field coverage, avg length, label source distribution.
6. **Gate:** ≥ 95% pass rate before split; otherwise block training.

## Report schema (excerpt)

```json
{
  "batch_id": "2026-06-25T12:00:00Z",
  "total": 1000,
  "passed": 972,
  "failed": 28,
  "pass_rate": 0.972,
  "failures_by_reason": { "missing_person_name": 12 },
  "field_coverage": { "person.linkedin": 0.65 }
}
```

## Future scripts

| Script | Purpose |
|--------|---------|
| `scripts/validate_dataset.py` | Run full validation suite |
| `scripts/quarantine_review.py` | Human review of failed records |

## Next stage

→ `preprocessing/split/` (only on pass)
