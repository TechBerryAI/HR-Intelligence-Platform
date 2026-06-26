# AI Services Layer (Future — M8–M10)

## Purpose

Feature-level AI capabilities exposed as discrete services. Each service maps to an HRMS product feature.

## Planned services

| Service | Input | Output | Benchmark category |
|---------|-------|--------|-------------------|
| `ResumeParseService` | Raw document | Resume TOON | `BENCH-PARSE` |
| `JDParseService` | Raw document | JD TOON | `BENCH-PARSE` |
| `BulkParseService` | Document batch | TOON collection | `BENCH-PARSE` |
| `ResumeMatchService` | Resume TOON + JD TOON | Match score + reasoning | `BENCH-MATCH` |
| `CandidateRankService` | Candidates + JD | Ranked list | `BENCH-RANK` |
| `ResumeSummaryService` | Resume TOON | Summary text | `BENCH-SUMMARY` |
| `InterviewQuestionService` | Resume + JD TOON | Question list | `BENCH-GEN` |
| `SkillExtractService` | Resume text | Normalized skills | `BENCH-PARSE` |
| `AISearchService` | Query + corpus | Ranked results | `BENCH-SEARCH` |
| `ChatAssistantService` | Conversation + context | Response | `BENCH-GEN` |

## Design rules

1. Services consume **data contracts** ([DATA_CONTRACTS.md](../../docs/DATA_CONTRACTS.md)), not raw DB rows.
2. Services call **inference layer**, never providers directly.
3. Each service has a registered prompt (`registry/prompts/`) and benchmark (`datasets/benchmark/`).
4. Service versions are independent — parsing v2 does not require matching v2.

## Milestone

Scaffold in M8; expand through M10.
