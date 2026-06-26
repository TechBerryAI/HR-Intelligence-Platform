# Job titles knowledge base

Canonical job title registry for role normalization and ATS experience matching.

## Layout

| File | Purpose |
|------|---------|
| `schema.yaml` | Entry shape and sharding rules |
| `aliases.json` | Alternate titles → `canonical_id` |
| `entries/` | Sharded canonical records |

## Adding entries

1. Assign `id` as `title-{slug}` per `schema.yaml`.
2. Add shard entries under `entries/`.
3. Register aliases (e.g. "SWE" → `title-software-engineer`).

## Contract link

Primary use: `experience.title` on resumes; `title` on job descriptions.

Domain contract: `ai/contracts/experience.yaml`, `ai/contracts/job_description.yaml`
