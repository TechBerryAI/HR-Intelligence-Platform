"""Node helper overlay + hardware CLI must resolve the same Ollama model."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.parser.engine import hardware as hw
from app.ai.parser.engine.hardware import PERFORMANCE_PROFILES

MODEL_KEYS = ('OLLAMA_MODEL', 'HCIP_HARDWARE_PROFILE', 'HCIP_VRAM_MB')


def hardware_helper_env(env_map: dict, process_env: dict) -> dict:
    """Mirror start.js hardwareHelperEnv (process wins; .env fills blanks)."""
    env = dict(process_env)
    for key in MODEL_KEYS:
        from_process = str(process_env.get(key) or '').strip()
        if from_process:
            env[key] = from_process
            continue
        from_file = str((env_map or {}).get(key) or '').strip()
        if from_file:
            env[key] = from_file
        else:
            env.pop(key, None)
    return env


def _base_process_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in MODEL_KEYS}
    env['HCIP_SKIP_DOTENV'] = '1'
    env['PYTHONPATH'] = str(BACKEND_ROOT)
    env['PATH'] = os.environ.get('PATH', '/usr/bin')
    return env


def _spawn_hint(overlay: dict[str, str]) -> str:
    result = subprocess.run(
        [sys.executable, '-m', 'app.ai.parser.engine.hardware'],
        cwd=str(BACKEND_ROOT),
        env=overlay,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + '\n' + result.stderr
    return result.stdout.strip().splitlines()[-1].strip()


def _inprocess_hint(overlay: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> str:
    for key in MODEL_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key in MODEL_KEYS:
        if key in overlay and str(overlay[key]).strip():
            monkeypatch.setenv(key, overlay[key])
    hw.reset_hardware_env_for_tests()
    try:
        return hw.detect_hardware_profile().preferred_model_hint
    finally:
        hw.reset_hardware_env_for_tests()


def _assert_spawn_matches(env_map: dict, monkeypatch: pytest.MonkeyPatch, expected: str | None = None):
    overlay = hardware_helper_env(env_map, _base_process_env())
    spawned = _spawn_hint(overlay)
    inproc = _inprocess_hint(overlay, monkeypatch)
    assert spawned == inproc
    if expected is not None:
        assert spawned == expected
    return spawned


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


def test_overlay_env_file_profile_when_process_unset():
    overlay = hardware_helper_env(
        {'HCIP_HARDWARE_PROFILE': 'cpu'},
        {'PATH': '/usr/bin', 'OLLAMA_MODEL': ''},
    )
    assert overlay['HCIP_HARDWARE_PROFILE'] == 'cpu'
    assert 'OLLAMA_MODEL' not in overlay


def test_overlay_process_model_wins():
    overlay = hardware_helper_env(
        {'OLLAMA_MODEL': 'file:14b', 'HCIP_HARDWARE_PROFILE': 'cpu'},
        {'OLLAMA_MODEL': 'shell:7b'},
    )
    assert overlay['OLLAMA_MODEL'] == 'shell:7b'


def test_contract_a_explicit_model(monkeypatch):
    _assert_spawn_matches({'OLLAMA_MODEL': 'custom:pin'}, monkeypatch, 'custom:pin')


def test_contract_b_cpu_profile(monkeypatch):
    _assert_spawn_matches(
        {'HCIP_HARDWARE_PROFILE': 'cpu'},
        monkeypatch,
        PERFORMANCE_PROFILES['cpu'].preferred_model,
    )


def test_contract_c_gpu_mid_profile(monkeypatch):
    _assert_spawn_matches(
        {'HCIP_HARDWARE_PROFILE': 'gpu_mid'},
        monkeypatch,
        PERFORMANCE_PROFILES['gpu_mid'].preferred_model,
    )


def test_contract_d_vram_override(monkeypatch):
    _assert_spawn_matches(
        {'HCIP_VRAM_MB': '8192'},
        monkeypatch,
        PERFORMANCE_PROFILES['gpu_mid'].preferred_model,
    )


def test_contract_e_no_override_same_model(monkeypatch):
    spawned = _assert_spawn_matches({}, monkeypatch)
    assert spawned
