# Normalize

**Stage 3** — structured TOON-aligned records from cleaned text.

## Inputs

| Source | Format |
|--------|--------|
| `datasets/cleaned/` | JSON with cleaned `text` |
| Human annotations or LLM labels (bootstrap) | Optional sidecar TOON |

## Outputs

| Destination | Format |
|-------------|--------|
| `datasets/normalized/{doc_type}/{id}.json` | JSON with `toon` dict |

## Responsibilities

1. Produce TOON-compatible structured output per document.
2. Canonicalize field names and list formats (pipe-separated → arrays).
3. Apply skill normalization hooks (future: ontology lookup).
4. Record label source: `human`, `grok`, `openai`, `synthetic`.
5. Attach `prompt_version` used for LLM labeling.

## TOON contract

Output must be parseable by HRMS `toon_loads_flex()` and pass `validate_toon_format()` rules. Schema reference: [docs/DATA_PIPELINE.md](../../docs/DATA_PIPELINE.md#toon-schema-contract).

## Output schema (excerpt)

```json
{
  "id": "uuid",
  "stage": "normalized",
  "doc_type": "resume",
  "toon": { "type": "resume", "person": { "name": "..." } },
  "labeling": {
    "source": "human",
    "annotator": "engineer_id",
    "prompt_version": "1.0.0",
    "reviewed": true
  }
}
```

## Future scripts

| Script | Purpose |
|--------|---------|
| `scripts/normalize_batch.py` | Batch LLM or rule-based normalization |
| `scripts/import_hrms_toon.py` | Import existing `parsed_resumes` / `parsed_jds` TOON |

## Next stage

→ `preprocessing/validate/`
