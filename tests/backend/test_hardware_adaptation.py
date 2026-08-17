"""Hardware-adaptive model selection and performance profile precedence."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
for p in (str(BACKEND_ROOT), str(BACKEND_ROOT / 'app')):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.ai.parser.engine import hardware as hw
from app.ai.parser.engine.hardware import PERFORMANCE_PROFILES


@pytest.fixture(autouse=True)
def _reset_hw(monkeypatch):
    hw.reset_hardware_env_for_tests()
    monkeypatch.delenv('OLLAMA_MODEL', raising=False)
    monkeypatch.delenv('HCIP_HARDWARE_PROFILE', raising=False)
    monkeypatch.delenv('HCIP_VRAM_MB', raising=False)
    monkeypatch.delenv('OLLAMA_MAX_CONCURRENT', raising=False)
    monkeypatch.setattr(hw, '_gpu_present_unverified', lambda: False)
    monkeypatch.setattr(hw, '_nvidia_smi_vram_mb', lambda: None)
    yield
    hw.reset_hardware_env_for_tests()


def test_explicit_ollama_model_wins(monkeypatch):
    monkeypatch.setenv('OLLAMA_MODEL', 'custom:pin')
    monkeypatch.setenv('HCIP_HARDWARE_PROFILE', 'cpu')
    profile = hw.detect_hardware_profile()
    assert profile.preferred_model_hint == 'custom:pin'
    assert profile.name == 'cpu'


def test_high_profile_selects_high_model(monkeypatch):
    monkeypatch.setenv('HCIP_HARDWARE_PROFILE', 'gpu_high')
    profile = hw.detect_hardware_profile()
    assert profile.name == 'gpu_high'
    assert profile.preferred_model_hint == PERFORMANCE_PROFILES['gpu_high'].preferred_model
    assert profile.ollama_max_concurrent == 3


def test_mid_profile_selects_mid_model(monkeypatch):
    monkeypatch.setenv('HCIP_HARDWARE_PROFILE', 'gpu_mid')
    profile = hw.detect_hardware_profile()
    assert profile.name == 'gpu_mid'
    assert profile.preferred_model_hint == PERFORMANCE_PROFILES['gpu_mid'].preferred_model


def test_cpu_profile_selects_low_model(monkeypatch):
    monkeypatch.setenv('HCIP_HARDWARE_PROFILE', 'cpu')
    profile = hw.detect_hardware_profile()
    assert profile.name == 'cpu'
    assert profile.preferred_model_hint == PERFORMANCE_PROFILES['cpu'].preferred_model
    assert profile.ollama_max_concurrent == 1


def test_unknown_profile_is_mid_safe(monkeypatch):
    monkeypatch.setenv('HCIP_HARDWARE_PROFILE', 'unknown')
    profile = hw.detect_hardware_profile()
    assert profile.name == 'unknown'
    assert profile.preferred_model_hint == PERFORMANCE_PROFILES['gpu_mid'].preferred_model
    assert profile.ollama_max_concurrent == 1


def test_explicit_vram_high(monkeypatch):
    monkeypatch.setenv('HCIP_VRAM_MB', '24576')
    profile = hw.detect_hardware_profile()
    assert profile.name == 'gpu_high'
    assert profile.vram_mb == 24576


def test_explicit_vram_mid(monkeypatch):
    monkeypatch.setenv('HCIP_VRAM_MB', '8192')
    profile = hw.detect_hardware_profile()
    assert profile.name == 'gpu_mid'


def test_explicit_vram_zero_is_cpu(monkeypatch):
    monkeypatch.setenv('HCIP_VRAM_MB', '0')
    monkeypatch.setattr(hw, '_gpu_present_unverified', lambda: True)
    profile = hw.detect_hardware_profile()
    assert profile.name == 'cpu'


def test_nvidia_unavailable_does_not_crash(monkeypatch):
    monkeypatch.setattr(hw, '_nvidia_smi_vram_mb', lambda: None)
    monkeypatch.setattr(hw, '_gpu_present_unverified', lambda: False)
    profile = hw.detect_hardware_profile()
    assert profile.name == 'cpu'
    assert profile.preferred_model_hint == PERFORMANCE_PROFILES['cpu'].preferred_model


def test_unverified_gpu_is_unknown_not_cpu(monkeypatch):
    monkeypatch.setattr(hw, '_nvidia_smi_vram_mb', lambda: None)
    monkeypatch.setattr(hw, '_gpu_present_unverified', lambda: True)
    profile = hw.detect_hardware_profile()
    assert profile.name == 'unknown'
    assert profile.vram_mb == 0
    assert profile.preferred_model_hint == PERFORMANCE_PROFILES['unknown'].preferred_model


def test_blank_ollama_model_is_unset(monkeypatch):
    monkeypatch.setenv('OLLAMA_MODEL', '   ')
    monkeypatch.setenv('HCIP_HARDWARE_PROFILE', 'cpu')
    assert not hw.ollama_model_is_explicit()
    profile = hw.apply_hardware_env()
    assert os.environ['OLLAMA_MODEL'] == PERFORMANCE_PROFILES['cpu'].preferred_model
    assert profile.preferred_model_hint == PERFORMANCE_PROFILES['cpu'].preferred_model


def test_apply_does_not_override_explicit_model(monkeypatch):
    monkeypatch.setenv('OLLAMA_MODEL', 'kept:model')
    monkeypatch.setenv('HCIP_HARDWARE_PROFILE', 'gpu_high')
    hw.apply_hardware_env()
    assert os.environ['OLLAMA_MODEL'] == 'kept:model'


def test_conservative_fallback_when_no_signals(monkeypatch):
    profile = hw.detect_hardware_profile()
    assert profile.name == 'cpu'
    assert profile.detection_source == 'conservative-fallback'


def test_ollama_slot_releases_on_failure(monkeypatch):
    from app.ai.parser.engine.ollama_limit import ollama_slot, reset_ollama_limit_for_tests

    monkeypatch.setenv('OLLAMA_MAX_CONCURRENT', '1')
    reset_ollama_limit_for_tests()
    with pytest.raises(RuntimeError):
        with ollama_slot():
            raise RuntimeError('boom')
    with ollama_slot():
        pass
    reset_ollama_limit_for_tests()
