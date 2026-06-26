# Experiments

Hypothesis-driven research workspace. Experiments are **exploratory** — only outcomes promoted to `training/runs/` and `registry/models/` become production candidates.

## Purpose

Machine learning progress depends on structured experimentation:
- Prompt A/B tests before updating `prompts/`
- Base model comparisons before committing GPU time
- QLoRA rank sweeps
- Provider quality probes before fine-tuning investment

## Directory layout

```
experiments/
├── README.md
├── _template/              # Copy to start a new experiment
└── {YYYY-MM-DD}_{slug}/    # One directory per experiment
```

## Experiment directory structure

```
experiments/2026-06-25_parsing-qlora-baseline/
├── README.md               # Hypothesis, method, outcome (required)
├── config.yaml             # Parameters varied in this experiment
├── notes.md                # Running observations
├── artifacts/              # Small outputs (gitignored if large)
└── links.yaml              # Pointers to training runs, eval reports
```

## README template (`_template/README.md`)

```markdown
# Experiment: {title}

**ID:** {YYYY-MM-DD}_{slug}
**Status:** planned | running | completed | abandoned
**Author:** {name}
**Date:** {YYYY-MM-DD}

## Hypothesis

{What you expect to happen and why}

## Method

{What you will change — one variable at a time when possible}

## Variables

| Variable | Control | Experiment |
|----------|---------|------------|
| base_model | Llama 3.2 3B | ... |

## Success criteria

{Measurable thresholds}

## Outcome

{Filled after completion — link to registry/experiments/ entry}

## Next steps

{Promote to training / abandon / iterate}
```

## Naming convention

```
{YYYY-MM-DD}_{kebab-case-slug}
```

Examples:
- `2026-06-25_parsing-qlora-baseline`
- `2026-07-01_prompt-v2-ablation`
- `2026-07-10_grok-vs-llama-zero-shot`

## Lifecycle

```
planned → running → completed | abandoned
                ↓
         registry/experiments/{id}.yaml
                ↓
    (if successful) training/runs/ + registry/models/
```

## Git policy

- Experiment README and config: **committed**
- Large artifacts: **gitignored**
- Always register outcome in `registry/experiments/` when completed

## Relationship to training

| Experiments | Training |
|-------------|----------|
| Exploratory, may fail | Production-oriented runs |
| Multiple variants | One config snapshot per run |
| Informal notes | Formal metrics in `training/logs/` |
| May not produce a model | Always produces artifacts |

## Feature experiments (long-term)

| Feature | Example experiment |
|---------|-------------------|
| Parsing | QLoRA rank sweep, prompt v2 ablation |
| Matching | Embedding model comparison |
| Summarization | Summary length vs faithfulness |
| Interview Qs | Temperature sweep for diversity |
| Skill normalization | Ontology mapping strategies |
