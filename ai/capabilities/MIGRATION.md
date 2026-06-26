# Capability Library Migration Notes

## Summary

The AI Runtime now resolves all tasks through the **Capability Library** (`ai/capabilities/`) instead of scattered prompt/schema YAML metadata files.

**Public API: unchanged.** `get_runtime()`, `run_task()`, and `AIRuntime` method signatures are identical.

## What Changed (Internal Only)

| Component | Before | After |
|-----------|--------|-------|
| Task definitions | `runtime/config/tasks.default.yaml` | Capability `runtime.yaml` + `capability.yaml` |
| Prompts | `runtime/prompts/definitions/*.yaml` (stub templates) | Capability `prompt.md` |
| Schemas | `runtime/schemas/definitions/*.yaml` (no JSON files) | Capability `schema.json` |
| Validation | Inline `validation` dict in tasks YAML | Capability `validation.yaml` |
| Execution config | TaskDefinition fields only | Capability `runtime.yaml` (temperature, timeout, streaming, etc.) |

## Execution Flow Migration

```
# Before
Task → PromptRegistry → SchemaRegistry → OutputValidator → Provider

# After
Task → CapabilityRegistry → prompt.md → schema.json → validation.yaml → runtime.yaml → Provider
```

`TaskRegistry`, `PromptRegistry`, and `SchemaRegistry` remain as facade APIs but delegate to `CapabilityRegistry` when `capabilities_dir` is configured.

## Configuration

Add to `runtime.default.yaml`:

```yaml
runtime:
  capabilities_dir: ../../capabilities
```

Path is relative to the runtime config file directory (`ai/runtime/config/`).

Legacy mode (no `capabilities_dir`) still loads from `tasks_config_path`, `prompts_dir`, and `schemas_dir`.

## Schema ID Changes

| Legacy ID | Capability Schema ID |
|-----------|---------------------|
| `matching_v1` | `candidate_match_v1` |
| `summary_v1` | `resume_summary_v1` |
| `resume_v1` | `resume_v1` (unchanged) |
| `jd_v1` | `jd_v1` (unchanged) |

Task names are unchanged (`candidate_matching`, `resume_summary`, etc.).

## Validation Behavior

Real JSON Schema validation is now **enabled** for capabilities with `schema_validate: true`. Mock provider responses in `runtime.default.yaml` were updated with schema-compliant payloads for local development and tests.

## New Runtime Property

```python
runtime = get_runtime()
runtime.capabilities  # CapabilityRegistry | None
runtime.capabilities.get("resume_parsing")
```

Existing properties (`runtime.tasks`, `runtime.prompts`, `runtime.schemas`) continue to work.

## TaskResult Metadata

Successful executions now include additional metadata:

- `capability_id`
- `capability_version`
- `output_mode`

## Deprecated (Not Removed)

These paths are retained for reference and legacy fallback:

- `ai/runtime/config/tasks.default.yaml`
- `ai/runtime/prompts/definitions/`
- `ai/runtime/schemas/definitions/`

Do not add new prompts or schemas there. Use the Capability Library.

## Rollback

To revert to legacy registries, remove or comment out `capabilities_dir` in runtime config. The runtime will fall back to YAML task/prompt/schema definitions.

## Checklist for New Capabilities

- [ ] Create folder under `ai/capabilities/<id>/`
- [ ] Add all required files (`capability.yaml`, `prompt.md`, `schema.json`, `validation.yaml`, `runtime.yaml`)
- [ ] Add example templates (no real HR data)
- [ ] Add benchmark definition
- [ ] Add capability tests under `tests/`
- [ ] Register model alias if new
- [ ] Verify with `runtime.run_task("<id>", sample_input)`

No runtime modifications required.
