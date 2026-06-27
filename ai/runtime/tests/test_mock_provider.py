"""Mock provider tests."""

from __future__ import annotations

import json

import pytest

from runtime.exceptions import ProviderError
from runtime.interfaces.types import InferenceRequest
from providers.mock import MockProvider


def test_mock_provider_success() -> None:
    provider = MockProvider("mock", {"enabled": True, "default_latency_ms": 0})
    response = provider.complete(
        InferenceRequest(
            task="resume_parsing",
            prompt="parse",
            input_text="Jane Doe resume",
            model="mock-resume-parser-v1",
            schema_id="resume_v1",
        )
    )
    payload = json.loads(response.content)
    assert payload["task"] == "resume_parsing"
    assert payload["status"] == "mock_success"
    assert response.provider_id == "mock"


def test_mock_provider_simulated_failure_then_success() -> None:
    provider = MockProvider(
        "mock",
        {"enabled": True, "default_latency_ms": 0, "fail_until_attempt": 1},
    )
    with pytest.raises(ProviderError):
        provider.complete(
            InferenceRequest(
                task="resume_parsing",
                prompt="parse",
                input_text="data",
                model="mock-resume-parser-v1",
                schema_id="resume_v1",
                metadata={"attempt": 1},
            )
        )
    response = provider.complete(
        InferenceRequest(
            task="resume_parsing",
            prompt="parse",
            input_text="data",
            model="mock-resume-parser-v1",
            schema_id="resume_v1",
            metadata={"attempt": 2},
        )
    )
    assert json.loads(response.content)["status"] == "mock_success"


def test_mock_provider_health_check() -> None:
    provider = MockProvider("mock", {"enabled": True})
    health = provider.health_check()
    assert health.available is True
    assert health.provider_id == "mock"
