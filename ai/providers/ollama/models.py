"""Ollama API response models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OllamaModelInfo:
    """Discovered Ollama model metadata."""

    name: str
    size: int | None = None
    modified_at: str | None = None
    digest: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> OllamaModelInfo:
        return cls(
            name=str(payload.get("name", "")),
            size=payload.get("size"),
            modified_at=payload.get("modified_at"),
            digest=payload.get("digest"),
            details=payload.get("details") or {},
        )


@dataclass(frozen=True)
class OllamaChatResponse:
    """Normalized Ollama chat completion."""

    content: str
    model: str
    done: bool = True
    prompt_eval_count: int | None = None
    eval_count: int | None = None
    total_duration_ns: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def token_usage(self) -> dict[str, int] | None:
        if self.prompt_eval_count is None and self.eval_count is None:
            return None
        prompt_tokens = int(self.prompt_eval_count or 0)
        completion_tokens = int(self.eval_count or 0)
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> OllamaChatResponse:
        message = payload.get("message") or {}
        content = message.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        return cls(
            content=content,
            model=str(payload.get("model", "")),
            done=bool(payload.get("done", True)),
            prompt_eval_count=payload.get("prompt_eval_count"),
            eval_count=payload.get("eval_count"),
            total_duration_ns=payload.get("total_duration"),
            raw=payload,
        )


@dataclass(frozen=True)
class OllamaStreamChunk:
    """Single streaming chunk from Ollama."""

    content: str
    done: bool
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> OllamaStreamChunk:
        message = payload.get("message") or {}
        content = message.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        return cls(
            content=content,
            done=bool(payload.get("done", False)),
            raw=payload,
        )


@dataclass(frozen=True)
class ProviderMetadata:
    """Provider capability and connection metadata."""

    provider_id: str
    provider_type: str
    base_url: str
    configured: bool
    available_models: tuple[str, ...] = ()
    supports_streaming: bool = True
    supports_structured_output: bool = True
