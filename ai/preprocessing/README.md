# Preprocessing

Modular data engineering pipelines. Each subdirectory is an **independent stage** with defined inputs, outputs, and responsibilities. Stages compose left-to-right; no stage writes to a prior stage's directory.

## Pipeline map

```
preprocessing/extract/    →  datasets/extracted/
preprocessing/clean/      →  datasets/cleaned/
preprocessing/normalize/  →  datasets/normalized/
preprocessing/validate/   →  validation reports (pass/fail gates)
preprocessing/split/      →  datasets/jsonl/{train,val,test}.jsonl
```

| Module | README | Input | Output |
|--------|--------|-------|--------|
| `extract/` | [extract/README.md](extract/README.md) | `datasets/raw/` | `datasets/extracted/` |
| `clean/` | [clean/README.md](clean/README.md) | `datasets/extracted/` | `datasets/cleaned/` |
| `normalize/` | [normalize/README.md](normalize/README.md) | `datasets/cleaned/` | `datasets/normalized/` |
| `validate/` | [validate/README.md](validate/README.md) | `datasets/normalized/` | Reports + gate decision |
| `split/` | [split/README.md](split/README.md) | `datasets/normalized/` | `datasets/jsonl/` |

## Design principles

- **Idempotent:** Re-running a stage with the same inputs produces the same outputs.
- **Manifest-driven:** Each stage writes a `manifest.json` with counts, checksums, and errors.
- **Isolated from HRMS:** No imports from `backend/` at runtime; TOON schema is mirrored, not imported.
- **Feature-agnostic core:** Extract/clean/normalize serve parsing today and summarization, skill extraction, etc. tomorrow.

## Future scripts (not implemented)

Scripts land in `scripts/` and call stage modules. Naming convention: `{stage}_{action}.py` (e.g. `extract_batch.py`).

Canonical reference: [docs/DATA_PIPELINE.md](../docs/DATA_PIPELINE.md).
