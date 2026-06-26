# Provider Management Layer (Future — M8)

## Purpose

Pluggable LLM provider implementations with unified interface. **Conceptual home for provider code** — not to be confused with `registry/providers/` (metadata).

## Planned providers

| Provider | Role | Registry ID |
|----------|------|-------------|
| Ollama | Primary (fine-tuned local) | `PROV-OLLAMA` |
| Grok/X.AI | Secondary / baseline | `PROV-GROK` |
| OpenAI | Fallback | `PROV-OPENAI` |
| Claude | Fallback | `PROV-ANTHROPIC` |
| Gemini | Fallback | `PROV-GEMINI` |

## Responsibilities (planned)

- Implement common `LLMProvider` interface (M8)
- Health checks and capability discovery
- Key rotation (Grok multi-key via existing `llm_key_manager` pattern)
- Cost and latency reporting to `platform/monitoring/`

## Configuration

Runtime config: `configs/providers.yaml`
Registry metadata: `registry/providers/`

## Constraint

No provider code until **M8**. Evaluation in M6 uses scripts that will later migrate here.
