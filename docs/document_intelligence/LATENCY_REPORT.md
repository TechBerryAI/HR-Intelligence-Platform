# Document Intelligence — Latency Report

**Hardware profile:** `cpu`  
**Model hint:** `qwen2.5:3b-instruct`

| Suite | N | mean ms | p50 ms | p95 ms |
|-------|---|---------|--------|--------|
| Resume | 50 | 2.1 | 1.6 | 1.9 |
| JD | 50 | 1.5 | 1.5 | 1.9 |

Notes: In-memory text path (source.txt), deterministic section parsers, LLM skipped when coverage gate passes.
