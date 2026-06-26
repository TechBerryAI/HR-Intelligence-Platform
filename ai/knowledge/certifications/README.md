# Certifications knowledge base

Canonical professional certification registry.

## Layout

| File | Purpose |
|------|---------|
| `schema.yaml` | Entry shape |
| `aliases.json` | Exam codes and alternate names |
| `entries/` | Sharded certification records |

## Adding entries

1. Use `cert-{slug}` ids.
2. Link `issuer_id` to `knowledge/companies` when the issuing org is canonicalized.
3. Add aliases for common abbreviations (e.g. "AWS SAA" → `cert-aws-solutions-architect-associate`).

## Contract link

Domain contract: `ai/contracts/certification.yaml`

TOON may store certifications as strings; normalization promotes to objects with `canonical_id`.
