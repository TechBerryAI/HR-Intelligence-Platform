"""Provider configuration CRUD (encrypted credentials, masked responses)."""
from __future__ import annotations

from app.domains.integrations.config import (
    PROVIDER_CATALOG,
    is_builtin,
    is_valid_provider_slug,
    slugify_provider,
)
from app.domains.integrations import repository as repo
from app.domains.integrations.security.secrets import encrypt_secret
from app.domains.integrations.service.serializers import row_to_provider_config


def _empty_public(provider: str) -> dict:
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


def _row_public(row: dict | None, provider: str) -> dict:
    if not row:
        return _empty_public(provider)
    cfg = row_to_provider_config(row, decrypt=False)
    return cfg.to_public_dict() if cfg else _empty_public(provider)


def catalog_with_status(company_key: str) -> list[dict]:
    """Built-ins always listed; custom HTTP platforms listed when configured for company."""
    rows = {r['provider']: r for r in repo.list_providers(company_key)}
    out = []
    for meta in PROVIDER_CATALOG:
        row = rows.get(meta['id'])
        out.append({
            'id': meta['id'],
            'name': meta['name'],
            'idPrefix': meta['id_prefix'],
            'builtin': True,
            'configured': bool(row),
            'config': _row_public(row, meta['id']),
        })
        rows.pop(meta['id'], None)

    for provider, row in sorted(rows.items()):
        settings = repo.row_to_settings(row)
        display = (
            settings.get('displayName')
            or settings.get('display_name')
            or provider.replace('_', ' ').title()
        )
        out.append({
            'id': provider,
            'name': display,
            'idPrefix': (provider[:2] or 'XB').upper(),
            'builtin': False,
            'configured': True,
            'logoUrl': settings.get('logoUrl') or None,
            'config': _row_public(row, provider),
        })
    return out


def get_provider_config(company_key: str, provider: str) -> dict | None:
    provider = (provider or '').strip().lower()
    if not provider:
        return None
    if is_builtin(provider):
        row = repo.get_provider_row(company_key, provider)
        return _row_public(row, provider)
    row = repo.get_provider_row(company_key, provider)
    if not row:
        return None
    return _row_public(row, provider)


def _normalize_logo_url(raw) -> str | None:
    """HTTPS logo URL only; reject data:/http:/relative."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return ''
    from urllib.parse import urlparse
    parsed = urlparse(s)
    if parsed.scheme != 'https' or not parsed.netloc:
        raise ValueError('logoUrl must be an https:// URL')
    return s


def _normalize_http_settings(data: dict, display_name: str | None = None) -> dict:
    settings = data.get('settings') or data.get('settings_json') or {}
    if not isinstance(settings, dict):
        settings = {}
    settings = dict(settings)
    settings['adapter'] = 'http'
    if display_name:
        settings['displayName'] = display_name
    # Accept flat fields from UI
    for src, dst in (
        ('baseUrl', 'baseUrl'),
        ('base_url', 'baseUrl'),
        ('authHeader', 'authHeader'),
        ('auth_header', 'authHeader'),
        ('logoUrl', 'logoUrl'),
        ('logo_url', 'logoUrl'),
    ):
        if src in data and data.get(src) is not None:
            settings[dst] = data[src]
    # Normalize / validate logoUrl (empty clears)
    if 'logoUrl' in settings:
        settings['logoUrl'] = _normalize_logo_url(settings.get('logoUrl'))
        if settings['logoUrl'] == '':
            settings.pop('logoUrl', None)
    endpoints = settings.get('endpoints') if isinstance(settings.get('endpoints'), dict) else {}
    endpoints = dict(endpoints)
    flat_eps = data.get('endpoints') if isinstance(data.get('endpoints'), dict) else {}
    endpoints.update(flat_eps)
    for key in ('test', 'publish', 'update', 'close', 'applications', 'status'):
        flat_key = f'endpoint_{key}'
        if data.get(flat_key):
            endpoints[key] = data[flat_key]
        camel = f'endpoint{key.title()}'
        if data.get(camel):
            endpoints[key] = data[camel]
    if endpoints:
        settings['endpoints'] = endpoints
    return settings


def save_provider_config(
    company_key: str,
    company: str | None,
    provider: str,
    data: dict,
    *,
    connect: bool = False,
    allow_custom: bool = True,
) -> dict | None:
    provider = (provider or '').strip().lower()
    display_name = (data.get('displayName') or data.get('name') or data.get('display_name') or '').strip()

    if not provider:
        if display_name:
            provider = slugify_provider(display_name)
        else:
            raise ValueError('provider or name is required')

    if not is_valid_provider_slug(provider):
        raise ValueError('Invalid provider slug (use lowercase letters, numbers, underscore)')

    creating_custom = allow_custom and not is_builtin(provider)
    if creating_custom:
        # Creating/updating custom HTTP platform
        settings = _normalize_http_settings(data, display_name or provider)
        if not (settings.get('baseUrl') or '').strip():
            # Allow save without baseUrl only when disconnecting / partial update of existing
            existing = repo.get_provider_row(company_key, provider)
            if not existing and not data.get('allowIncomplete'):
                raise ValueError('API Base URL is required for custom platforms')
        data = {**data, 'settings': settings}
    elif not is_builtin(provider):
        raise ValueError(f'Unsupported provider: {provider}')

    client_secret = data.get('clientSecret') or data.get('client_secret')
    access_token = data.get('accessToken') or data.get('access_token')
    refresh_token = data.get('refreshToken') or data.get('refresh_token')

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
        auth_type=data.get('authType') or data.get('auth_type') or ('api_key' if creating_custom else None),
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
    return _row_public(row, provider)


def disconnect_provider(company_key: str, provider: str) -> dict | None:
    provider = (provider or '').strip().lower()
    repo.upsert_provider(
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
    return _row_public(repo.get_provider_row(company_key, provider), provider)


def delete_provider_config(company_key: str, provider_or_id: str | int) -> bool:
    if isinstance(provider_or_id, int) or (isinstance(provider_or_id, str) and provider_or_id.isdigit()):
        return repo.delete_provider_by_id(company_key, int(provider_or_id)) > 0
    provider = str(provider_or_id).strip().lower()
    # Do not allow deleting builtin catalog identity — clearing row is ok
    return repo.delete_provider(company_key, provider) > 0
