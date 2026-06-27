# Benchmark Strategy

Future-proof evaluation design for all HRMS AI features. Benchmarks are **frozen contracts** — models are measured against them; they are never trained on them.

---

## Principles

1. **Category isolation** — each feature has its own benchmark category.
2. **Version immutability** — `v1` never changes; add `v2` for new cases.
3. **Registry authority** — `BENCH-{CAT}-v{N}` in `registry/benchmarks/`.
4. **Baseline on creation** — record Grok (or best available) scores when benchmark is frozen.
5. **Regression gates** — `evaluation/regression/` holds thresholds per category.

---

## Directory layout

```
dataset/lake/benchmark/
├── parsing/           # BENCH-PARSE
│   ├── v1/
│   │   ├── resume.jsonl
│   │   ├── jd.jsonl
│   │   └── manifest.yaml
│   └── v2/            # future
├── matching/          # BENCH-MATCH
├── ranking/           # BENCH-RANK
├── summarization/     # BENCH-SUMMARY
├── generation/        # BENCH-GEN (interview questions)
└── search/            # BENCH-SEARCH
```

---

## Category specifications

### BENCH-PARSE (Parsing)

| Attribute | Value |
|-----------|-------|
| **Features** | Resume parsing, JD parsing, bulk parsing |
| **Input** | `raw_text` |
| **Gold output** | `expected_toon` (full TOON dict) |
| **Metrics** | `toon_validity`, `required_fields`, `field_f1`, `latency_ms` |
| **Min size** | 50 resumes + 50 JDs (v1) |
| **Evolution** | v2 adds: multi-page, non-English, sparse, scanned OCR cases |

**Providers evaluated:** Grok, Ollama, OpenAI, Claude, fine-tuned.

---

### BENCH-MATCH (Matching)

| Attribute | Value |
|-----------|-------|
| **Features** | Resume–JD matching, ATS scoring |
| **Input** | `resume_toon` + `jd_toon` |
| **Gold output** | `expected_score`, `expected_verdict`, `expected_reasoning` |
| **Metrics** | Score MAE, verdict accuracy, mandatory gate accuracy |
| **Min size** | 100 pairs (v1) |
| **Evolution** | v2 adds: edge cases where mandatory skills gate applies |

**Note:** Current HRMS ATS is rule-based (`ats_service.py`). Benchmark establishes baseline before LLM reranking (M10).

---

### BENCH-RANK (Ranking)

| Attribute | Value |
|-----------|-------|
| **Features** | Candidate ranking for a job |
| **Input** | `jd_toon` + `candidate_toon[]` |
| **Gold output** | `expected_ranking` (ordered candidate IDs) |
| **Metrics** | NDCG@10, MRR, Kendall tau |
| **Min size** | 20 jobs × 10 candidates (v1) |
| **Evolution** | v2 adds: diverse seniority spreads |

---

### BENCH-SUMMARY (Summarization)

| Attribute | Value |
|-----------|-------|
| **Features** | Resume summaries for recruiters |
| **Input** | `resume_toon` or `raw_text` |
| **Gold output** | `expected_summary` (human-written) |
| **Metrics** | ROUGE-L, faithfulness score, length compliance |
| **Min size** | 50 resumes (v1) |
| **Evolution** | v2 adds: executive vs technical summary styles |

---

### BENCH-GEN (Generation)

| Attribute | Value |
|-----------|-------|
| **Features** | Interview question generation |
| **Input** | `resume_toon` + `jd_toon` |
| **Gold output** | `expected_questions[]` with category tags |
| **Metrics** | Relevance score (LLM-judge + human), diversity, toxicity=0 |
| **Min size** | 30 pairs (v1) |
| **Evolution** | v2 adds: behavioral vs technical question mix |

---

### BENCH-SEARCH (AI Search)

| Attribute | Value |
|-----------|-------|
| **Features** | Semantic candidate/job search |
| **Input** | `query` + `corpus` |
| **Gold output** | `expected_result_ids[]` (ranked) |
| **Metrics** | Recall@10, MRR, latency_ms |
| **Min size** | 50 queries (v1) |
| **Evolution** | v2 adds: multi-filter queries (skills + location) |

---

## Benchmark lifecycle

```
Design → Annotate → Validate → Freeze → Register → Baseline eval → Gate
```

| Step | Action |
|------|--------|
| Design | Define category, size, difficulty tags |
| Annotate | Human gold labels; dual-review for v1 |
| Validate | Schema + inter-annotator agreement |
| Freeze | `frozen: true` in registry; no edits |
| Register | `registry/benchmarks/BENCH-{CAT}-v{N}.yaml` |
| Baseline | Run Grok + rule-based ATS; store in registry |
| Gate | Copy thresholds to `evaluation/regression/` |

---

## Difficulty and tags

Every benchmark record should include:

```yaml
difficulty: easy | medium | hard
tags: [multi-page, non-english, sparse-skills, executive, fresh-graduate]
```

Enables per-segment analysis in `evaluation/comparisons/`.

---

## Evaluation registry linkage

Each eval run registers in `registry/evaluations/`:

```yaml
id: EVAL-PARSE-20260625
benchmark: BENCH-PARSE-v1
providers: [PROV-GROK, PROV-OLLAMA]
models: [hrms-parsing-v1]
report: evaluation/reports/EVAL-PARSE-20260625/
passed_gates: true
```

---

## Multi-model comparison matrix

|  | Grok | Ollama FT | OpenAI | Claude | Rule ATS |
|--|------|-----------|--------|--------|----------|
| BENCH-PARSE | baseline | target | fallback | fallback | N/A |
| BENCH-MATCH | future | future | future | future | baseline |
| BENCH-RANK | future | future | N/A | N/A | N/A |
| BENCH-SUMMARY | baseline | target | compare | compare | N/A |
| BENCH-GEN | baseline | target | compare | compare | N/A |
| BENCH-SEARCH | N/A | embedding | embedding | N/A | keyword |

---

## Related documents

- [VERSIONING.md](VERSIONING.md)
- [dataset/lake/benchmark/README.md](../dataset/lake/benchmark/README.md)
- [registry/benchmarks/](../registry/benchmarks/) (future records)
- [adr/ADR-003-registry-design.md](adr/ADR-003-registry-design.md)
