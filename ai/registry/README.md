# Registry

Central metadata catalog for the HRMS AI platform. **The registry is the source of truth for lineage** — binary artifacts in `models/` and `dataset/lake/` are referenced by path, not embedded.

## Sub-registries

Eight artifact categories:

```
registry/
├── schema.yaml
├── models/           # Model versions, artifacts, promotion status
├── datasets/         # Dataset versions, checksums, provenance
├── benchmarks/       # Frozen benchmark definitions (BENCH-*)
├── experiments/      # EXP-* hypothesis outcomes
├── prompts/          # PROMPT-* version history
├── providers/        # PROV-* capability and config references
├── evaluations/      # EVAL-* run records linked to reports
└── deployments/      # DEPLOY-* Ollama/gateway deployment snapshots
```

## Why multiple registries (not one)

| Registry | Problem it solves |
|----------|-------------------|
| **models/** | Which model is in production? What trained it? |
| **datasets/** | Which data trained model v3? Checksums valid? |
| **benchmarks/** | Which eval set gates promotion? Is it frozen? |
| **experiments/** | What did EXP-0007 conclude? Link to runs. |
| **prompts/** | Which prompt version was used for train + eval? |
| **providers/** | Which Grok model string? Rate limits? Fallback order? |
| **evaluations/** | Did EVAL-PARSE-20260625 pass gates? Immutable record. |
| **deployments/** | What Ollama tag + Modelfile is staging? Prevent `latest` drift. |

See [adr/ADR-003-registry-design.md](../docs/adr/ADR-003-registry-design.md).

---

## Prompt registry (example)

File: `registry/prompts/PROMPT-0007.yaml`

```yaml
id: PROMPT-0007
version: "2.1.0"
feature: parsing
doc_type: resume
status: active              # active | deprecated
file: prompts/parsing_resume.yaml
previous: PROMPT-0006
created_at: "2026-06-25T10:00:00Z"
changelog: "Improved URL extraction instructions"
used_by:
  datasets: [DS-PARSE-v1.0.0]
  models: [hrms-parsing-v1]
  evaluations: [EVAL-PARSE-20260625]
```

---

## Provider registry (example)

File: `registry/providers/PROV-GROK.yaml`

```yaml
id: PROV-GROK
name: Grok / X.AI
status: active
type: cloud
config_ref: configs/providers.yaml
defaults:
  model: grok-4-fast-reasoning
  base_url: https://api.x.ai/v1
  timeout_seconds: 45
capabilities:
  - parsing
  - summarization
key_rotation: true
key_env_prefix: HRMS_API_KEY_
baseline_for:
  - BENCH-PARSE-v1
```

---

## Evaluation registry (example)

File: `registry/evaluations/EVAL-PARSE-20260625.yaml`

```yaml
id: EVAL-PARSE-20260625
benchmark: BENCH-PARSE-v1
created_at: "2026-06-25T16:00:00Z"
report: evaluation/reports/EVAL-PARSE-20260625/
config_snapshot: evaluation/reports/EVAL-PARSE-20260625/config.yaml
targets:
  - provider: PROV-GROK
    model: grok-4-fast-reasoning
  - provider: PROV-OLLAMA
    model: hrms-parsing-v1
metrics_summary:
  PROV-GROK:
    toon_validity: 0.97
    required_fields: 0.93
  PROV-OLLAMA:
    toon_validity: 0.96
    required_fields: 0.94
passed_gates: true
promotion_decision: candidate → staging
```

---

## Deployment registry (example)

File: `registry/deployments/DEPLOY-parsing-v1-ollama.yaml`

```yaml
id: DEPLOY-parsing-v1-ollama
model: hrms-parsing-v1
target: ollama
status: staging
created_at: "2026-06-26T09:00:00Z"
artifacts:
  gguf: models/gguf/hrparser-v1-llama32-3b-q4_k_m.gguf
  modelfile: exports/modelfiles/hrms-parsing-v1.Modelfile
ollama:
  host: ${OLLAMA_HOST:http://192.168.1.200:11434}
  model_name: hrms-parsing-v1
  tag: "v1.0.0"           # immutable tag — not `latest`
prompts:
  resume: PROMPT-0007
  jd: PROMPT-0008
health_check:
  last_passed: "2026-06-26T09:30:00Z"
```

---

## Model registry record

File: `registry/models/hrms-parsing-v1.yaml`

```yaml
id: hrms-parsing-v1
version: "1.0.0"
artifact_id: ART-MODEL-hrms-parsing-v1
status: candidate
feature: parsing

training:
  run_id: parsing-qlora-llama32-3b-v1-20260625
  experiment: EXP-0001
  dataset: DS-PARSE-v1.0.0

artifacts:
  adapter: models/adapters/parsing-qlora-llama32-3b-v1-20260625/
  merged: models/merged/hrms-parsing-v1/
  gguf: models/gguf/hrparser-v1-llama32-3b-q4_k_m.gguf

compatible:
  datasets: [DS-PARSE-v1.0.0]
  prompts: [PROMPT-0007, PROMPT-0008]
  benchmarks: [BENCH-PARSE-v1]
  deployments: [DEPLOY-parsing-v1-ollama]
  evaluations: [EVAL-PARSE-20260625]
```

---

## Status lifecycle (models)

```
candidate → staging → production → deprecated
```

---

## Schema validation

All records conform to [schema.yaml](schema.yaml). Future: `scripts/validate_registry.py`.

---

## Related documents

- [VERSIONING.md](../docs/VERSIONING.md)
- [ARTIFACT_LINEAGE.md](../docs/ARTIFACT_LINEAGE.md)
- [REPRODUCIBILITY.md](../docs/REPRODUCIBILITY.md)
