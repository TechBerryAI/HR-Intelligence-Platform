#!/usr/bin/env bash
# Run the resume parsing benchmark with the backend's own interpreter.
#
# Why this exists: the benchmark must run inside WSL because the OCR engine
# (RapidOCR) is only installed in the Linux backend venv, not Windows Python.
# This wraps that WSL/venv/PYTHONPATH plumbing so the day-to-day command is
# short. See ai/eval/resume_benchmark/README.md for what the flags do.
#
# PYTHONPYCACHEPREFIX redirects .pyc bytecode caching to a scratch dir instead
# of the venv's own __pycache__: editing app/ai source from the Windows side
# and immediately re-running through WSL has been observed to reuse stale
# bytecode (the 9p/NTFS mtime Python compares against __pycache__ can lag a
# fresh Windows-side edit), silently benchmarking old code. This avoids that
# without ever touching the venv's own cache — see AGENTS.md on not
# hand-deleting __pycache__ trees.
#
# Usage (from the repo root, in PowerShell or bash on Windows):
#   scripts/run-resume-benchmark.sh
#   scripts/run-resume-benchmark.sh --case naukri_ashishpandey_3y_6m__dac285 --show
#   scripts/run-resume-benchmark.sh --gate
#   scripts/run-resume-benchmark.sh --set-baseline --write-thresholds
set -euo pipefail

WSL_DISTRO="${WSL_DISTRO:-Ubuntu}"
PROJECT_DIR_WSL="/mnt/d/Projects/HR-Intelligence-Platform"

# Already inside WSL/Linux (e.g. CI) — skip the wsl.exe hop and run directly.
if [ "$(uname -s 2>/dev/null)" = "Linux" ]; then
  cd "$(dirname "$0")/.."
  exec env PYTHONPATH=apps/backend PYTHONPYCACHEPREFIX=/tmp/hcip_pycache \
    ./apps/backend/venv/bin/python \
    ai/eval/resume_benchmark/run_benchmark.py --workers 4 "$@"
fi

# Safely quote each argument for the remote bash -lc string.
REMOTE_ARGS=""
for arg in "$@"; do
  REMOTE_ARGS="$REMOTE_ARGS $(printf '%q' "$arg")"
done

exec wsl -d "$WSL_DISTRO" -- bash -lc "cd '$PROJECT_DIR_WSL' && PYTHONPATH=apps/backend PYTHONPYCACHEPREFIX=/tmp/hcip_pycache ./apps/backend/venv/bin/python ai/eval/resume_benchmark/run_benchmark.py --workers 4$REMOTE_ARGS"
