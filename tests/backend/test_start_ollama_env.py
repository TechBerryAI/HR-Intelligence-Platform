"""Node helper contract: start.js must not persist an implicit OLLAMA_MODEL."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_start_js_does_not_persist_implicit_ollama_model():
    script = ROOT / 'tests' / 'start' / 'test_start_ollama_env.js'
    result = subprocess.run(
        ['node', str(script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + '\n' + result.stderr
