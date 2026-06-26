# Prompt templates

Versioned system and user prompts for resume and JD parsing. These mirror the production prompts in `backend/llm_service.py` and serve as the **single source of truth** for:

- Fine-tuning instruction data
- Evaluation benchmarks across providers
- Ollama Modelfile system messages
- Future backend provider adapter (M3+)

## Files

| Template | Purpose |
|----------|---------|
| `resume_parser.yaml.example` | Resume → TOON extraction |
| `jd_parser.yaml.example` | Job description → TOON extraction |

## Versioning

Increment `version` in each YAML when changing prompt text. Record changes in `docs/ROADMAP.md` or a dedicated changelog. Evaluation runs must log the prompt version used.

## Usage

```bash
cp prompts/resume_parser.yaml.example prompts/resume_parser.yaml
cp prompts/jd_parser.yaml.example prompts/jd_parser.yaml
```

Reference paths from `configs/evaluation.yaml` and `configs/ollama.yaml`.
