"""
Local bulk resume parsing when external Bulk-Resume-Parser (port 8001) is unavailable.
Uses existing text_extraction + llm_service; stores results in memory and exports Excel.
Persists session/file progress to PostgreSQL (bulk_parse_sessions / bulk_parse_files).
Processes files in parallel (configurable workers) for faster throughput.
"""
import io
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

# In-memory job store: job_id -> { status, total_files, processed_files, failed_files, results, message, failed_filenames, success_filenames }
_local_jobs: dict[str, dict[str, Any]] = {}
_local_jobs_lock = threading.Lock()

_BULK_EXPORT_DIR = Path(__file__).resolve().parents[3] / 'data' / 'bulk_exports'


def _export_path(job_id: str) -> Path:
    return _BULK_EXPORT_DIR / f'{job_id}.xlsx'


def _persist_excel(job_id: str, rows: list[dict]) -> None:
    try:
        _BULK_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        _export_path(job_id).write_bytes(_build_excel_bytes(rows))
    except Exception as e:
        print(f"[local_bulk_parser] persist excel failed: {e}")

ALLOWED_EXT = {'pdf', 'doc', 'docx'}

# Parallel workers for bulk parse. With 4 Grok keys, 6–8 balances speed and rate limits; increase if you have more keys.
BULK_PARSE_MAX_WORKERS = max(1, min(24, int(os.getenv('BULK_PARSE_MAX_WORKERS', '6'))))


def _flatten_toon(toon: dict, filename: str) -> dict:
    """Flatten one TOON resume to a row dict for Excel."""
    person = toon.get('person') or {}
    skills = toon.get('skills') or []
    exp = toon.get('experience') or []
    edu = toon.get('education') or []
    certs = toon.get('certifications') or []
    exp_text = '; '.join(
        f"{e.get('title', '')} at {e.get('company', '')} ({e.get('from', '')}-{e.get('to', '')})"
        for e in exp[:10]
    )
    edu_text = '; '.join(
        f"{e.get('degree', '')} - {e.get('institution', '')}"
        for e in edu[:5]
    )
    return {
        'Filename': filename,
        'Name': person.get('name') or '',
        'Email': person.get('email') or '',
        'Phone': person.get('phone') or '',
        'LinkedIn': person.get('linkedin') or '',
        'GitHub': person.get('github') or '',
        'Summary': (toon.get('summary') or '')[:500],
        'Skills': ', '.join(skills[:30]) if isinstance(skills, list) else str(skills)[:500],
        'Experience': exp_text[:1000],
        'Education': edu_text[:500],
        'Certifications': ', '.join(certs[:20]) if isinstance(certs, list) else str(certs)[:300],
        'Total Experience Years': toon.get('total_experience_years') or '',
    }


def _build_excel_bytes(rows: list[dict]) -> bytes:
    """Build .xlsx from list of row dicts using openpyxl."""
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Resumes"
    if rows:
        headers = list(rows[0].keys())
        ws.append(headers)
        for r in rows:
            ws.append([r.get(h, '') for h in headers])
        for col in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(col)].width = min(40, max(10, len(str(headers[col - 1])) + 2))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _process_one_file(args: tuple[str, bytes]) -> tuple[str, dict | None, bool, str]:
    """
    Process a single file: extract text + LLM. Thread-safe; no shared state.
    Returns (filename, row or None, failed: bool, message).
    """
    from app.ai.parser.text_extraction import extract_text
    from app.integrations.openai.llm_service import call_llm

    filename, data = args
    try:
        raw_text = extract_text(data, filename)
        if not raw_text or len(raw_text.strip()) < 30:
            return (filename, None, True, f'Skipped (insufficient text): {filename}')
        toon = call_llm(raw_text, 'resume')
        row = _flatten_toon(toon, filename)
        return (filename, row, False, f'Processing: {filename}')
    except Exception as e:
        return (filename, None, True, f'Failed: {filename} - {str(e)[:100]}')


