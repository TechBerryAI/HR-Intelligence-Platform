# Knowledge Bases

Reference datasets for normalization, alias resolution, and entity linking.

## What is this?

Six curated knowledge bases provide canonical vocabularies for skills, job titles, degrees, certifications, companies, and locations.

## Components

| Base | Path | Purpose |
|------|------|---------|
| Skills | `skills/` | Skill aliases and categories |
| Job titles | `job_titles/` | Title normalization |
| Degrees | `degrees/` | Education credential vocabulary |
| Certifications | `certifications/` | Certification names |
| Companies | `companies/` | Employer normalization |
| Locations | `locations/` | Geographic aliases |

## Why does it exist?

Raw HR text uses inconsistent terminology. Knowledge bases enable deterministic normalization before TOON projection.

## What belongs here?

- `manifest.yaml` — registry of all bases
- `schema.yaml` per base — entry shape
- `entries/` — data shards (gitignored; structure tracked)

## What should never be placed here?

- Full resume corpora → `dataset/lake/`
- LLM-generated labels → `dataset/lake/proposals/`
- Runtime capability logic → `ai/capabilities/`

## Consumers

| Consumer | Usage |
|----------|-------|
| Normalization (future) | Alias lookup during schema validation |
| TOON dictionary | `ai/toon/v1/dictionary/` cross-references |

## Extension points

1. Add entries under `{base}/entries/`
2. Rebuild `index.json` when entry format changes
3. Register updates in `manifest.yaml`

## Related documentation

- [Contracts](../contracts/README.md)
- [TOON dictionary](../toon/v1/dictionary/dictionary.yaml)
