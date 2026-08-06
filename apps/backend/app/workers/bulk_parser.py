"""
Local bulk resume parsing when external Bulk-Resume-Parser (port 8001) is unavailable.
Uses existing text_extraction + llm_service; stages uploads on disk; exports Excel.
Persists session/file progress to PostgreSQL (bulk_parse_sessions / bulk_parse_files).
Supports chunked uploads, ZIP extract, and parallel workers.
"""
from __future__ import annotations

import io
import os
import re
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from app.core import media_storage

# In-memory job store: job_id -> job dict
_local_jobs: dict[str, dict[str, Any]] = {}
_local_jobs_lock = threading.Lock()

_BULK_EXPORT_DIR = media_storage.bulk_exports_dir()
_BULK_UPLOAD_DIR = media_storage.bulk_uploads_dir()

ALLOWED_EXT = {'pdf', 'doc', 'docx'}
EXCEL_HEADERS = [
    'Filename',
    'Name',
    'Email',
    'Phone',
    'LinkedIn',
    'GitHub',
    'Summary',
    'Skills',
    'Experience',
    'Education',
    'Certifications',
    'Total Experience Years',
    'ParseStatus',
    'ParseNotes',
]

BULK_OCR_RETRY_DPI = 300
BULK_MIN_TEXT_CHARS = 30

# OCR/extract can run in parallel; LLM calls are gated by OLLAMA_MAX_CONCURRENT.
# Higher default now that most clean resumes skip Ollama via deterministic path.
BULK_PARSE_MAX_WORKERS = max(1, min(24, int(os.getenv('BULK_PARSE_MAX_WORKERS', '6'))))
# Serialize local 14B inference so large batches queue instead of timing out.
OLLAMA_MAX_CONCURRENT = max(1, min(8, int(os.getenv('OLLAMA_MAX_CONCURRENT', '1'))))
BULK_LLM_ATTEMPTS = max(2, min(8, int(os.getenv('BULK_LLM_ATTEMPTS', '4'))))
BULK_EXCEL_CHECKPOINT_EVERY = max(5, int(os.getenv('BULK_EXCEL_CHECKPOINT_EVERY', '25')))
BULK_SKIP_LLM_WHEN_DETERMINISTIC = os.getenv(
    'BULK_SKIP_LLM_WHEN_DETERMINISTIC', 'true'
).lower() in ('1', 'true', 'yes')
_llm_semaphore = threading.Semaphore(OLLAMA_MAX_CONCURRENT)


def _is_retryable_llm_error(err: str) -> bool:
    low = (err or '').lower()
    return any(
        token in low
        for token in (
            'timeout',
            'timed out',
            'connection',
            'temporarily',
            'unavailable',
            'overloaded',
            'busy',
            '429',
            '500',
            '502',
            '503',
            '504',
            'provider not available',
            'no healthy',
            'read timed out',
            'connect',
        )
    )


def _call_llm_throttled(raw_text: str, doc_type: str = 'resume'):
    """Queue LLM calls so Ollama is not overwhelmed on large batches."""
    from app.integrations.openai.llm_service import call_llm

    with _llm_semaphore:
        return call_llm(raw_text, doc_type)


def _export_path(job_id: str) -> Path:
    return _BULK_EXPORT_DIR / f'{job_id}.xlsx'


def _staging_dir(job_id: str) -> Path:
    return _BULK_UPLOAD_DIR / job_id


def _safe_filename(name: str) -> str:
    """Basename + secure characters; keep uniqueness via caller if needed."""
    from werkzeug.utils import secure_filename

    base = secure_filename(Path(name).name) or 'file'
    return base


