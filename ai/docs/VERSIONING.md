# Versioning Strategy

Canonical versioning rules for the HRMS AI platform. All engineers must follow these conventions to ensure reproducibility, auditability, and five-year maintainability.

---

## Versioning philosophy

1. **Immutable versions** — never mutate a released version; create the next one.
2. **Human-readable IDs** — prefixed identifiers (`EXP-`, `PROMPT-`, `BENCH-`) for cross-referencing in tickets and ADRs.
3. **Semantic versions where appropriate** — datasets and prompts use semver; experiments use sequential IDs.
4. **Registry is authoritative** — filesystem paths follow registry IDs, not the reverse.

---

## ID prefix registry

| Prefix | Entity | Example | Registry path |
|--------|--------|---------|---------------|
| *(none)* | Dataset file | `resume_v1.0.0.jsonl` | `registry/datasets/` |
| `hrms-` | Model | `hrms-parsing-v1` | `registry/models/` |
| `EXP-` | Experiment | `EXP-0001` | `registry/experiments/` |
| `PROMPT-` | Prompt | `PROMPT-0007` | `registry/prompts/` |
| `BENCH-` | Benchmark | `BENCH-PARSE-v1` | `registry/benchmarks/` |
| `EVAL-` | Evaluation run | `EVAL-PARSE-20260625` | `registry/evaluations/` |
| `DEPLOY-` | Deployment | `DEPLOY-parsing-v1-ollama` | `registry/deployments/` |
| `PROV-` | Provider | `PROV-GROK` | `registry/providers/` |
| `ART-` | Artifact | `ART-EXTRACT-a1b2c3` | Embedded in artifact metadata |

---

## Datasets

### File naming

```
{doc_type}_v{major}.{minor}.{patch}.jsonl
```

| Example | Meaning |
|---------|---------|
| `resume_v1.0.0.jsonl` | Resume training split, initial release |
| `jd_v1.0.0.jsonl` | JD training split |
| `resume_v1.1.0.jsonl` | Added 200 resumes, backward compatible |
| `resume_v2.0.0.jsonl` | Schema change — breaking |

### Directory naming (splits)

```
datasets/jsonl/{feature}-v{major}/
  train.jsonl    → may symlink or embed version in manifest
  val.jsonl
  test.jsonl
  manifest.yaml
```

### Registry ID

```yaml
id: DS-PARSE-v1.0.0
feature: parsing
version: "1.0.0"
```

### Version bump rules

| Change | Bump |
|--------|------|
| Add records, same schema | PATCH (1.0.0 → 1.0.1) |
| Add records, new doc types in mix | MINOR (1.0.0 → 1.1.0) |
| Schema field added (optional) | MINOR |
| Schema field removed or type changed | MAJOR (1.x → 2.0.0) |
| Re-label existing records | MAJOR (provenance change) |

---

## Models

### Model ID

```
hrms-{feature}-v{N}
```

Examples: `hrms-parsing-v1`, `hrms-matching-v2`, `hrms-summary-v1`

### GGUF filename

```
{model_short}-v{N}-{base_model}-{quant}.gguf
```

| Example | Components |
|---------|------------|
| `hrparser-v1-qwen2.5-7b-q4_k_m.gguf` | short name, version, base, quantization |
| `hrparser-v1-llama32-3b-q4_k_m.gguf` | Llama 3.2 3B variant |

**Rules:**
- Lowercase, hyphens only (no underscores in filenames)
- Quantization suffix: `q4_k_m`, `q8_0`, `f16`
- Base model abbreviated: `qwen2.5-7b`, `llama32-3b`, `mistral-7b`

### Registry record

```yaml
id: hrms-parsing-v1
version: "1.0.0"
artifact_id: ART-MODEL-hrms-parsing-v1
```

---

## Experiments

### ID format

```
EXP-{NNNN}
```

Sequential, zero-padded: `EXP-0001`, `EXP-0002`, …

### Directory naming

```
experiments/EXP-0001_{kebab-slug}/
```

