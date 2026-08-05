# Document Intelligence — Latency Report

**Hardware profile:** `cpu`  
**Model hint:** `qwen2.5:3b-instruct`

| Suite | N | mean ms | p50 ms | p95 ms |
|-------|---|---------|--------|--------|
| Resume | 50 | 1.3 | 0.7 | 0.8 |
| JD | 50 | 4.9 | 3.3 | 3.8 |

Notes: In-memory text path (source.txt), deterministic section parsers, LLM skipped when coverage gate passes.