def _unique_staged_name(job_id: str, filename: str) -> str:
    """Avoid collisions when the same basename appears in multiple batches/zip entries."""
    safe = _safe_filename(filename)
    dest_dir = _staging_dir(job_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    candidate = safe
    stem = Path(safe).stem
    suffix = Path(safe).suffix
    n = 1
    while (dest_dir / candidate).exists():
        candidate = f'{stem}_{n}{suffix}'
        n += 1
    return candidate


def _persist_excel(job_id: str, rows: list[dict], append: bool = False) -> None:
    try:
        _BULK_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        path = _export_path(job_id)
        if append and path.is_file():
            existing = _read_excel_rows(path)
            # Prefer newer rows for same Filename
            by_name = {r.get('Filename'): r for r in existing if r.get('Filename')}
            for r in rows:
                by_name[r.get('Filename')] = r
            merged = list(by_name.values()) if by_name else (existing + rows)
            path.write_bytes(_build_excel_bytes(merged))
        else:
            path.write_bytes(_build_excel_bytes(rows))
    except Exception as e:
        print(f"[local_bulk_parser] persist excel failed: {e}")


def _read_excel_rows(path: Path) -> list[dict]:
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    try:
        headers = [str(h) if h is not None else '' for h in next(rows_iter)]
    except StopIteration:
        wb.close()
        return []
    out = []
    for vals in rows_iter:
        row = {}
        for i, h in enumerate(headers):
            if not h:
                continue
            row[h] = vals[i] if i < len(vals) and vals[i] is not None else ''
        if any(str(v).strip() for v in row.values()):
            out.append(row)
    wb.close()
    return out


def _as_text(value: Any) -> str:
    """Coerce LLM TOON values to stripped text (ints/lists/None-safe)."""
    if value is None:
        return ''
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return str(value).strip()
    if isinstance(value, (int, float)):
        return str(value).strip()
    if isinstance(value, list):
        parts = [_as_text(item) for item in value]
        return ' '.join(p for p in parts if p)
    if isinstance(value, dict):
        for key in ('name', 'title', 'text', 'value', 'label', 'email', 'phone', 'skill'):
            if key in value and value[key] is not None:
                return _as_text(value[key])
        return ''
    return str(value).strip()


def _normalize_phone(phone: Any) -> str:
    s = _as_text(phone)
    if not s:
        return ''
    # Keep leading +, digits, spaces, dashes, parentheses
    cleaned = re.sub(r'[^\d+\-\s().]', '', s)
    return cleaned.strip()


def _normalize_email(email: Any) -> str:
    s = _as_text(email).lower()
    if not s:
        return ''
    if '@' not in s:
        return s
    return s


def _cert_to_str(c: Any) -> str:
    if isinstance(c, dict):
        name = _as_text(c.get('name'))
        issuer = _as_text(c.get('issuer'))
        if name and issuer:
            return f'{name} ({issuer})'
        return name or issuer or _as_text(c)
    return _as_text(c)


def _skill_to_str(s: Any) -> str:
    if isinstance(s, dict):
        return _as_text(s.get('name') or s.get('skill') or s)
    return _as_text(s)


def _flatten_toon(toon: dict, filename: str) -> dict:
    """Flatten one TOON resume to a row dict for Excel."""
    if not isinstance(toon, dict):
        toon = {}
    person = toon.get('person') or {}
    if not isinstance(person, dict):
        person = {}
    skills = toon.get('skills') or []
    exp = toon.get('experience') or []
    edu = toon.get('education') or []
    certs = toon.get('certifications') or []

    if not isinstance(skills, list):
        skills = [skills] if skills else []
    if not isinstance(exp, list):
        exp = []
    if not isinstance(edu, list):
        edu = []
    if not isinstance(certs, list):
        certs = [certs] if certs else []

    exp_parts = []
    for e in exp[:25]:
        if not isinstance(e, dict):
            continue
        title = _as_text(e.get('title'))
        company = _as_text(e.get('company'))
        fr = _as_text(e.get('from'))
        to = _as_text(e.get('to'))
        desc = _as_text(e.get('description'))
        chunk = f'{title} at {company} ({fr}-{to})'.strip()
        if desc:
            chunk = f'{chunk}: {desc[:400]}'
        if chunk and chunk != 'at ()':
            exp_parts.append(chunk)

    edu_parts = []
    for e in edu[:15]:
        if not isinstance(e, dict):
            continue
        degree = _as_text(e.get('degree'))
        inst = _as_text(e.get('institution'))
        field = _as_text(e.get('field'))
        year = _as_text(e.get('year') or e.get('to') or e.get('from'))
        chunk = degree
        if field:
            chunk = f'{chunk} ({field})' if chunk else field
        if inst:
            chunk = f'{chunk} - {inst}' if chunk else inst
        if year:
            chunk = f'{chunk} [{year}]' if chunk else year
        if chunk:
            edu_parts.append(chunk)

    skill_strs = [_skill_to_str(s) for s in skills[:50]]
    skill_strs = [s for s in skill_strs if s]
    cert_strs = [_cert_to_str(c) for c in certs[:30]]
    cert_strs = [c for c in cert_strs if c]

    years = toon.get('total_experience_years')
    if years is None or years == '':
        years_out = ''
    else:
        years_out = years

    return {
        'Filename': filename,
        'Name': _as_text(person.get('name')),
        'Email': _normalize_email(person.get('email')),
        'Phone': _normalize_phone(person.get('phone')),
        'LinkedIn': _as_text(person.get('linkedin')),
        'GitHub': _as_text(person.get('github')),
        'Summary': _as_text(toon.get('summary'))[:2000],
        'Skills': ', '.join(skill_strs)[:4000],
        'Experience': '; '.join(exp_parts)[:8000],
        'Education': '; '.join(edu_parts)[:3000],
        'Certifications': ', '.join(cert_strs)[:2000],
        'Total Experience Years': years_out,
        'ParseStatus': 'ok',
        'ParseNotes': '',
    }


def _build_excel_bytes(rows: list[dict]) -> bytes:
    """Build .xlsx from list of row dicts using openpyxl."""
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = 'Resumes'
    headers = EXCEL_HEADERS
    ws.append(headers)
    for r in rows:
        ws.append([r.get(h, '') for h in headers])
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = min(40, max(10, len(str(headers[col - 1])) + 2))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _bulk_timing_begin(filename: str, job_id: str | None = None):
    """Start a Developer Mode session for one bulk file (worker thread). Returns (ctx, wall_start) or (None, None)."""
    try:
        from app.core.developer_mode import is_developer_mode_enabled
        from app.core.request_context import start_request_context
        from app.core.timing_collector import timing_collector

        if not is_developer_mode_enabled():
            return None, None
        path = f"/api/admin/bulk-parse/{filename}"
        ctx = start_request_context(path=path, method="WORKER")
        if job_id:
            ctx.job_id = str(job_id)
        timing_collector.begin_session(
            request_id=ctx.request_id,
            started_at=ctx.started_at_iso,
            path=ctx.path,
            method=ctx.method,
            user_id=ctx.user_id,
            job_id=str(job_id) if job_id else None,
        )
        return ctx, time.perf_counter()
    except Exception:
        return None, None


def _bulk_timing_end(ctx, wall_start: float | None, *, failed: bool = False) -> None:
    try:
        if ctx is None:
            return
        from app.core.request_context import set_timing_context
        from app.core.timing_collector import timing_collector

        if failed:
            timing_collector.mark_error(ctx.request_id)
        wall_ms = None
        if wall_start is not None:
            wall_ms = (time.perf_counter() - wall_start) * 1000.0
        timing_collector.end_session(ctx.request_id, wall_duration_ms=wall_ms)
        set_timing_context(None)
    except Exception:
        pass


def _bulk_stage(stage: str, outcome: str, duration_ms: float = 0.0) -> None:
    try:
        from app.core.timing_collector import record_pipeline_stage

        record_pipeline_stage(
            stage,
            outcome,
            duration_ms=duration_ms,
            module="app.workers.bulk_parser",
        )
    except Exception:
        pass


def _process_one_file(args: tuple) -> tuple[str, dict | None, bool, str, str]:
    """
    Process a single staged file: extract → deterministic rules → LLM if needed.
    Returns (filename, row or None, failed: bool, message, code).
    Codes: insufficient_text | unsupported_format | llm | validation | empty_fields | exception | ok | partial
    """
    # args may be (filename, path) or (filename, path, job_id)
    if len(args) >= 3:
        filename, path, job_id = args[0], args[1], args[2]
    else:
        filename, path = args[0], args[1]
        job_id = None

    ctx, wall_start = _bulk_timing_begin(filename, job_id=job_id)
    failed = True
    try:
        result = _process_one_file_inner(filename, path)
        failed = bool(result[2])
        return result
    finally:
        _bulk_timing_end(ctx, wall_start, failed=failed)


def _process_one_file_inner(filename: str, path: Path) -> tuple[str, dict | None, bool, str, str]:
    from app.ai.parser.text_extraction import extract_text
    from app.domains.recruitment.services.parsing_storage import validate_toon_format_bulk

    try:
        # Bulk text path: no parse-cache / layout / separate raw-store step
        _bulk_stage("cache", "skipped")
        _bulk_stage("persist_raw", "skipped")
        _bulk_stage("layout", "skipped")

        data = path.read_bytes()
        last_extract_err = None
        raw_text = ""
        t_text = time.perf_counter()
        try:
            raw_text = extract_text(data, filename) or ""
        except Exception as extract_err:
            raw_text = ""
            last_extract_err = str(extract_err)[:200]

        if len(raw_text.strip()) < BULK_MIN_TEXT_CHARS and filename.lower().endswith(".pdf"):
            try:
                raw_text = extract_text(data, filename, dpi=BULK_OCR_RETRY_DPI) or ""
                last_extract_err = None
            except Exception as retry_err:
                last_extract_err = str(retry_err)[:200]

        text_ms = (time.perf_counter() - t_text) * 1000.0
        if not raw_text or len(raw_text.strip()) < BULK_MIN_TEXT_CHARS:
            _bulk_stage("text", "failed", text_ms)
            detail = last_extract_err or "insufficient text after OCR"
            low = (detail or "").lower()
            if "legacy .doc" in low or (
                filename.lower().endswith(".doc") and "not supported" in low
            ):
                return (
                    filename,
                    None,
                    True,
                    f"Skipped (unsupported format): {filename} - {detail}",
                    "unsupported_format",
                )
            return (
                filename,
                None,
                True,
                f"Skipped (insufficient text): {filename} - {detail}",
                "insufficient_text",
            )

        _bulk_stage("text", "completed", text_ms)

        # --- Intelligence Engine text path (shared with single-file parse) ---
        if BULK_SKIP_LLM_WHEN_DETERMINISTIC:
            try:
                from app.ai.parser.engine import parse_resume_text_via_engine
                from app.ai.parser.deterministic_resume import score_resume_toon

                det_toon, source, eng_notes = parse_resume_text_via_engine(
                    raw_text,
                    allow_llm=False,
                    skip_llm_when_deterministic=True,
                )
                conf, missing, passes = score_resume_toon(
                    det_toon if isinstance(det_toon, dict) else {}
                )
                if passes and isinstance(det_toon, dict):
                    t_val = time.perf_counter()
                    accept, notes, parse_status = validate_toon_format_bulk(det_toon, "resume")
                    _bulk_stage(
                        "validate",
                        "completed" if accept else "failed",
                        (time.perf_counter() - t_val) * 1000.0,
                    )
                    if accept:
                        t_persist = time.perf_counter()
                        row = _flatten_toon(det_toon, filename)
                        note_bits = [f"source=engine:{source}", f"conf={conf:.2f}"]
                        note_bits.extend(eng_notes[:4])
                        if missing:
                            note_bits.append("weak=" + ",".join(missing[:6]))
                        if notes:
                            note_bits.append(notes)
                        row["ParseStatus"] = "ok" if parse_status == "ok" else parse_status
                        row["ParseNotes"] = "; ".join(note_bits)[:2000]
                        _bulk_stage(
                            "persist",
                            "completed",
                            (time.perf_counter() - t_persist) * 1000.0,
                        )
                        if (
                            row.get("Name")
                            or row.get("Email")
                            or row.get("Phone")
                            or row.get("Skills")
                            or row.get("Experience")
                        ):
                            return (
                                filename,
                                row,
                                False,
                                f"Processing: {filename} (engine:{source})",
                                parse_status if parse_status in ("ok", "partial") else "ok",
                            )
            except Exception as det_err:
                print(f"[local_bulk_parser] engine det path failed for {filename}: {det_err}")

        # --- Slow path: engine with LLM (section-scoped + knowledge) ---
        toon = None
        last_err = None
        for attempt in range(BULK_LLM_ATTEMPTS):
            try:
                from app.ai.parser.engine import parse_resume_text_via_engine

                toon, source, eng_notes = parse_resume_text_via_engine(
                    raw_text,
                    allow_llm=True,
                    skip_llm_when_deterministic=False,
                )
                if not isinstance(toon, dict):
                    last_err = "Engine returned non-object"
                    toon = None
                    if attempt < BULK_LLM_ATTEMPTS - 1:
                        time.sleep(min(30, 2**attempt))
                    continue
                t_val = time.perf_counter()
                accept, notes, parse_status = validate_toon_format_bulk(toon, "resume")
                _bulk_stage(
                    "validate",
                    "completed" if accept else "failed",
                    (time.perf_counter() - t_val) * 1000.0,
                )
                if accept:
                    t_persist = time.perf_counter()
                    row = _flatten_toon(toon, filename)
                    note_bits = [f"source=engine:{source}", f"status={parse_status}"]
                    note_bits.extend(eng_notes[:4])
                    if notes:
                        note_bits.append(notes)
                    row["ParseStatus"] = parse_status
                    row["ParseNotes"] = "; ".join(note_bits)[:2000]
                    _bulk_stage(
                        "persist",
                        "completed",
                        (time.perf_counter() - t_persist) * 1000.0,
                    )
                    if not (
                        row.get("Name")
                        or row.get("Email")
                        or row.get("Phone")
                        or row.get("Skills")
                        or row.get("Experience")
                    ):
                        last_err = "empty fields after flatten"
                        toon = None
                        continue
                    return (
                        filename,
                        row,
                        False,
                        f"Processing: {filename} (engine:{source})",
                        parse_status if parse_status in ("ok", "partial") else "ok",
                    )
                last_err = notes or "validation failed"
                toon = None
            except Exception as e:
                last_err = str(e)[:200]
                toon = None
                if _is_retryable_llm_error(last_err) and attempt < BULK_LLM_ATTEMPTS - 1:
                    time.sleep(min(45, 2**attempt + 1))
                    continue

        if last_err and "empty fields" in (last_err or ""):
            return (
                filename,
                None,
                True,
                f"Failed (empty fields): {filename}",
                "empty_fields",
            )
        code = "validation" if last_err and "validation" in (last_err or "").lower() else "llm"
        if last_err and any(
            x in (last_err or "").lower()
            for x in ("person.", "missing", "must not", "insufficient fields")
        ):
            code = "validation"
        return (
            filename,
            None,
            True,
            f"Failed (parse/validate): {filename} - {last_err}",
            code,
        )
    except Exception as e:
        return (filename, None, True, f"Failed: {filename} - {str(e)[:100]}", "exception")


def _load_staged_files(job_id: str) -> list[tuple[str, Path]]:
    with _local_jobs_lock:
        job = _local_jobs.get(job_id) or {}
        names = list(job.get('staged_filenames') or [])
    out = []
    for name in names:
        p = _staging_dir(job_id) / name
        if p.is_file():
            out.append((name, p))
    return out


def _worker(job_id: str, started_at: float, append: bool = False) -> None:
    """Background: process staged files in parallel, update progress, write Excel."""
    from app.domains.administration.repositories.bulk_session_db import (
        finalize_session,
        update_file_status,
        update_session_progress,
    )

    with _local_jobs_lock:
        job = _local_jobs.get(job_id)
    if not job or job.get('status') == 'cancelled':
        return

    files_list = _load_staged_files(job_id)
    total = len(files_list)
    results: list[dict] = []
    success_count = 0
    failed_count = 0
    max_workers = min(BULK_PARSE_MAX_WORKERS, max(1, total))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {
            executor.submit(_process_one_file, (item[0], item[1], job_id)): item[0]
            for item in files_list
        }
        for future in as_completed(future_to_file):
            with _local_jobs_lock:
                j = _local_jobs.get(job_id)
            if not j or j.get('status') == 'cancelled':
                break
            filename, row, is_failed, message, code = future.result()
            if is_failed:
                failed_count += 1
                update_file_status(job_id, filename, 'Failed', error_message=message)
                with _local_jobs_lock:
                    if job_id in _local_jobs:
                        _local_jobs[job_id].setdefault('failed_filenames', []).append(filename)
                        _local_jobs[job_id].setdefault('failed_details', []).append(
                            {'filename': filename, 'error': message, 'code': code}
                        )
            else:
                if row:
                    results.append(row)
                success_count += 1
                notes = (row or {}).get('ParseNotes') or None
                update_file_status(job_id, filename, 'Completed', error_message=notes)
                with _local_jobs_lock:
                    if job_id in _local_jobs:
                        _local_jobs[job_id].setdefault('success_filenames', []).append(filename)
            done = success_count + failed_count
            update_session_progress(job_id, done, success_count, failed_count)
            with _local_jobs_lock:
                if job_id in _local_jobs:
                    _local_jobs[job_id]['processed_files'] = done
                    _local_jobs[job_id]['failed_files'] = failed_count
                    _local_jobs[job_id]['message'] = message
            # Checkpoint Excel during long runs so progress survives restarts
            if results and done > 0 and done % BULK_EXCEL_CHECKPOINT_EVERY == 0:
                _persist_excel(job_id, list(results), append=append)

    with _local_jobs_lock:
        if job_id in _local_jobs:
            _local_jobs[job_id]['status'] = 'completed'
            _local_jobs[job_id]['processed_files'] = success_count + failed_count
            _local_jobs[job_id]['failed_files'] = failed_count
            _local_jobs[job_id]['results'] = results
            _local_jobs[job_id]['message'] = f'Completed: {success_count} successful, {failed_count} failed'

    if results:
        _persist_excel(job_id, results, append=append)
    elif append and _export_path(job_id).is_file():
        pass  # keep existing workbook
    else:
        _persist_excel(job_id, [], append=False)

    finalize_session(job_id, started_at, success_count, failed_count)


def create_local_job(started_by=None, append: bool = False) -> tuple[str, dict]:
    """Create an empty bulk job ready to receive file chunks. Returns (job_id, payload)."""
    from app.domains.administration.repositories.bulk_session_db import create_empty_session

    job_id = None
    if started_by:
        job_id = create_empty_session(started_by)
    if not job_id:
        job_id = str(uuid.uuid4())

    _staging_dir(job_id).mkdir(parents=True, exist_ok=True)
    with _local_jobs_lock:
        _local_jobs[job_id] = {
            'status': 'pending',
            'total_files': 0,
            'processed_files': 0,
            'failed_files': 0,
            'results': [],
            'message': 'Waiting for uploads...',
            'failed_filenames': [],
            'success_filenames': [],
            'failed_details': [],
            'staged_filenames': [],
            'started_by': started_by,
            'append': bool(append),
            'started_at': None,
        }
    return job_id, {
        'job_id': job_id,
        'total_files': 0,
        'status': 'pending',
        'message': 'Bulk parse job created. Upload files, then start.',
    }


def _ensure_job(job_id: str, started_by=None, append: bool = False) -> dict | None:
    with _local_jobs_lock:
        job = _local_jobs.get(job_id)
        if job:
            if append:
                job['append'] = True
            return job
    # Recreate from DB owner if needed
    from app.domains.administration.repositories.bulk_session_db import get_session_owner

    owner = get_session_owner(job_id)
    if not owner and not started_by:
        return None
    _staging_dir(job_id).mkdir(parents=True, exist_ok=True)
    with _local_jobs_lock:
        if job_id not in _local_jobs:
            _local_jobs[job_id] = {
                'status': 'pending',
                'total_files': 0,
                'processed_files': 0,
                'failed_files': 0,
                'results': [],
                'message': 'Waiting for uploads...',
                'failed_filenames': [],
                'success_filenames': [],
                'failed_details': [],
                'staged_filenames': [],
                'started_by': owner or started_by,
                'append': bool(append),
                'started_at': None,
            }
        return _local_jobs[job_id]


def stage_files(job_id: str, files_list: list[tuple[str, bytes]], started_by=None) -> tuple[bool, dict]:
    """
    Stage resume bytes on disk for an existing (or newly ensured) job.
    files_list: list of (filename, bytes).
    """
    job = _ensure_job(job_id, started_by=started_by)
    if not job:
        return False, {'error': 'Job not found'}
    with _local_jobs_lock:
        status = job.get('status')
    if status not in ('pending', 'uploading'):
        return False, {'error': f'Cannot upload to job in status {status}'}

    from app.domains.administration.repositories.bulk_session_db import add_session_files, bump_session_total

    staged_names: list[str] = []
    file_bytes_for_db: list[bytes] = []
    for original_name, data in files_list:
        if not data:
            continue
        ext = original_name.rsplit('.', 1)[-1].lower() if '.' in original_name else ''
        if ext not in ALLOWED_EXT:
            continue
        staged_name = _unique_staged_name(job_id, original_name)
        (_staging_dir(job_id) / staged_name).write_bytes(data)
        staged_names.append(staged_name)
        file_bytes_for_db.append(data)

    if not staged_names:
        return False, {'error': 'No valid resume files (PDF/DOC/DOCX)'}

    with _local_jobs_lock:
        if job_id in _local_jobs:
            _local_jobs[job_id]['status'] = 'uploading'
            _local_jobs[job_id].setdefault('staged_filenames', []).extend(staged_names)
            _local_jobs[job_id]['total_files'] = len(_local_jobs[job_id]['staged_filenames'])
            _local_jobs[job_id]['message'] = f"Uploaded {_local_jobs[job_id]['total_files']} file(s)"
            total = _local_jobs[job_id]['total_files']

    add_session_files(job_id, staged_names, file_bytes_for_db)
    bump_session_total(job_id, total)

    return True, {
        'job_id': job_id,
        'added_files': len(staged_names),
        'total_files': total,
        'status': 'uploading',
        'message': f'Added {len(staged_names)} file(s). Total staged: {total}.',
    }


def extract_zip_to_job(job_id: str, zip_bytes: bytes, started_by=None) -> tuple[bool, dict]:
    """Extract PDF/DOC/DOCX from a zip archive into the job staging directory."""
    job = _ensure_job(job_id, started_by=started_by)
    if not job:
        return False, {'error': 'Job not found'}
    with _local_jobs_lock:
        status = job.get('status')
    if status not in ('pending', 'uploading'):
        return False, {'error': f'Cannot upload to job in status {status}'}

    extracted: list[tuple[str, bytes]] = []
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                name = info.filename.replace('\\', '/')
                # Skip macOS junk / hidden
                parts = name.split('/')
                if any(p.startswith('.') or p == '__MACOSX' for p in parts):
                    continue
                base = parts[-1]
                if not base or '.' not in base:
                    continue
                ext = base.rsplit('.', 1)[-1].lower()
                if ext not in ALLOWED_EXT:
                    continue
                try:
                    data = zf.read(info)
                except Exception:
                    continue
                if data:
                    # Preserve nested path so subfolder duplicates stay unique
                    flat_name = '__'.join(p for p in parts if p) if len(parts) > 1 else base
                    extracted.append((flat_name, data))
    except zipfile.BadZipFile:
        return False, {'error': 'Invalid ZIP file'}
    except Exception as e:
        return False, {'error': f'ZIP extract failed: {e}'}

    if not extracted:
        return False, {'error': 'No valid resume files (PDF/DOC/DOCX) found in ZIP'}

    return stage_files(job_id, extracted, started_by=started_by)


def start_staged_job(job_id: str, append: bool | None = None) -> tuple[bool, dict]:
    """Start processing all staged files for a job."""
    with _local_jobs_lock:
        job = _local_jobs.get(job_id)
        if not job:
            return False, {'error': 'Job not found'}
        if job.get('status') in ('started', 'completed'):
            return False, {'error': f'Job already {job.get("status")}'}
        total = len(job.get('staged_filenames') or [])
        if total == 0:
            return False, {'error': 'No files uploaded for this job'}
        if append is not None:
            job['append'] = bool(append)
        use_append = bool(job.get('append'))
        started_at = time.time()
        job['status'] = 'started'
        job['started_at'] = started_at
        job['processed_files'] = 0
        job['failed_files'] = 0
        job['failed_filenames'] = []
        job['success_filenames'] = []
        job['results'] = []
        job['message'] = 'Processing...'
        job['total_files'] = total

    from app.domains.administration.repositories.bulk_session_db import mark_session_running

    mark_session_running(job_id, total)

    t = threading.Thread(target=_worker, args=(job_id, started_at, use_append), daemon=True)
    t.start()
    return True, {
        'job_id': job_id,
        'total_files': total,
        'status': 'started',
        'message': 'Local bulk parsing started.',
    }


def start_local_job(files_list: list[tuple[str, bytes]], started_by=None, append: bool = False) -> tuple[str, dict]:
    """
    Backward-compatible: create job, stage all files, start immediately.
    Returns (job_id, payload).
    """
    job_id, _ = create_local_job(started_by=started_by, append=append)
    ok, staged = stage_files(job_id, files_list, started_by=started_by)
    if not ok:
        with _local_jobs_lock:
            _local_jobs.pop(job_id, None)
        raise ValueError(staged.get('error', 'Upload failed'))
    ok, result = start_staged_job(job_id, append=append)
    if not ok:
        raise ValueError(result.get('error', 'Start failed'))
    return job_id, result


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
            'failed_details': job.get('failed_details', []),
        }

    from app.domains.administration.repositories.bulk_session_db import get_session_owner, get_session_progress

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
    export_file = _export_path(job_id)
    with _local_jobs_lock:
        job = _local_jobs.get(job_id)
    if job:
        if job['status'] != 'completed':
            return False, {'error': 'Job not completed yet'}
        if export_file.is_file():
            return True, (
                io.BytesIO(export_file.read_bytes()),
                'Parsed_Resumes.xlsx',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
        rows = job.get('results') or []
        try:
            xlsx_bytes = _build_excel_bytes(rows)
        except Exception as e:
            return False, {'error': f'Excel build failed: {e}'}
        return True, (
            io.BytesIO(xlsx_bytes),
            'Parsed_Resumes.xlsx',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

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
