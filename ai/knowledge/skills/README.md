# Skills knowledge base

Canonical skill registry for the HR Intelligence Foundation.

## Layout

| File | Purpose |
|------|---------|
| `schema.yaml` | Entry shape and sharding rules |
| `aliases.json` | Surface form → `canonical_id` map |
| `entries/` | Sharded canonical records (`shard-0001.json`, …) |
| `index.json` | Optional id → shard index (create when scaling) |

## Adding entries

1. Choose or generate `id` matching `skill-{slug}` (see `schema.yaml`).
2. Append to the current shard or create `entries/shard-NNNN.json` when a shard reaches ~1000 entries.
3. Register aliases in `aliases.json`:

```json
{
  "canonical_id": "skill-example",
  "aliases": ["Example", "example lang"],
  "locale": "en",
  "match": "case_insensitive"
}
```

4. Bump `version` in `schema.yaml` on breaking entry shape changes.

## Contract link

Domain contract: `ai/contracts/skill.yaml`

## Versioning

- Patch: new entries or aliases only
- Minor: new optional entry fields
- Major: breaking entry schema (requires re-shard migration)
