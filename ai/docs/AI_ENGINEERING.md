# AI Engineering Handbook

Engineering standards for the HRMS AI platform. This document is the **operational reference** for environment setup, tooling, hardware, and reproducibility on developer workstations and training machines.

**Review cadence:** Quarterly, or when CUDA/PyTorch/Ollama major versions release.

---

## 1. Operating system

### Primary development environment

| Component | Requirement |
|-----------|-------------|
| OS | **Ubuntu 22.04 LTS** on WSL2 (Windows host) |
| WSL version | WSL2 with `systemd` enabled (for Ollama service) |
| Kernel | ≥ 6.6.x (matches current team environment) |

### Why Ubuntu WSL2

- CUDA toolkit compatibility for local QLoRA experimentation
- Ollama native Linux binaries
- Alignment with future CI/CD and cloud GPU instances (Ubuntu-based)
- Same path structure as production Linux deploys

### WSL2 setup checklist

```bash
# Verify WSL2
wsl --version

# Enable systemd ( /etc/wsl.conf )
[boot]
systemd=true

# Essential build tools
sudo apt update && sudo apt install -y build-essential git curl wget \
  python3.11 python3.11-venv python3-pip \
  poppler-utils libmagic1
```

---

## 2. NVIDIA GPU stack

### Recommended driver and CUDA

| Component | Version | Notes |
|-----------|---------|-------|
| NVIDIA Driver | **≥ 535.x** (Linux) | `nvidia-smi` must work inside WSL2 |
| CUDA Toolkit | **12.1** or **12.4** | Match PyTorch CUDA build |
| cuDNN | **8.9+** | Via PyTorch wheels or system |

### Verify GPU access

```bash
nvidia-smi
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

### GPU memory recommendations

| Workload | VRAM | Example GPU |
|----------|------|-------------|
| QLoRA 3B (4-bit) | ≥ 8 GB | RTX 3060 12GB, T4 |
| QLoRA 7B (4-bit) | ≥ 16 GB | RTX 4080, A10 |
| QLoRA 7B (4-bit) + long context | ≥ 24 GB | RTX 4090, A100 40GB |
| Full fine-tune 7B | ≥ 40 GB | A100 40GB+ |
| GGUF export | CPU RAM ≥ 32 GB | No GPU required |
| Ollama inference 7B q4 | ≥ 8 GB VRAM or 16 GB RAM | CPU fallback slower |

**Platform default:** QLoRA on **3B–7B instruct models** with 4-bit quantization.

---

## 3. Python environment

### Version

| Component | Version |
|-----------|---------|
| Python | **3.11.x** (matches `backend/venv`) |
| pip | ≥ 23.0 |
| venv | `python3.11 -m venv .venv` |

### Isolation rule

**Never install AI platform dependencies into `backend/venv`.** The AI workspace has its own `.venv` at `ai/.venv`.

```bash
cd ai
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 4. PyTorch stack

### Recommended versions (pin in training configs)

| Package | Version | Notes |
|---------|---------|-------|
| torch | **2.1.2** – **2.3.x** | Match CUDA build |
| torchvision | Match torch | |
| transformers | **4.38+** | |
| peft | **0.10+** | LoRA/QLoRA |
| trl | **0.8+** | SFT trainer |
| accelerate | **0.27+** | |
| bitsandbytes | **0.42+** | 4-bit quantization |
| datasets | **2.16+** | |

### Install example (CUDA 12.1)

```bash
pip install torch==2.1.2 torchvision --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
```

Record exact versions in `training/configs/{run_id}.yaml` → `environment:` block.

---

## 5. Flash Attention

| Setting | Recommendation |
|---------|----------------|
| Package | `flash-attn` (optional, compile from source) |
| When to use | Full fine-tune or long-context 7B+ |
| QLoRA default | **Not required** — bitsandbytes 4-bit sufficient for 3B–7B |
| WSL2 note | Compilation requires matching CUDA toolkit; allow 10–20 min build |

```bash
# Optional — only if needed
pip install flash-attn --no-build-isolation
```

Document in experiment README if Flash Attention was used — affects reproducibility.

---

## 6. Unsloth

| Setting | Recommendation |
|---------|----------------|
| Package | `unsloth` (optional accelerator) |
| When to use | Faster QLoRA training experiments |
| Platform stance | **Evaluate in experiments (EXP-*)** before platform adoption |
| Risk | Pins specific model architectures; may diverge from vanilla PEFT |

If adopted, record `unsloth` version in training config snapshot. Not a platform default until validated in M5.

---

## 7. Ollama

### Version

| Component | Version |
|-----------|---------|
| Ollama | **≥ 0.3.x** (latest stable) |

