"""Integration DTOs and result types."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class JobSnapshot:
    """Provider-agnostic job view — never pass ORM/raw Job rows to providers."""

    job_id: str
    title: str
    company: str
    company_key: str
    location: str | None = None
    salary: str | None = None
    experience: str | None = None
    description: str | None = None
    keywords: str | None = None
    enabled: bool = True
    posted_on: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProviderConfig:
    id: int | None
    company_key: str
    company: str | None
    provider: str
    enabled: bool = False
    status: str = 'disconnected'
    auth_type: str = 'api_key'
    auto_publish: bool = False
    auto_sync: bool = False
    client_id: str | None = None
    client_secret: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    expires_at: Any = None
    settings: dict[str, Any] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, Any]:
        from app.domains.integrations.security.secrets import is_secret_configured, mask_secret

        return {
            'id': self.id,
            'companyKey': self.company_key,
            'company': self.company,
            'provider': self.provider,
            'enabled': self.enabled,
            'status': self.status,
            'authType': self.auth_type,
            'autoPublish': self.auto_publish,
            'autoSync': self.auto_sync,
            'clientId': self.client_id or '',
            'clientSecret': mask_secret(self.client_secret),
            'accessToken': mask_secret(self.access_token),
            'refreshToken': mask_secret(self.refresh_token),
            'clientSecretConfigured': is_secret_configured(self.client_secret),
            'accessTokenConfigured': is_secret_configured(self.access_token),
            'refreshTokenConfigured': is_secret_configured(self.refresh_token),
            'expiresAt': self.expires_at.isoformat() if getattr(self.expires_at, 'isoformat', None) else self.expires_at,
            'settings': self.settings or {},
        }


@dataclass
class PublishResult:
    success: bool
    provider: str
    external_job_id: str | None = None
    external_status: str | None = None
    message: str | None = None
    payload: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SyncResult:
    success: bool
    provider: str
    imported_count: int = 0
    message: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConnectionResult:
    success: bool
    provider: str
    message: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AggregatePublishResult:
    job_id: str
    results: list[PublishResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'jobId': self.job_id,
            'results': [r.to_dict() for r in self.results],
            'successCount': sum(1 for r in self.results if r.success),
            'failureCount': sum(1 for r in self.results if not r.success),
        }
