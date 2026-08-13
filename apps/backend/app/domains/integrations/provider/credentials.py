"""Shared credential checks for job-board providers."""
from __future__ import annotations

from app.domains.integrations.dto import ConnectionResult, ProviderConfig, PublishResult

PROVIDER_ACCESS_REQUIRED = 'PROVIDER ACCESS REQUIRED'


def provider_access_publish(provider: str, detail: str) -> PublishResult:
    return PublishResult(
        success=False,
        provider=provider,
        error=f'{PROVIDER_ACCESS_REQUIRED}: {detail}',
        message=PROVIDER_ACCESS_REQUIRED,
    )


def provider_access_connection(provider: str, detail: str) -> ConnectionResult:
    return ConnectionResult(
        success=False,
        provider=provider,
        error=f'{PROVIDER_ACCESS_REQUIRED}: {detail}',
        message=PROVIDER_ACCESS_REQUIRED,
    )


def has_credentials(config: ProviderConfig | None) -> bool:
    if not config:
        return False
    client_id = (config.client_id or '').strip()
    client_secret = (config.client_secret or '').strip()
    access_token = (config.access_token or '').strip()
    # Accept either API-key pair or bearer access token
    if client_id and client_secret:
        return True
    if access_token:
        return True
    return False


def credentials_missing_connection(provider: str) -> ConnectionResult:
    return ConnectionResult(
        success=False,
        provider=provider,
        error='Credentials required. Enter Client ID and Client Secret (or Access Token), then Save.',
        message='Credentials required to connect',
    )


def credentials_missing_publish(provider: str) -> PublishResult:
    return PublishResult(
        success=False,
        provider=provider,
        error='Credentials required before publishing. Configure and save provider credentials in Settings → Integrations.',
        message='Credentials required',
    )
