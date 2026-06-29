"""
Bulk Resume Parsing Service - calls Bulk-Resume-Parser API when available.
Falls back to local bulk parsing (text_extraction + LLM) when external service is unreachable.
"""
import json
import os
from pathlib import Path

import requests

BULK_PARSER_URL = (os.getenv('BULK_PARSER_URL') or 'http://localhost:8001').rstrip('/') or None

ERROR_CODE_UNREACHABLE = 'BULK_PARSER_UNREACHABLE'

_EXTERNAL_OWNERS_FILE = Path(__file__).resolve().parent.parent / 'data' / 'bulk_external_owners.json'
_owners_lock = __import__('threading').Lock()


def _load_external_owners() -> dict:
    try:
        if _EXTERNAL_OWNERS_FILE.is_file():
            return json.loads(_EXTERNAL_OWNERS_FILE.read_text(encoding='utf-8'))
    except Exception as e:
        print(f"[bulk_parsing_service] load owners failed: {e}")
    return {}


def _save_external_owner(job_id: str, started_by: str) -> None:
    if not job_id or not started_by:
        return
    with _owners_lock:
        owners = _load_external_owners()
        owners[job_id] = started_by
        try:
            _EXTERNAL_OWNERS_FILE.parent.mkdir(parents=True, exist_ok=True)
            _EXTERNAL_OWNERS_FILE.write_text(json.dumps(owners), encoding='utf-8')
        except Exception as e:
            print(f"[bulk_parsing_service] save owner failed: {e}")


def _get_external_owner(job_id: str) -> str | None:
    return _load_external_owners().get(job_id)


def _is_connection_error(e):
    if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.ConnectTimeout)):
        return True
    if getattr(e, 'cause', None) and getattr(e.cause, 'errno', None):
        return True
    err = str(e).lower()
    return 'connection refused' in err or 'max retries exceeded' in err or 'connection error' in err


def upload_files(files_list, output_filename=None, append=False, started_by=None):
    """
    Try external Bulk-Resume-Parser first; on connection failure use local bulk parsing.
    files_list: list of (filename, file_bytes).
    Returns (success, {job_id, total_files, status, ...} or error dict).
    """
    if BULK_PARSER_URL:
        try:
            files = [('files', (name, data)) for name, data in files_list]
            data = {}
            if output_filename:
                data['output_path'] = output_filename
            if append is not None:
                data['append'] = 'true' if append else 'false'
            resp = requests.post(
                f'{BULK_PARSER_URL}/api/upload',
                files=files,
                data=data,
                timeout=30,
            )
            resp.raise_for_status()
            payload = resp.json()
            job_id = payload.get('job_id')
            if started_by and job_id:
                _save_external_owner(job_id, started_by)
            return True, payload
        except requests.exceptions.RequestException as e:
            if not _is_connection_error(e):
                err = str(e)
                if getattr(e, 'response', None) is not None:
                    try:
                        err = e.response.json().get('detail', err)
                    except Exception:
                        pass
                return False, {'error': err}
            # Fall through to local fallback
    # Local bulk parsing (external unreachable or BULK_PARSER_URL not set)
    from services.local_bulk_parser import start_local_job
    _, result = start_local_job(files_list, started_by=started_by)
    return True, result


def get_progress(job_id, user=None):
    """Check local job first; else forward to Bulk-Resume-Parser GET /api/progress/{job_id}."""
    from services.local_bulk_parser import get_local_progress
    from rbac import can_access_bulk_session
    ok, result = get_local_progress(job_id)
    if ok:
        started_by = result.get('started_by')
        if user and started_by and not can_access_bulk_session(user, started_by):
            return False, {'error': 'Access denied'}
        return True, {k: v for k, v in result.items() if k != 'started_by'}
    if not BULK_PARSER_URL:
        return False, {'error': 'Job not found'}
    try:
        owner = _get_external_owner(job_id)
        if user and owner and not can_access_bulk_session(user, owner):
            return False, {'error': 'Access denied'}
        resp = requests.get(f'{BULK_PARSER_URL}/api/progress/{job_id}', timeout=10)
        resp.raise_for_status()
        return True, resp.json()
    except requests.exceptions.RequestException as e:
        if _is_connection_error(e):
            return False, {'error': 'Bulk parsing service unavailable.', 'code': ERROR_CODE_UNREACHABLE}
        err = str(e)
        if getattr(e, 'response', None) is not None and e.response.status_code == 404:
            return False, {'error': 'Job not found'}
        return False, {'error': err}


def get_download_url(job_id):
    """Return URL for client to download Excel from Bulk-Resume-Parser (same-origin proxy recommended)."""
    if not BULK_PARSER_URL:
        return None
    return f'{BULK_PARSER_URL}/api/download/{job_id}'


def stream_download(job_id, user=None):
    """
    Return Excel from local job if present; else stream from Bulk-Resume-Parser.
    Returns (success, (content_iterator, filename, content_type)) or (False, error_dict).
    """
    from services.local_bulk_parser import get_local_progress, get_local_download
    from rbac import can_access_bulk_session
    ok_meta, meta = get_local_progress(job_id, check_only=True)
    if ok_meta:
        started_by = meta.get('started_by')
        if user and started_by and not can_access_bulk_session(user, started_by):
            return False, {'error': 'Access denied'}
    else:
        owner = _get_external_owner(job_id)
        if user and owner and not can_access_bulk_session(user, owner):
            return False, {'error': 'Access denied'}
    ok, payload = get_local_download(job_id)
    if ok:
        bio, filename, content_type = payload
        bio.seek(0)
        def chunk_iter(b):
            while True:
                chunk = b.read(8192)
                if not chunk:
                    break
                yield chunk
        return True, (chunk_iter(bio), filename, content_type)
    if not BULK_PARSER_URL:
        return False, payload
    try:
        owner = _get_external_owner(job_id)
        if user and owner and not can_access_bulk_session(user, owner):
            return False, {'error': 'Access denied'}
        resp = requests.get(
            f'{BULK_PARSER_URL}/api/download/{job_id}',
            stream=True,
            timeout=120,
        )
        resp.raise_for_status()
        filename = resp.headers.get('Content-Disposition', '').split('filename=')[-1].strip('"\'') or 'Parsed_Resumes.xlsx'
        content_type = resp.headers.get('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        return True, (resp.iter_content(chunk_size=8192), filename, content_type)
    except requests.exceptions.RequestException as e:
        if _is_connection_error(e):
            return False, {'error': 'Bulk parsing service unavailable.', 'code': ERROR_CODE_UNREACHABLE}
        err = str(e)
        if getattr(e, 'response', None) is not None:
            if e.response.status_code == 404:
                err = 'Job not found or not completed'
            elif e.response.status_code == 400:
                err = 'Job not completed yet'
        return False, {'error': err}
