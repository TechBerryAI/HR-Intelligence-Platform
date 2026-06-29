"""Grok error mapping to runtime provider exceptions."""

from __future__ import annotations

import httpx

from runtime.exceptions import ProviderError, ProviderNotAvailableError, ProviderTimeoutError


def map_httpx_error(exc: Exception, *, provider_id: str) -> ProviderError:
    if isinstance(exc, httpx.TimeoutException):
        return ProviderTimeoutError(
            f"Grok request timed out: {exc}",
            provider_id=provider_id,
            retryable=True,
        )
    if isinstance(exc, httpx.ConnectError):
        return ProviderNotAvailableError(
            f"Grok service unreachable: {exc}",
            provider_id=provider_id,
            retryable=True,
        )
    if isinstance(exc, httpx.HTTPStatusError):
        return map_http_status(exc.response.status_code, str(exc), provider_id=provider_id)
    return ProviderError(
        f"Grok request failed: {exc}",
        provider_id=provider_id,
        retryable=True,
    )


def map_http_status(status_code: int, message: str, *, provider_id: str) -> ProviderError:
    retryable = status_code in {429, 500, 502, 503, 504}
    if status_code in {401, 403}:
        return ProviderNotAvailableError(
            message,
            provider_id=provider_id,
            retryable=False,
            status_code=status_code,
        )
    if status_code == 408:
        return ProviderTimeoutError(
            message,
            provider_id=provider_id,
            retryable=True,
            status_code=status_code,
        )
    return ProviderError(
        message,
        provider_id=provider_id,
        retryable=retryable,
        status_code=status_code,
    )
