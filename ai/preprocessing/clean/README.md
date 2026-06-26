# Clean

**Stage 2** — text normalization without semantic structuring.

## Inputs

| Source | Format |
|--------|--------|
| `datasets/extracted/` | JSON with `raw_text` |

## Outputs

| Destination | Format |
|-------------|--------|
| `datasets/cleaned/{doc_type}/{id}.json` | JSON with cleaned `text` field |

## Responsibilities

1. Unicode normalization (NFKC).
2. Whitespace collapse, line break standardization.
3. Remove repeated headers/footers (heuristic).
4. Strip null bytes and control characters.
5. Optional language detection tag (for future multilingual support).
6. Preserve original `raw_text` in metadata for audit.

## Output schema (excerpt)

```json
{
  "id": "uuid",
  "stage": "cleaned",
  "text": "cleaned plain text...",
  "cleaning": {
    "rules_applied": ["unicode_nfkc", "whitespace_collapse"],
    "language": "en",
    "char_count_before": 4521,
    "char_count_after": 4480
  }
}
```

## Future scripts

| Script | Purpose |
|--------|---------|
| `scripts/clean_batch.py` | Process all extracted records |

## Next stage

→ `preprocessing/normalize/`
