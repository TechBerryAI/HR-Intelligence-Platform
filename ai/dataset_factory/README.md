# Dataset Factory

First executable component of the AI platform. Reusable pipeline that transforms raw resumes and job descriptions into production-quality training datasets.

**Entry point:** [`manifest.yaml`](manifest.yaml)

| Artifact | Path |
|----------|------|
| Pipeline flow | [`pipeline.yaml`](pipeline.yaml) |
| Implementation roadmap | [`roadmap.yaml`](roadmap.yaml) |
| Shared interfaces | [`shared/`](shared/) |
| Stage 1 — Inspector | [`inspector/`](inspector/) |

## Pipeline

```
Inspector → Extractor → Validator → Normalizer → Human Review → JSONL Export → Training Dataset
                                      ↘ Benchmark (frozen branch)
```

Inspector is **designed** (schemas + templates). All other stages are **interface only**.

## Constraints

- Never modifies `datasets/raw/` source files
- No HRMS, backend, frontend, training, or Ollama changes
- No fake statistics — templates use `null` placeholders

## Current milestone

**M3.1 — Dataset Inspector (design)** ✅

**Next:** M3.2 — Inspector Python implementation
