# AI Platform Layers (Future)

The HRMS AI workspace is an **AI platform**, not a training repository. Training is one capability among many. This directory documents where future platform components will live — **no implementation exists yet**.

## Platform stack (target state)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  HRMS Application (backend/frontend) — consumes platform via gateway    │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────────┐
│  platform/services/          AI feature APIs (parse, match, rank, chat)   │
├─────────────────────────────────────────────────────────────────────────┤
│  platform/orchestration/     Multi-step workflows (apply → parse → ATS) │
├─────────────────────────────────────────────────────────────────────────┤
│  platform/inference/         Model routing, batching, caching           │
├─────────────────────────────────────────────────────────────────────────┤
│  platform/providers/         Ollama, Grok, OpenAI, Claude, Gemini        │
├─────────────────────────────────────────────────────────────────────────┤
│  platform/monitoring/        Latency, cost, quality drift, alerts         │
└─────────────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
   datasets/              models/ + registry/     evaluation/
   preprocessing/         training/               experiments/
```

## Subdirectories

| Directory | Future responsibility | Milestone |
|-----------|----------------------|-----------|
| [inference/](inference/README.md) | Request routing, batch inference, response cache | M8 (LLM Gateway) |
| [services/](services/README.md) | Feature-level AI services (parsing, matching, chat) | M8–M10 |
| [orchestration/](orchestration/README.md) | DAG workflows, retries, fallbacks | M9+ |
| [providers/](providers/README.md) | Provider adapter implementations | M8 |
| [monitoring/](monitoring/README.md) | Metrics, drift detection, cost tracking | M11 |

## Design principle

**Business logic stays in HRMS until M9.** Platform layers are built and validated inside `ai/` first, then integrated via the LLM Gateway (M8) without changing route handlers.

## Related documents

- [docs/PLATFORM_VISION.md](../docs/PLATFORM_VISION.md)
- [docs/adr/ADR-006-ai-platform-vision.md](../docs/adr/ADR-006-ai-platform-vision.md)