Example: `experiments/EXP-0001_parsing-qlora-baseline/`

**Why sequential IDs:** Experiments are numerous and often abandoned. Sequential IDs avoid date collisions and simplify ticket references. Date is recorded in registry metadata.

---

## Prompts

### ID format

```
PROMPT-{NNNN}
```

Sequential: `PROMPT-0001`, `PROMPT-0007`

### Version field (within prompt YAML)

```yaml
id: PROMPT-0007
version: "2.1.0"
feature: parsing
doc_type: resume
```

### File naming

```
prompts/{feature}_{doc_type}.yaml
```

Examples: `prompts/parsing_resume.yaml`, `prompts/matching_pair.yaml`

Registry holds full history; `prompts/` holds the **current active** version per feature/doc_type.

### Version bump rules

| Change | Bump |
|--------|------|
| Wording tweak, same output schema | PATCH |
| New optional output fields | MINOR |
| Required field changes | MAJOR |

---

## Benchmarks

### ID format

```
BENCH-{CATEGORY}-v{N}
```

| Category code | Feature |
|---------------|---------|
| `PARSE` | Resume + JD parsing |
| `MATCH` | Resume–JD matching |
| `RANK` | Candidate ranking |
| `SUMMARY` | Resume summarization |
| `GEN` | Interview question generation |
| `SEARCH` | AI search / retrieval |

Examples: `BENCH-PARSE-v1`, `BENCH-MATCH-v1`, `BENCH-GEN-v2`

### Directory layout

```
dataset/lake/benchmark/{category}/v{N}/
```

Maps to: `dataset/lake/benchmark/parsing/v1/` for `BENCH-PARSE-v1`

---

## Evaluations

### ID format

```
EVAL-{CATEGORY}-{YYYYMMDD}
```

Example: `EVAL-PARSE-20260625`

### Registry

`registry/evaluations/EVAL-PARSE-20260625.yaml` links to `evaluation/reports/`.

---

## Deployments

### ID format

```
DEPLOY-{feature}-v{N}-{target}
```

Examples:
- `DEPLOY-parsing-v1-ollama`
- `DEPLOY-parsing-v1-gateway`

---

## Providers

### ID format

```
PROV-{PROVIDER}
```

| ID | Provider |
|----|----------|
| `PROV-OLLAMA` | Ollama (local) |
| `PROV-GROK` | Grok / X.AI |
| `PROV-OPENAI` | OpenAI |
| `PROV-ANTHROPIC` | Claude |
| `PROV-GEMINI` | Google Gemini |

---

## Artifacts (lineage)

### ID format

```
ART-{TYPE}-{hash8}
```

| TYPE | Stage |
|------|-------|
| `RAW` | Raw document |
| `EXTRACT` | Extracted text |
| `CLEAN` | Cleaned text |
| `NORM` | Normalized JSON |
| `JSONL` | JSONL dataset |
| `ADAPTER` | LoRA adapter |
| `MERGED` | Merged model |
| `GGUF` | GGUF binary |
| `EVAL` | Evaluation report |
| `DEPLOY` | Deployment package |

Example: `ART-EXTRACT-a1b2c3d4`

Full specification: [ARTIFACT_LINEAGE.md](ARTIFACT_LINEAGE.md)

---

## Compatibility matrix (required in registry)

Every model registry entry must declare:

```yaml
compatible:
  datasets: ["DS-PARSE-v1.0.0"]
  prompts: ["PROMPT-0007"]
  benchmarks: ["BENCH-PARSE-v1"]
  deployments: ["DEPLOY-parsing-v1-ollama"]
```

---

## Deprecation

Deprecated versions remain in registry with `status: deprecated` and `superseded_by` field. Never delete registry records.

---

## Related documents

- [ARTIFACT_LINEAGE.md](ARTIFACT_LINEAGE.md)
- [CONVENTIONS.md](CONVENTIONS.md)
- [adr/ADR-005-versioning-strategy.md](adr/ADR-005-versioning-strategy.md)
