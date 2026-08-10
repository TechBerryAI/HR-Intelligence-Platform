# Engineering Workflow

## Productized vs capability packs

| Surface | Status |
|---------|--------|
| Resume / JD parsing (+ ATS via HRMS adapter) | **Production HRMS path** |
| Matching, chat, interview-generation, ranking/summary | **Capability packs** in `ai/` — not fully productized app services |

Market and roadmap claims should match this table. See [docs/06-AI.md](06-AI.md) and [ADRS.md](ADRS.md) (ADR-006).

## Standard workflow

### 1. Research (optional)

```
experiments/{YYYY-MM-DD}_{slug}/
  → hypothesis, config, notes
  → registry/experiments/{id}.yaml on completion
```

### 2. Acquire raw data

```bash
# Manual
cp resumes/*.pdf ai/dataset/lake/raw/resumes/

# Future: HRMS export
python scripts/export_hrms_dataset.py --output dataset/lake/raw/
```

### 3. Run preprocessing pipeline

```
raw/ → extract/ → cleaned/ → normalized/ → validate/ → jsonl/
```

Each stage writes `manifest.yaml`. Register dataset version in `registry/datasets/`.

### 4. Curate benchmark (parallel)

```
dataset/lake/benchmark/parsing/v1/   # frozen, never train on this
registry/benchmarks/parsing-v1.yaml
```

### 5. Train

```bash
# Snapshot config
cp configs/training.yaml training/configs/{run_id}.yaml

# Future
python scripts/train_qlora.py --config training/configs/{run_id}.yaml
```

Promote: `models/adapters/` → `models/merged/` → `models/gguf/`

### 6. Deploy locally

```bash
# Future
python scripts/deploy_ollama.py --model hrms-parsing-v1
```

Modelfile: `exports/modelfiles/hrms-parsing-v1.Modelfile`

### 7. Evaluate

```bash
# Future
python scripts/benchmark_providers.py --config configs/evaluation.yaml
```

Review: `evaluation/reports/{eval_id}/summary.json`
Compare: `evaluation/comparisons/`
Gate: `evaluation/regression/baseline.yaml`

### 8. Register and promote

```yaml
# registry/models/hrms-parsing-v1.yaml
status: staging  # → production after HRMS integration
```

---

## Review checklist

- [ ] No secrets committed
- [ ] Dataset version in registry with checksums
- [ ] Training config snapshot exists
- [ ] Benchmark not mutated (new version if needed)
- [ ] Prompt version bumped if text changed
- [ ] Eval report linked in registry
- [ ] No `backend/` or `frontend/` changes (until M5)

---

## Related documents

- [DATA_PIPELINE.md](DATA_PIPELINE.md) — canonical pipeline
- [REPRODUCIBILITY.md](REPRODUCIBILITY.md) — replay guide
- [CONVENTIONS.md](CONVENTIONS.md) — naming standards
