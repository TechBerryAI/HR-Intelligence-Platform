# Split

**Stage 5** — produce train/val/test JSONL for training and provider benchmarking.

## Inputs

| Source | Format |
|--------|--------|
| `datasets/normalized/` (validated) | JSON with `toon` + `text` |

## Outputs

| Destination | Format |
|-------------|--------|
| `datasets/jsonl/{version}/train.jsonl` | Instruction tuning format |
| `datasets/jsonl/{version}/val.jsonl` | Validation during training |
| `datasets/jsonl/{version}/test.jsonl` | Held-out test (not benchmark) |
| `datasets/jsonl/{version}/manifest.yaml` | Split metadata |

## Responsibilities

1. Stratified split by `doc_type` (default 80/10/10).
2. Ensure no `source_hash` leakage across splits.
3. Format records as instruction triples using `prompts/*.yaml` templates.
4. Register dataset version in `registry/datasets/`.

## JSONL record format

```json
{
  "id": "uuid",
  "doc_type": "resume",
  "instruction": "<system prompt>",
  "input": "<cleaned text>",
  "output": "<toon_dumps(toon)>",
  "metadata": {
    "dataset_version": "parsing-v1",
    "prompt_version": "1.0.0",
    "source_hash": "sha256:..."
  }
}
```

## Versioning

Directory naming: `datasets/jsonl/parsing-v1/`, `datasets/jsonl/parsing-v2/`.

Register in `registry/datasets/parsing-v1.yaml`.

## Future scripts

| Script | Purpose |
|--------|---------|
| `scripts/split_dataset.py` | Create versioned JSONL splits |

## Downstream consumers

- `training/` — QLoRA fine-tuning
- `evaluation/` — provider benchmarking (non-benchmark splits)
- `experiments/` — hypothesis testing
