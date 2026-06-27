# AI Platform Vision

The HRMS AI workspace is not a model training folder. It is an **enterprise AI platform** that will power recruitment intelligence for years.

---

## Paradigm shift

| Training-centric view (reject) | Platform-centric view (adopt) |
|-------------------------------|------------------------------|
| "Fine-tune a model for parsing" | "Operate a parsing **service** with measurable SLAs" |
| "Export GGUF to Ollama" | "Manage a **deployment registry** with rollback" |
| "Compare Grok vs local model" | "Run **evaluation registry** with regression gates" |
| "Write prompts in a file" | "Govern prompts in a **prompt registry** with semver" |
| "Call OpenAI API" | "Route through **provider management** with fallback" |

---

## Platform capabilities (target state)

```
┌────────────────────────────────────────────────────────────────────────┐
│                         HRMS AI PLATFORM                               │
├──────────────┬──────────────┬──────────────┬──────────────┬────────────┤
│    Data      │   Training   │  Inference   │  Evaluation  │ Governance │
│   Platform   │   Platform   │   Platform   │   Platform   │  Platform  │
├──────────────┼──────────────┼──────────────┼──────────────┼────────────┤
│ dataset/lake/    │ training/    │ platform/    │ evaluation/  │ registry/  │
│ preprocess/  │ models/      │ inference/   │ benchmarks/  │ ai/docs/ (governance standards in ADRs)│
│ contracts    │ experiments/ │ services/    │ regression/  │ adr/       │
│ artifacts    │              │ providers/   │ comparisons/ │ versioning │
│              │              │ orchestration│              │            │
│              │              │ monitoring/  │              │            │
└──────────────┴──────────────┴──────────────┴──────────────┴────────────┘
```

---

## Feature map

| HRMS Feature | Platform service | Data contract | Benchmark |
|--------------|-----------------|---------------|-----------|
| Resume parsing | `ResumeParseService` | Resume | BENCH-PARSE |
| JD parsing | `JDParseService` | JD | BENCH-PARSE |
| Bulk parsing | `BulkParseService` | Resume | BENCH-PARSE |
| Resume matching | `ResumeMatchService` | Resume + JD | BENCH-MATCH |
| Candidate ranking | `CandidateRankService` | Candidate + JD | BENCH-RANK |
| AI search | `AISearchService` | Skills + text | BENCH-SEARCH |
| Interview questions | `InterviewQuestionService` | Resume + JD | BENCH-GEN |
| Resume summaries | `ResumeSummaryService` | Resume | BENCH-SUMMARY |
| Skill extraction | `SkillExtractService` | Skills | BENCH-PARSE |
| Skill normalization | `SkillNormalizeService` | Skills | BENCH-PARSE |
| Salary intelligence | `SalaryIntelService` | JD + market data | TBD |
| AI chat assistant | `ChatAssistantService` | Multi | BENCH-GEN |

---

## Platform layers (implementation timeline)

| Layer | Directory | Milestone |
|-------|-----------|-----------|
| Data contracts | `docs/DATA_CONTRACTS.md` | M2 |
| Dataset engineering | `dataset/lake/`, `dataset/` | M3–M4 |
| Training | `training/`, `models/` | M5 |
| Evaluation | `evaluation/`, benchmarks | M6 |
| Deployment | `exports/`, `models/gguf/` | M7 |
| LLM Gateway | `runtime/`, `providers/` | M8 |
| HRMS integration | `exports/integration/` | M9 |
| Advanced features | `platform/services/` | M10 |
| Monitoring | `platform/monitoring/` | M11 |

---

## Integration boundary

```
HRMS backend (business logic, routes, DB)
        │
        │  HTTP / internal adapter (M9)
        ▼
LLM Gateway (M8) — routing, fallback, caching
        │
        ├── Ollama (primary)
        ├── Grok (fallback)
        └── Cloud providers
```

**Rule:** HRMS route handlers do not change. Only `llm_service.py` internals adapt in M9.

---

## Success criteria (platform maturity)

| Level | Criteria |
|-------|----------|
| L1 | Architecture documented, contracts defined |
| L2 | Data pipeline operational, artifacts traced |
| L3 | Parsing model trained, benchmark passed |
| L4 | Ollama deployed, eval registry complete |
| L5 | LLM Gateway operational in `ai/` |
| L6 | HRMS integrated with feature flag |
| L7 | Second feature (matching/summary) on platform |
| L8 | Monitoring and continuous improvement loop |

---

## Related documents

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [ROADMAP.md](ROADMAP.md)
- [platform/README.md](../platform/README.md)
- [adr/ADR-006-ai-platform-vision.md](adr/ADR-006-ai-platform-vision.md)