def _worker(job_id: str, files_list: list[tuple[str, bytes]], started_at: float) -> None:
    """Background: process files in parallel (ThreadPoolExecutor), update job progress as each completes."""
    from app.domains.administration.repositories.bulk_session_db import finalize_session, update_file_status, update_session_progress

    with _local_jobs_lock:
        job = _local_jobs.get(job_id)
    if not job or job.get('status') == 'cancelled':
        return
    total = len(files_list)
    results: list[dict] = []
    success_count = 0
    failed_count = 0
    max_workers = min(BULK_PARSE_MAX_WORKERS, total)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {executor.submit(_process_one_file, (fname, fdata)): fname for fname, fdata in files_list}
        for future in as_completed(future_to_file):
            with _local_jobs_lock:
                j = _local_jobs.get(job_id)
            if not j or j.get('status') == 'cancelled':
                break
            filename, row, is_failed, message = future.result()
            if is_failed:
                failed_count += 1
                update_file_status(job_id, filename, 'Failed', error_message=message)
                with _local_jobs_lock:
                    if job_id in _local_jobs:
                        _local_jobs[job_id].setdefault('failed_filenames', []).append(filename)
            else:
                if row:
                    results.append(row)
                success_count += 1
                update_file_status(job_id, filename, 'Completed')
                with _local_jobs_lock:
                    if job_id in _local_jobs:
                        _local_jobs[job_id].setdefault('success_filenames', []).append(filename)
            update_session_progress(job_id, success_count + failed_count, success_count, failed_count)
            with _local_jobs_lock:
                if job_id in _local_jobs:
                    _local_jobs[job_id]['processed_files'] = success_count + failed_count
                    _local_jobs[job_id]['failed_files'] = failed_count
                    _local_jobs[job_id]['message'] = message

    with _local_jobs_lock:
        if job_id in _local_jobs:
            _local_jobs[job_id]['status'] = 'completed'
            _local_jobs[job_id]['processed_files'] = success_count + failed_count
            _local_jobs[job_id]['failed_files'] = failed_count
            _local_jobs[job_id]['results'] = results
            _local_jobs[job_id]['message'] = f'Completed: {success_count} successful, {failed_count} failed'

    if results:
        _persist_excel(job_id, results)

    finalize_session(job_id, started_at, success_count, failed_count)


def start_local_job(files_list: list[tuple[str, bytes]], started_by=None) -> tuple[str, dict]:
    """
    Start local bulk parse job. Returns (job_id, { job_id, total_files, status: 'started' }).
    Persists session to DB when started_by is provided.
    """
    from app.domains.administration.repositories.bulk_session_db import create_session

    filenames = [f[0] for f in files_list]
    file_data = [f[1] for f in files_list]
    job_id = None
    if started_by:
        job_id = create_session(started_by, filenames, file_data)
    if not job_id:
        job_id = str(uuid.uuid4())

    started_at = time.time()
    with _local_jobs_lock:
        _local_jobs[job_id] = {
            'status': 'started',
            'total_files': len(files_list),
            'processed_files': 0,
            'failed_files': 0,
            'results': [],
            'message': 'Processing...',
            'failed_filenames': [],
            'success_filenames': [],
            'started_by': started_by,
            'started_at': started_at,
        }
    t = threading.Thread(target=_worker, args=(job_id, files_list, started_at), daemon=True)
    t.start()
    return job_id, {
        'job_id': job_id,
        'total_files': len(files_list),
        'status': 'started',
        'message': 'Local bulk parsing started.',
    }


def get_local_progress(job_id: str, check_only: bool = False) -> tuple[bool, dict]:
    """Return (True, progress_dict) if job exists; else (False, error_dict)."""
    with _local_jobs_lock:
        job = _local_jobs.get(job_id)
    if job:
        if check_only:
            return True, {'started_by': job.get('started_by')}
        return True, {
            'status': job['status'],
            'started_by': job.get('started_by'),
            'total_files': job['total_files'],
            'processed_files': job.get('processed_files', 0),
            'failed_files': job.get('failed_files', 0),
            'message': job.get('message', ''),
            'failed_filenames': job.get('failed_filenames', []),
            'success_filenames': job.get('success_filenames', []),
        }

    from app.domains.administration.repositories.bulk_session_db import get_session_progress, get_session_owner

    db_progress = get_session_progress(job_id)
    if db_progress:
        if check_only:
            return True, {'started_by': db_progress.get('started_by')}
        return True, db_progress

    owner = get_session_owner(job_id)
    if owner and check_only:
        return True, {'started_by': owner}

    return False, {'error': 'Job not found'}


def get_local_download(job_id: str) -> tuple[bool, Any]:
    """
    If job completed, return (True, (bytes_io, filename, content_type)).
    Else (False, error_dict).
    """
    with _local_jobs_lock:
        job = _local_jobs.get(job_id)
    if job:
        if job['status'] != 'completed':
            return False, {'error': 'Job not completed yet'}
        rows = job.get('results') or []
        try:
            xlsx_bytes = _build_excel_bytes(rows)
        except Exception as e:
            return False, {'error': f'Excel build failed: {e}'}
        return True, (io.BytesIO(xlsx_bytes), 'Parsed_Resumes.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    export_file = _export_path(job_id)
    if export_file.is_file():
        return True, (
            io.BytesIO(export_file.read_bytes()),
            'Parsed_Resumes.xlsx',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

    from app.domains.administration.repositories.bulk_session_db import get_session_progress

    db_progress = get_session_progress(job_id)
    if db_progress and db_progress.get('status') == 'completed':
        return False, {'error': 'Export file not found for completed session'}

    return False, {'error': 'Job not found'}
