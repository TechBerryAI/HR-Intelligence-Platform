# Benchmark Datasets

Frozen evaluation sets organized by **category**. Never train on benchmark data.

> **Path:** `ai/dataset/lake/benchmark/`

## Categories (planned layout)

| Category | Registry ID | Features | Status |
|----------|-------------|----------|--------|
| `parsing/` | `BENCH-PARSE-v{N}` | Resume/JD parsing, bulk parse | Planned |
| `matching/` | `BENCH-MATCH-v{N}` | Resume–JD matching | Planned |
| `ranking/` | `BENCH-RANK-v{N}` | Candidate ranking | Planned |
| `summarization/` | `BENCH-SUMMARY-v{N}` | Resume summaries | Planned |
| `generation/` | `BENCH-GEN-v{N}` | Interview questions | Planned |
| `search/` | `BENCH-SEARCH-v{N}` | AI search / retrieval | Planned |

Category subdirectories will be created when the first benchmark version is frozen. See layout below.

Full strategy: [BENCHMARK_STRATEGY.md](../../docs/BENCHMARK_STRATEGY.md)

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
- **Baseline:** record provider scores at freeze time

## First benchmark (M4 target)

`parsing/v1/` — ≥50 resumes + ≥50 JDs with gold `expected_toon`

## Related documentation

- [TOON benchmarks](../../toon/v1/benchmarks/README.md)
- [Data lake](../README.md)
