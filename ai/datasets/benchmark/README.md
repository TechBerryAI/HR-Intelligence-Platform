# Benchmark datasets

Frozen evaluation sets organized by **category**. Never train on benchmark data.

## Categories

| Directory | Registry ID | Features |
|-----------|-------------|----------|
| [parsing/](parsing/) | `BENCH-PARSE-v{N}` | Resume/JD parsing, bulk parse |
| [matching/](matching/) | `BENCH-MATCH-v{N}` | Resume–JD matching |
| [ranking/](ranking/) | `BENCH-RANK-v{N}` | Candidate ranking |
| [summarization/](summarization/) | `BENCH-SUMMARY-v{N}` | Resume summaries |
| [generation/](generation/) | `BENCH-GEN-v{N}` | Interview questions |
| [search/](search/) | `BENCH-SEARCH-v{N}` | AI search / retrieval |

Full strategy: [docs/BENCHMARK_STRATEGY.md](../docs/BENCHMARK_STRATEGY.md)

## Layout per category

```
{parsing|matching|...}/v{N}/
├── manifest.yaml
├── *.jsonl
└── README.md (optional)
```

## Versioning

- **Immutable:** create `v2/` — never edit `v1/`
- **Register:** `registry/benchmarks/BENCH-{CAT}-v{N}.yaml`
- **Baseline:** record Grok scores at freeze time

## First benchmark (M4 target)

`parsing/v1/` — ≥50 resumes + ≥50 JDs with gold `expected_toon`
