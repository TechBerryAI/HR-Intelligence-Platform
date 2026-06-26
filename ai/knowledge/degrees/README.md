# Degrees knowledge base

Canonical academic degree registry for education normalization.

## Layout

| File | Purpose |
|------|---------|
| `schema.yaml` | Entry shape |
| `aliases.json` | Abbreviations and variants (BS, B.Sc., Bachelor of Science) |
| `entries/` | Sharded degree records |

## Adding entries

1. Use `degree-{slug}` ids.
2. Register common abbreviations in `aliases.json` pointing to the same `canonical_id`.

## Contract link

Domain contract: `ai/contracts/education.yaml`

Used by ATS when comparing resume `education[].degree` to JD `qualifications[]`.
