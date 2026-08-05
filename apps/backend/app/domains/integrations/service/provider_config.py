"""Provider configuration CRUD (encrypted credentials, masked responses)."""
from __future__ import annotations

from app.domains.integrations.config import PROVIDER_CATALOG, VALID_PROVIDERS
from app.domains.integrations import repository as repo
from app.domains.integrations.security.secrets import encrypt_secret
from app.domains.integrations.service.serializers import row_to_provider_config


def catalog_with_status(company_key: str) -> list[dict]:
    rows = {r['provider']: r for r in repo.list_providers(company_key)}
    out = []
    for meta in PROVIDER_CATALOG:
        row = rows.get(meta['id'])
        cfg = row_to_provider_config(row, decrypt=False) if row else None
        out.append({
            'id': meta['id'],
            'name': meta['name'],
            'idPrefix': meta['id_prefix'],
            'configured': bool(row),
            'config': cfg.to_public_dict() if cfg else {
                'provider': meta['id'],
                'enabled': False,
                'status': 'disconnected',
                'autoPublish': False,
                'autoSync': False,
                'clientId': '',
                'clientSecret': None,
                'accessToken': None,
                'refreshToken': None,
                'clientSecretConfigured': False,
                'accessTokenConfigured': False,
                'refreshTokenConfigured': False,
                'settings': {},
            },
        })
    return out


def get_provider_config(company_key: str, provider: str) -> dict | None:
    provider = (provider or '').strip().lower()
    if provider not in VALID_PROVIDERS:
        return None
    row = repo.get_provider_row(company_key, provider)
    if not row:
        return {
            'provider': provider,
            'enabled': False,
            'status': 'disconnected',
            'autoPublish': False,
            'autoSync': False,
            'clientId': '',
            'clientSecret': None,
            'accessToken': None,
            'refreshToken': None,
            'clientSecretConfigured': False,
            'accessTokenConfigured': False,
            'refreshTokenConfigured': False,
            'settings': {},
        }
    cfg = row_to_provider_config(row, decrypt=False)
    return cfg.to_public_dict() if cfg else None


def save_provider_config(
    company_key: str,
    company: str | None,
    provider: str,
    data: dict,
    *,
    connect: bool = False,
) -> dict | None:
    provider = (provider or '').strip().lower()
    if provider not in VALID_PROVIDERS:
        raise ValueError(f'Unsupported provider: {provider}')

    client_secret = data.get('clientSecret') or data.get('client_secret')
    access_token = data.get('accessToken') or data.get('access_token')
    refresh_token = data.get('refreshToken') or data.get('refresh_token')

    # Ignore masked placeholders from UI
    def _clean(v):
        if v is None:
            return None
        s = str(v).strip()
        if not s or s.startswith('•') or s == '********':
            return None
        return s

    client_secret = _clean(client_secret)
    access_token = _clean(access_token)
    refresh_token = _clean(refresh_token)

    status = data.get('status')
    if connect:
        status = 'connected'
    enabled = data.get('enabled')
    auto_publish = data.get('autoPublish') if 'autoPublish' in data else data.get('auto_publish')
    auto_sync = data.get('autoSync') if 'autoSync' in data else data.get('auto_sync')

    row = repo.upsert_provider(
        company_key,
        company,
        provider,
        enabled=enabled,
        status=status,
        auth_type=data.get('authType') or data.get('auth_type'),
        auto_publish=auto_publish,
        auto_sync=auto_sync,
        client_id=data.get('clientId') if 'clientId' in data else data.get('client_id'),
        client_secret=encrypt_secret(client_secret) if client_secret is not None else None,
        access_token=encrypt_secret(access_token) if access_token is not None else None,
        refresh_token=encrypt_secret(refresh_token) if refresh_token is not None else None,
        expires_at=data.get('expiresAt') or data.get('expires_at'),
        settings_json=data.get('settings') or data.get('settings_json'),
        update_secrets=False,
    )
    cfg = row_to_provider_config(row, decrypt=False)
    return cfg.to_public_dict() if cfg else None


def disconnect_provider(company_key: str, provider: str) -> dict | None:
    provider = (provider or '').strip().lower()
    row = repo.upsert_provider(
        company_key,
        None,
        provider,
        enabled=False,
        status='disconnected',
        auto_publish=False,
        client_secret='',
        access_token='',
        refresh_token='',
        update_secrets=True,
    )
    # Clear secrets explicitly
    repo.upsert_provider(
        company_key,
        None,
        provider,
        status='disconnected',
        enabled=False,
        client_secret='',
        access_token='',
        refresh_token='',
        update_secrets=True,
    )
    cfg = row_to_provider_config(repo.get_provider_row(company_key, provider), decrypt=False)
    return cfg.to_public_dict() if cfg else None


def delete_provider_config(company_key: str, provider_or_id: str | int) -> bool:
    if isinstance(provider_or_id, int) or (isinstance(provider_or_id, str) and provider_or_id.isdigit()):
        return repo.delete_provider_by_id(company_key, int(provider_or_id)) > 0
    return repo.delete_provider(company_key, str(provider_or_id).strip().lower()) > 0
