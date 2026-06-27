# Proposal Generator

Generates structured LLM proposals from silver-layer documents using the AI Runtime.

## What is this?

The Proposal Generator discovers silver documents, calls the AI Runtime for each document's task (e.g. `resume_parsing`), validates results, and writes proposal artifacts (`proposal.json`, metadata, reports).

## Why does it exist?

Building training and evaluation datasets requires machine-generated labels at scale. This module automates LLM inference over extracted text while preserving lineage and audit trails.

## What belongs here?

| Path | Purpose |
|------|---------|
| `engine/` | Discovery, processing, orchestration, runtime client |
| `exporters/` | Artifact writers |
| `validators/` | Input preflight checks |
| `cli/` | `python -m dataset.proposals.cli.generate_proposals` |
| `tests/` | Integration tests (mock runtime) |

## What should never be placed here?

- Runtime implementation → `ai/runtime/`
- Capability prompts/schemas → `ai/capabilities/`
- Document text extraction → `dataset/extraction/`

## Dependencies

| Consumes | From |
|----------|------|
| AI Runtime | `runtime/` (via `engine/runtime_client.py` only) |
| Silver documents | `dataset/lake/silver/` |
| Output | `dataset/lake/proposals/` |

## Consumers

| Consumer | Usage |
|----------|-------|
| Dataset Factory exporter (future) | JSONL training pairs |
| Evaluation benchmarks | Gold vs proposal comparison |

## Extension points

- Set `runtime_config_path` in config or CLI to use a custom runtime YAML
- Add doc types via `shared/constants.py` task map

## Quick start

```bash
cd ai
python -m dataset.proposals.cli.generate_proposals --help
pytest dataset/proposals/tests/
```

## Configuration

Default: `config.default.yaml`

```yaml
source_path: dataset/lake/silver/resumes
output_path: dataset/lake/proposals/resumes
```

## Related documentation

- [Runtime](../../runtime/README.md)
- [Dataset platform](../README.md)
