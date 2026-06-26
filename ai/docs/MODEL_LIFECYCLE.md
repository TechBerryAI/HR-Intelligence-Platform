# Model Lifecycle

Model promotion from experiment to production. Registry is the authority — see [registry/README.md](../registry/README.md).

## Lifecycle diagram

```
experiments/          research & hypothesis
      ↓
training/runs/        QLoRA / LoRA execution
      ↓
models/adapters/      promoted adapter weights
      ↓
models/merged/        base + adapter merge
      ↓
models/gguf/          quantized inference weights
      ↓
exports/modelfiles/   Ollama deployment config
      ↓
evaluation/reports/   benchmark against all providers
      ↓
registry/models/      status: candidate → staging → production
      ↓
HRMS integration      future M5 (feature-flagged)
```

Full pipeline: [DATA_PIPELINE.md](DATA_PIPELINE.md)

## Status lifecycle

```
candidate → staging → production → deprecated
```

| Status | Criteria | Actions allowed |
|--------|----------|-----------------|
| `candidate` | Training complete, eval run exists | Local testing |
| `staging` | Passed regression gates, loaded in Ollama | Internal HRMS staging env |
| `production` | Approved by team, feature flag ready | HRMS production |
| `deprecated` | Superseded by newer version | Audit only, no new deploys |

## Promotion gates

From `evaluation/regression/gates.yaml`:

| Gate | Threshold |
|------|-----------|
| `toon_validity` | ≥ 0.95 |
| `required_fields` | ≥ Grok baseline |
| `field_f1` | ≥ Grok baseline − 0.02 |
| `latency_p95_ms` | ≤ 30,000 |

## Rollback

1. Set HRMS `LLM_PROVIDER=xai` (M5+)
2. Update registry status → `deprecated`
3. Document in `registry/models/{id}.yaml` → `notes`
4. Root-cause via `evaluation/reports/.../failures.jsonl`

## Multi-feature models

| Feature | Model ID pattern | Shared base? |
|---------|-----------------|--------------|
| Parsing (resume + JD) | `hrms-parsing-v{N}` | Same model, different prompts |
| Matching | `hrms-matching-v{N}` | May share encoder |
| Summarization | `hrms-summary-v{N}` | Separate fine-tune |

## Related documents

- [REPRODUCIBILITY.md](REPRODUCIBILITY.md)
- [DATA_PIPELINE.md](DATA_PIPELINE.md)
