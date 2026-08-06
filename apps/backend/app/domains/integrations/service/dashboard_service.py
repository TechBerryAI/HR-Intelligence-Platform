"""Dashboard / status aggregates for integrations UI."""
from __future__ import annotations

from app.domains.integrations.config import PROVIDER_CATALOG, is_builtin
from app.domains.integrations import repository as repo
from app.domains.integrations.service.serializers import serialize_log_row
from app.domains.integrations.worker.queue import get_queue


def build_status(company_key: str) -> dict:
    counts = repo.count_external_by_status(company_key)
    by_provider: dict[str, dict[str, int]] = {}
    for row in counts:
        p = row.get('provider') or 'unknown'
        st = row.get('sync_status') or 'unknown'
        by_provider.setdefault(p, {})
        by_provider[p][st] = int(row.get('count') or 0)

    providers = []
    seen = set()
    for meta in PROVIDER_CATALOG:
        pid = meta['id']
        seen.add(pid)
        stats = by_provider.get(pid, {})
        cfg = repo.get_provider_row(company_key, pid)
        providers.append({
            'provider': pid,
            'name': meta['name'],
            'builtin': True,
            'status': (cfg or {}).get('status') or 'disconnected',
            'enabled': bool((cfg or {}).get('enabled')),
            'autoPublish': bool((cfg or {}).get('auto_publish')),
            'published': stats.get('published', 0),
            'pending': stats.get('pending', 0),
            'failed': stats.get('failed', 0) + stats.get('dead', 0),
            'closed': stats.get('closed', 0),
        })

    for row in repo.list_providers(company_key):
        pid = row.get('provider')
        if not pid or pid in seen:
            continue
        seen.add(pid)
        settings = repo.row_to_settings(row)
        stats = by_provider.get(pid, {})
        providers.append({
            'provider': pid,
            'name': settings.get('displayName') or pid.replace('_', ' ').title(),
            'builtin': False,
            'logoUrl': settings.get('logoUrl') or None,
            'status': row.get('status') or 'disconnected',
            'enabled': bool(row.get('enabled')),
            'autoPublish': bool(row.get('auto_publish')),
            'published': stats.get('published', 0),
            'pending': stats.get('pending', 0),
            'failed': stats.get('failed', 0) + stats.get('dead', 0),
            'closed': stats.get('closed', 0),
        })

    # Include providers that have external_jobs but no config row yet
    for pid, stats in by_provider.items():
        if pid in seen:
            continue
        providers.append({
            'provider': pid,
            'name': pid.replace('_', ' ').title(),
            'builtin': is_builtin(pid),
            'status': 'disconnected',
            'enabled': False,
            'autoPublish': False,
            'published': stats.get('published', 0),
            'pending': stats.get('pending', 0),
            'failed': stats.get('failed', 0) + stats.get('dead', 0),
            'closed': stats.get('closed', 0),
        })

    queue = get_queue()
    return {
        'providers': providers,
        'pendingQueue': queue.pending_count() if queue else 0,
    }


def build_dashboard(company_key: str) -> dict:
    status = build_status(company_key)
    logs = repo.list_sync_logs(company_key, limit=20)
    recent_errors = [
        serialize_log_row(r)
        for r in logs
        if (r.get('status') or '') in ('failed', 'error')
    ][:10]
    last_by_provider: dict[str, dict] = {}
    for row in logs:
        p = row.get('provider')
        if p and p not in last_by_provider:
            last_by_provider[p] = serialize_log_row(row)

    return {
        **status,
        'recentErrors': recent_errors,
        'lastActivityByProvider': last_by_provider,
        'recentLogs': [serialize_log_row(r) for r in logs[:10]],
    }
