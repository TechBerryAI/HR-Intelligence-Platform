"""Operator / profile / fallback precedence for AI performance profiles."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.parser.engine.hardware import (  # noqa: E402
    DEFAULT_MAX_TOKENS_RESUME_JD,
    PERFORMANCE_PROFILES,
)


def test_profile_defaults_are_centralized():
    assert PERFORMANCE_PROFILES['gpu_high'].preferred_model == 'qwen2.5:14b-instruct'
    assert PERFORMANCE_PROFILES['gpu_mid'].preferred_model == 'qwen2.5:7b-instruct'
    assert PERFORMANCE_PROFILES['unknown'].preferred_model == 'qwen2.5:7b-instruct'
    assert PERFORMANCE_PROFILES['cpu'].preferred_model == 'qwen2.5:3b-instruct'
    assert PERFORMANCE_PROFILES['gpu_high'].ollama_max_concurrent == 3
    assert PERFORMANCE_PROFILES['gpu_mid'].ollama_max_concurrent == 2
    assert PERFORMANCE_PROFILES['unknown'].ollama_max_concurrent == 1
    assert PERFORMANCE_PROFILES['cpu'].ollama_max_concurrent == 1
    for spec in PERFORMANCE_PROFILES.values():
        assert spec.max_tokens_resume_jd == DEFAULT_MAX_TOKENS_RESUME_JD