### Installation (WSL2)

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable ollama
sudo systemctl start ollama
ollama --version
```

### Platform conventions

| Setting | Value |
|---------|-------|
| Host | `http://localhost:11434` |
| Model naming | `hrms-{feature}-v{N}` |
| Default quant | `q4_K_M` |
| Context | 8192 (parsing); 4096 for smoke tests |

### Health check

```bash
ollama list
curl http://localhost:11434/api/tags
```

---

## 8. GGUF compatibility

### Toolchain

| Tool | Purpose |
|------|---------|
| `llama.cpp` | HF → GGUF conversion |
| `quantize` | q4_K_M, q8_0 quantization |

### Quantization matrix

| Quant | Size | Quality | Use case |
|-------|------|---------|----------|
| `q4_K_M` | Small | Good | **Production default** |
| `q8_0` | Medium | Better | Quality experiments |
| `f16` | Large | Best | Staging comparison |

### Filename convention

```
hrparser-v1-qwen2.5-7b-q4_k_m.gguf
```

See [VERSIONING.md](VERSIONING.md).

### Compatibility rule

GGUF must be loadable by target Ollama version before promotion to `staging`. Record Ollama version in `registry/deployments/`.

---

## 9. Git LFS

### When to use

| Asset | Git LFS? | Alternative |
|-------|----------|-------------|
| GGUF weights | Optional | Object storage + registry path |
| Merged HF models | **No** | Local/cache only |
| Raw resumes (PII) | **Never** | Gitignored |
| Benchmark JSONL | **No** | Gitignored; registry metadata only |
| Modelfiles | No | Committed (text) |

### Platform default

**Do not use Git LFS for model weights.** Store paths in `registry/`; binaries on local disk, NAS, or S3. LFS creates long-term lock-in and bloated clones.

If LFS is adopted for small shared artifacts (e.g. sample benchmark subset), document in ADR.

---

## 10. Storage recommendations

### Directory sizing (planning)

| Path | Estimated size (1 year) |
|------|-------------------------|
| `dataset/lake/raw/` | 10–50 GB |
| `dataset/lake/extracted/` – `normalized/` | 5–20 GB |
| `dataset/lake/jsonl/` | 1–5 GB |
| `models/base/` | 15–50 GB per base model |
| `models/merged/` | 15–50 GB per model |
| `models/gguf/` | 2–8 GB per quant |
| `training/runs/` | 20–100 GB (prune after merge) |

### Recommended layout

```
/mnt/ai-data/          # Large disk mount (WSL: /mnt/d/ai-data)
  ├── dataset/lake/
  ├── models/
  └── training/

/mnt/d/Projects/HR-Job-Portal-App/ai/   # Git repo (metadata only)
```

Symlink or set `AI_DATA_ROOT` env var (future) to separate code from data.

### Retention

| Artifact | Retention |
|----------|-----------|
| `training/runs/` | 90 days after merge |
| `training/checkpoints/` | Delete after promote |
| `evaluation/reports/` | Indefinite (small) |
| `models/gguf/` production | Indefinite |
| `models/gguf/` deprecated | 1 year |

---

## 11. Recommended project setup

```bash
# 1. Clone repo
cd /mnt/d/Projects/HR-Job-Portal-App

# 2. AI workspace venv
cd ai
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Environment
cp .env.example .env
# Edit: OLLAMA_HOST, API keys for benchmarking

# 4. Config templates
for f in configs/*.yaml.example; do
  cp "$f" "${f%.example}"
done

# 5. Verify GPU (if training)
python -c "import torch; print('CUDA:', torch.cuda.is_available())"

# 6. Verify Ollama (if deploying)
ollama list

# 7. Jupyter (optional)
python -m ipykernel install --user --name=hrms-ai
```

---

## 12. Experiment tracking

| Tool | Use |
|------|-----|
| WandB | Training metrics (optional) |
| `registry/` | Authoritative lineage |
| `training/logs/` | Local stdout backup |
| `experiments/` | Hypothesis and outcome |

Always duplicate critical metrics in `training/runs/{run_id}/metrics.json` — do not depend solely on WandB.

---

## 13. Security

- API keys in `ai/.env` only — never in configs, registry, or notebooks.
- Raw resumes contain PII — `dataset/lake/raw/` is gitignored.
- Benchmark JSONL is gitignored.
- Use read-only DB credentials for HRMS export (M3).

---

## Related documents

- [REPRODUCIBILITY.md](REPRODUCIBILITY.md)
- [VERSIONING.md](VERSIONING.md)
- [WORKFLOW.md](WORKFLOW.md)
- [ai/docs/ (governance standards in ADRs)README.md](../ai/docs/ (governance standards in ADRs)README.md)
