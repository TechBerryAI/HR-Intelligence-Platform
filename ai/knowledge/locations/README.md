# Locations knowledge base

Canonical geographic location registry.

## Layout

| File | Purpose |
|------|---------|
| `schema.yaml` | Entry shape |
| `aliases.json` | City nicknames, metro names, common misspellings |
| `entries/` | Sharded location records |

## Adding entries

1. Use `loc-{slug}` ids (e.g. `loc-san-francisco-ca-us`).
2. Populate `country_code` with ISO 3166-1 alpha-2 when known.
3. Add `loc-remote` for remote/WFH normalization (see `schema.yaml`).

## Contract link

Domain contract: `ai/contracts/location.yaml`

TOON uses free-text `location` on JD and `person.location` on resumes.

## ATS note

Location scoring compares JD location string to candidate `person.location` in production HRMS.
