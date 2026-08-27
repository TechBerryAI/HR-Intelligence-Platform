"""HTTP client for the Ollama API."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx

from providers.ollama.config import OllamaProviderConfig
from providers.ollama.exceptions import map_httpx_error, map_http_status
from providers.ollama.models import OllamaChatResponse, OllamaModelInfo, OllamaStreamChunk

logger = logging.getLogger(__name__)

_IN_FLIGHT: set[httpx.Client] = set()
_IN_FLIGHT_LOCK = threading.Lock()


@contextmanager
def _track_client(client: httpx.Client):
    with _IN_FLIGHT_LOCK:
        _IN_FLIGHT.add(client)
    try:
        yield client
    finally:
        with _IN_FLIGHT_LOCK:
            _IN_FLIGHT.discard(client)


def abort_in_flight_requests() -> int:
    """Close HTTP clients for in-flight Ollama calls so generation can stop.

    Used when the application timeout fires while a chat request is still
    blocked. Does not stop the Ollama daemon or unload models.
    """
    with _IN_FLIGHT_LOCK:
        clients = list(_IN_FLIGHT)
    closed = 0
    for client in clients:
        try:
            if not client.is_closed:
                client.close()
                closed += 1
        except Exception:
            logger.debug("ollama abort: client close failed", exc_info=True)
    if closed:
        logger.info("cancelled in-flight ollama http requests count=%s", closed)
    return closed


class OllamaClient:
    """Connection-managed Ollama HTTP client."""

    def __init__(
        self,
        config: OllamaProviderConfig,
        *,
        provider_id: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._config = config
        self._provider_id = provider_id
        self._owns_client = http_client is None
        self._client = http_client or self._build_client()
        self._client_lock = threading.Lock()

    @property
    def base_url(self) -> str:
        return self._config.base_url

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _ensure_client(self) -> httpx.Client:
        with self._client_lock:
            if self._client.is_closed:
                self._client = self._build_client()
            return self._client

    def list_models(self) -> list[OllamaModelInfo]:
        """Discover models available on the Ollama host."""
        response = self._request("GET", "/api/tags")
        payload = response.json()
        models = payload.get("models") or []
        return [OllamaModelInfo.from_api(item) for item in models if isinstance(item, dict)]

    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: str | dict[str, Any] | None = None,
        stream: bool = False,
        timeout_seconds: float | None = None,
        keep_alive: str | int | None = None,
        cancel_event: threading.Event | None = None,
    ) -> OllamaChatResponse:
        """Execute a chat completion.

        The HTTP call is always streamed so a client timeout can close the
        connection and stop Ollama generation. ``stream=True`` still returns
        assembled content to this method; use ``chat_stream`` for chunks.
        """
        if stream:
            chunks = list(
                self.chat_stream(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    timeout_seconds=timeout_seconds,
                    keep_alive=keep_alive,
                    cancel_event=cancel_event,
                )
            )
            content = "".join(chunk.content for chunk in chunks)
            last = chunks[-1] if chunks else None
            raw = last.raw if last else {}
            return OllamaChatResponse.from_api(
                {
                    **raw,
                    "model": raw.get("model") or model,
                    "message": {"role": "assistant", "content": content},
                    "done": bool(raw.get("done", True)),
                }
            )

        return self._chat_assembled(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            timeout_seconds=timeout_seconds,
            keep_alive=keep_alive,
            cancel_event=cancel_event,
        )

    def chat_stream(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: str | dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
        keep_alive: str | int | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Iterator[OllamaStreamChunk]:
        """Stream chat completion chunks (streaming-ready architecture)."""
        body = self._chat_body(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            keep_alive=keep_alive,
            http_stream=True,
        )
        timeout = self._resolve_timeout(timeout_seconds)
        deadline = self._deadline(timeout_seconds)
        client = self._ensure_client()
        try:
            with _track_client(client):
                with client.stream(
                    "POST",
                    "/api/chat",
                    json=body,
                    headers=self._headers(),
                    timeout=timeout,
                ) as response:
                    response.raise_for_status()
                    for payload in self._iter_json_lines(response, deadline, cancel_event):
                        yield OllamaStreamChunk.from_api(payload)
        except Exception as exc:
            raise map_httpx_error(exc, provider_id=self._provider_id) from exc

    def _chat_assembled(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: str | dict[str, Any] | None,
        timeout_seconds: float | None,
        keep_alive: str | int | None,
        cancel_event: threading.Event | None,
    ) -> OllamaChatResponse:
        body = self._chat_body(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            keep_alive=keep_alive,
            http_stream=True,
        )
        timeout = self._resolve_timeout(timeout_seconds)
        deadline = self._deadline(timeout_seconds)
        client = self._ensure_client()
        parts: list[str] = []
        last_payload: dict[str, Any] = {}
        aborted = False
        try:
            with _track_client(client):
                with client.stream(
                    "POST",
                    "/api/chat",
                    json=body,
                    headers=self._headers(),
                    timeout=timeout,
                ) as response:
                    response.raise_for_status()
                    for payload in self._iter_json_lines(response, deadline, cancel_event):
                        last_payload = payload
                        chunk = OllamaStreamChunk.from_api(payload)
                        if chunk.content:
                            parts.append(chunk.content)
                        if chunk.done:
                            break
                    else:
                        aborted = True
        except Exception as exc:
            raise map_httpx_error(exc, provider_id=self._provider_id) from exc

        if aborted or (cancel_event is not None and cancel_event.is_set()):
            raise httpx.ReadTimeout("Ollama chat aborted after timeout or cancel")
        if deadline is not None and time.monotonic() >= deadline and not last_payload.get("done"):
            raise httpx.ReadTimeout("Ollama chat exceeded wall-clock timeout")

        content = "".join(parts)
        merged = {
            **last_payload,
            "model": last_payload.get("model") or model,
            "message": {"role": "assistant", "content": content},
            "done": bool(last_payload.get("done", True)),
        }
        return OllamaChatResponse.from_api(merged)

    def _chat_body(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: str | dict[str, Any] | None,
        keep_alive: str | int | None,
        http_stream: bool,
    ) -> dict[str, Any]:
        ttl = keep_alive if keep_alive is not None else self._config.keep_alive
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": http_stream,
            "keep_alive": ttl,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if response_format is not None:
            body["format"] = response_format
        return body

    def _iter_json_lines(
        self,
        response: httpx.Response,
        deadline: float | None,
        cancel_event: threading.Event | None,
    ) -> Iterator[dict[str, Any]]:
        for line in response.iter_lines():
            if cancel_event is not None and cancel_event.is_set():
                return
            if deadline is not None and time.monotonic() >= deadline:
                return
            if not line:
                continue
            yield json.loads(line)

    @staticmethod
    def _deadline(timeout_seconds: float | None) -> float | None:
        if timeout_seconds is None:
            return None
        return time.monotonic() + float(timeout_seconds)

    def _build_client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self._config.base_url,
            headers=self._headers(),
            timeout=httpx.Timeout(self._config.default_timeout_seconds),
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        return headers

    def _resolve_timeout(self, timeout_seconds: float | None) -> httpx.Timeout:
        seconds = timeout_seconds if timeout_seconds is not None else self._config.default_timeout_seconds
        # Connect fails fast. Read is bounded by the wall-clock loop; keep a
        # finite read timeout so a silent stall cannot hang forever.
        return httpx.Timeout(seconds, connect=min(10.0, float(seconds)))

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
    ) -> httpx.Response:
        timeout = self._resolve_timeout(timeout_seconds)
        client = self._ensure_client()
        try:
            response = client.request(
                method,
                path,
                json=json,
                headers=self._headers(),
                timeout=timeout,
            )
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            raise map_http_status(
                exc.response.status_code,
                f"Ollama API error ({exc.response.status_code}): {exc.response.text}",
                provider_id=self._provider_id,
            ) from exc
        except Exception as exc:
            raise map_httpx_error(exc, provider_id=self._provider_id) from exc
