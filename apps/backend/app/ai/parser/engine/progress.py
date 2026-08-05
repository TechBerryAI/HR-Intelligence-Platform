"""In-memory parse job progress registry for single-file parse streaming."""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Optional

from app.ai.parser.engine.types import StageEvent

_LOCK = threading.RLock()
_JOBS: dict[str, dict[str, Any]] = {}
_MAX_JOBS = 500
_TTL_SEC = 3600


def _prune_locked() -> None:
    now = time.time()
    stale = [jid for jid, job in _JOBS.items() if now - job.get('created_at', 0) > _TTL_SEC]
    for jid in stale:
        _JOBS.pop(jid, None)
    while len(_JOBS) > _MAX_JOBS:
        oldest = min(_JOBS.items(), key=lambda kv: kv[1].get('created_at', 0))
        _JOBS.pop(oldest[0], None)


def create_parse_job(doc_type: str) -> str:
    job_id = str(uuid.uuid4())
    with _LOCK:
        _prune_locked()
        _JOBS[job_id] = {
            'id': job_id,
            'doc_type': doc_type,
            'status': 'running',
            'created_at': time.time(),
            'updated_at': time.time(),
            'events': [],
            'result': None,
            'error': None,
        }
    return job_id


def emit_stage(job_id: Optional[str], event: StageEvent) -> None:
    if not job_id:
        return
    event.job_id = job_id
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job['events'].append(event.to_dict())
        job['updated_at'] = time.time()
        if event.status == 'failed':
            job['status'] = 'failed'
            job['error'] = event.message


def complete_parse_job(job_id: Optional[str], result: dict[str, Any] | None, error: str | None = None) -> None:
    if not job_id:
        return
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job['updated_at'] = time.time()
        if error:
            job['status'] = 'failed'
            job['error'] = error
        else:
            job['status'] = 'completed'
            job['result'] = result


def get_parse_job(job_id: str) -> Optional[dict[str, Any]]:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None
        return {
            'id': job['id'],
            'doc_type': job['doc_type'],
            'status': job['status'],
            'events': list(job['events']),
            'result': job.get('result'),
            'error': job.get('error'),
            'created_at': job.get('created_at'),
            'updated_at': job.get('updated_at'),
        }


def list_stage_events(job_id: str) -> list[dict[str, Any]]:
    job = get_parse_job(job_id)
    if not job:
        return []
    return list(job.get('events') or [])
