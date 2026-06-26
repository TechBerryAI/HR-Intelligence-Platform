# Companies knowledge base

Canonical organization registry for employer name normalization.

## Layout

| File | Purpose |
|------|---------|
| `schema.yaml` | Entry shape |
| `aliases.json` | Trade names, abbreviations, former names |
| `entries/` | Sharded company records |

## Adding entries

1. Use `company-{slug}` ids.
2. Register aliases without legal suffixes for matching; keep `canonical_name` as display default.
3. Set `headquarters_id` to a `loc-*` entry when known.

## Contract link

Domain contract: `ai/contracts/company.yaml`

TOON stores company as plain string on JD and `experience.N.company`.
