# Evaluation

Systematic measurement of model and provider quality across parsing, matching, and future AI features.

## Directory layout

```
evaluation/
├── README.md           # This file
├── metrics/            # Metric definitions and calculators (future code)
├── reports/            # Per-run evaluation output
├── comparisons/        # Side-by-side provider/model comparisons
└── regression/         # CI regression baselines and failure archives
```

## What belongs where

| Directory | Contents | Purpose |
|-----------|----------|---------|
| `metrics/` | Metric spec YAML, scoring rubrics | Single source of truth for what we measure |
| `reports/{eval_id}/` | Full eval run output per model/provider | Audit trail |
| `comparisons/{comparison_id}/` | Cross-provider tables, charts data | Grok vs Ollama vs OpenAI vs Claude vs fine-tuned |
| `regression/` | Baseline scores, failure JSONL, gate config | Block promotion if regression detected |

## Providers and models evaluated

| Target | Type | Role |
|--------|------|------|
| Grok (`grok-4-fast-reasoning`) | Cloud API | Production baseline |
| Ollama (fine-tuned) | Local | Primary target |
| OpenAI | Cloud API | Fallback candidate |
| Claude | Cloud API | Fallback candidate |
| Fine-tuned merged | Local / Ollama | Platform model under test |

Configuration: `configs/evaluation.yaml`

## Eval ID convention

```
eval-{feature}-{benchmark_version}-{YYYYMMDD}
```

Example: `eval-parsing-v1-20260625`

## Report structure

```
reports/eval-parsing-v1-20260625/
├── summary.json              # Aggregate metrics per provider/model
├── config.yaml               # Snapshot of evaluation config
├── providers/
│   ├── grok/
│   ├── ollama/
│   ├── openai/
│   └── claude/
├── failures.jsonl            # Records that failed gates
└── promotion_decision.yaml   # pass | fail | manual_review
```

## Comparisons

`comparisons/` holds derived analysis across multiple `reports/`:

```
comparisons/parsing-v1-baseline-vs-ollama-v1/
├── table.csv
├── delta.json                # per-metric deltas vs baseline
└── notes.md
```

## Regression

`regression/` stores the **current production baseline** scores. CI (future) compares new eval runs against these gates:

| Gate | Default threshold |
|------|-------------------|
| `toon_validity` | ≥ 0.95 |
| `required_fields` | ≥ Grok baseline |
| `field_f1` | ≥ Grok baseline − 0.02 |
| `latency_p95_ms` | ≤ 30,000 |

Update `regression/baseline.yaml` only when intentionally promoting a new production model.

## Feature expansion (long-term)

| Feature | Benchmark location | Metrics |
|---------|-------------------|---------|
| Parsing | `datasets/benchmark/parsing/` | TOON validity, field F1 |
| Matching | `datasets/benchmark/matching/` | NDCG, MRR (future) |
| Summarization | `datasets/benchmark/summarization/` | ROUGE, human score (future) |
| Interview Qs | `datasets/benchmark/interview/` | relevance score (future) |

Canonical reference: [docs/DATA_PIPELINE.md](../docs/DATA_PIPELINE.md)
