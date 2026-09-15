"""Run the production resume pipeline over the gold corpus.

This mirrors ``_run_resume`` in ``app.ai.document_intelligence.pipeline`` minus
the database: extract -> prepare working text -> parse -> map to the form DTO.
Whatever the Apply screen would show is what gets scored.
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .config import BACKEND, CASES_DIR

_EXTRACT_CACHE_NAME = 'extracted.txt'
_EXTRACT_META_NAME = 'extract_meta.json'


def ensure_backend_on_path() -> None:
    for candidate in (str(BACKEND), str(BACKEND / 'app')):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)


def ocr_status() -> tuple[bool, str]:
    """``(available, engine_or_reason)`` for the interpreter running the benchmark.

    Scanned resumes only yield text through OCR, so a run without an engine
    scores a different corpus than a run with one. Callers must surface this.
    """
    ensure_backend_on_path()
    try:
        from app.ai.parser.text_extraction import get_ocr_engine_status

        return get_ocr_engine_status()
    except Exception as exc:  # noqa: BLE001 - probe must never break a run
        return False, f'probe failed: {type(exc).__name__}: {exc}'


def _source_file(case_dir: Path) -> Path | None:
    for path in sorted(case_dir.glob('source.*')):
        if path.suffix.lower() != '.txt':
            return path
    return None


def _cache_is_stale(meta: dict, ocr_available: bool) -> str:
    """Reason the cached text must be thrown away, or '' to keep it.

    Text extracted while no OCR engine was installed is not comparable to text
    extracted with one: a scanned resume cached as an empty string would keep
    scoring zero forever, long after OCR became available.
    """
    if not meta:
        return 'no extraction metadata recorded'
    if ocr_available and not meta.get('ocr_available', False):
        return 'cached without an OCR engine; one is available now'
    return ''


def extract_case_text(case_dir: Path, *, reextract: bool = False) -> tuple[str, dict]:
    """Extracted text for a case, cached on disk next to the source file."""
    ensure_backend_on_path()
    cache = case_dir / _EXTRACT_CACHE_NAME
    meta_path = case_dir / _EXTRACT_META_NAME
    ocr_available, ocr_engine = ocr_status()

    if cache.exists() and not reextract:
        try:
            cached_meta = json.loads(meta_path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            cached_meta = {}
        stale = _cache_is_stale(cached_meta, ocr_available)
        if not stale:
            return cache.read_text(encoding='utf-8'), {**cached_meta, 'cached': True}

    source = _source_file(case_dir)
    if source is None:
        return '', {'error': 'no source file', 'ocr_available': ocr_available}

    from app.ai.parser.text_extraction import extract_document

    started = time.perf_counter()
    result = extract_document(source.read_bytes(), source.name)
    text = (result.text or '').replace('\x00', '')
    meta = {
        'chars': len(text),
        'used_ocr': bool(getattr(result, 'used_ocr', False)),
        'ocr_engine': str(getattr(result, 'ocr_engine', '') or ''),
        'ocr_pages': list(getattr(result, 'ocr_pages', None) or []),
        'final_dpi': getattr(result, 'final_dpi', 0),
        'source': getattr(result, 'source', ''),
        'ocr_available': ocr_available,
        'ocr_engine_status': ocr_engine,
        'extract_ms': round((time.perf_counter() - started) * 1000, 1),
    }
    cache.write_text(text, encoding='utf-8')
    meta_path.write_text(json.dumps(meta, indent=2), encoding='utf-8')
    return text, {**meta, 'cached': False}


def predict_case(case_id: str, *, allow_semantic: bool = False, reextract: bool = False) -> dict:
    """Parse one case. Never raises - failures come back as ``error``."""
    ensure_backend_on_path()
    case_dir = CASES_DIR / case_id
    out: dict[str, Any] = {'case_id': case_id}
    try:
        text, extract_meta = extract_case_text(case_dir, reextract=reextract)
        out['extract'] = extract_meta
        if len(text.strip()) < 30:
            out['error'] = 'insufficient_text'
            out['prediction'] = {}
            return out

        from app.ai.document_intelligence.mapping.resume_form import map_candidate_to_form
        from app.ai.document_intelligence.pipeline import parse_resume_from_working_text
        from app.ai.document_intelligence.resume_preprocess import prepare_resume_working_text

        source = _source_file(case_dir)
        file_data = source.read_bytes() if source else None

        started = time.perf_counter()
        working = prepare_resume_working_text(text, file_data=file_data)
        profile, coverage, _sections, used_llm, _toon = parse_resume_from_working_text(
            working,
            allow_semantic=allow_semantic,
            source_filename=source.name if source else '',
        )
        form = map_candidate_to_form(profile, coverage=coverage.as_dicts())
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)

        payload = form.to_autofill_dict()
        trace = payload.pop('trace', []) or []
        payload.pop('coverage', None)

        out['prediction'] = payload
        out['parse_ms'] = elapsed_ms
        out['used_llm'] = bool(used_llm)
        out['missing_with_evidence'] = list(getattr(coverage, 'missing_with_evidence', []) or [])
        out['trace_sources'] = {
            t.get('form_field'): t.get('source') for t in trace if isinstance(t, dict)
        }
    except Exception as exc:  # noqa: BLE001 - a crash is a benchmark result
        out['error'] = f'{type(exc).__name__}: {exc}'
        out['traceback'] = traceback.format_exc(limit=6)
        out.setdefault('prediction', {})
    return out


def _worker(args: tuple[str, bool, bool]) -> dict:
    case_id, allow_semantic, reextract = args
    return predict_case(case_id, allow_semantic=allow_semantic, reextract=reextract)


def predict_all(
    case_ids: list[str],
    *,
    allow_semantic: bool = False,
    reextract: bool = False,
    workers: int = 1,
    progress: bool = True,
) -> list[dict]:
    if workers <= 1:
        results = []
        for i, case_id in enumerate(case_ids, 1):
            if progress:
                print(f'  [{i}/{len(case_ids)}] {case_id}', flush=True)
            results.append(_worker((case_id, allow_semantic, reextract)))
        return results

    os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
    payloads = [(cid, allow_semantic, reextract) for cid in case_ids]
    results: list[dict] = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_worker, p): p[0] for p in payloads}
        for i, fut in enumerate(as_completed(futures), 1):
            case_id = futures[fut]
            try:
                results.append(fut.result())
            except Exception as exc:  # noqa: BLE001
                results.append({'case_id': case_id, 'error': f'worker_crash: {exc}', 'prediction': {}})
            if progress:
                print(f'  [{i}/{len(case_ids)}] {case_id}', flush=True)
    order = {cid: i for i, cid in enumerate(case_ids)}
    results.sort(key=lambda r: order.get(r['case_id'], 0))
    return results
