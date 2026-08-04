"""Playwright runner: production harness upload → autofill → capture."""
from __future__ import annotations

import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

from .artifacts import append_checkpoint, ensure_report_dirs, write_case_artifacts
from .checks import evaluate_case
from .corpus import CorpusItem

_RETRYABLE_MARKERS = (
    'err_connection_refused',
    'err_network_changed',
    'err_connection_reset',
    'err_empty_response',
    'err_aborted',
    'net::err_',
    'target closed',
    'browser has been closed',
    'navigation failed',
)


def _is_retryable_error(exc: BaseException | str) -> bool:
    low = str(exc).lower()
    return any(m in low for m in _RETRYABLE_MARKERS)


def _wait_for_complete(page, timeout_ms: int) -> dict:
    page.wait_for_function(
        """() => {
          const v = window.__RESUME_VALIDATION__;
          return v && (v.status === 'complete' || v.status === 'error');
        }""",
        timeout=timeout_ms,
    )
    return page.evaluate('() => window.__RESUME_VALIDATION__')


def _open_harness(page, base_url: str, log: list[str]) -> None:
    log.append(f'open {base_url}/validation/resume-autofill')
    page.goto(f'{base_url}/validation/resume-autofill', wait_until='networkidle', timeout=60_000)
    page.wait_for_function('() => !!window.__RESUME_VALIDATION_RESET__', timeout=30_000)
    page.evaluate('() => window.__RESUME_VALIDATION_RESET__()')
    page.wait_for_selector('#resume-upload-input', state='attached', timeout=30_000)


def process_one(
    *,
    item: CorpusItem,
    base_url: str,
    timeout_ms: int,
    dirs: dict[str, Path],
    browser,
) -> dict[str, Any]:
    log: list[str] = []
    context = browser.new_context(viewport={'width': 1280, 'height': 1600})
    page = context.new_page()
    timed_out = False
    frontend_error = None
    screenshot_bytes = None
    capture: dict[str, Any] = {}
    elapsed_ms = 0

    try:
        bootstrap_attempts = 0
        while True:
            bootstrap_attempts += 1
            try:
                _open_harness(page, base_url, log)
                break
            except Exception as exc:
                if bootstrap_attempts < 2 and _is_retryable_error(exc):
                    log.append(f'bootstrap_retry: {exc}')
                    time.sleep(2)
                    try:
                        page.close()
                    except Exception:
                        pass
                    page = context.new_page()
                    continue
                raise

        t0 = time.perf_counter()
        log.append(f'upload {item.path}')
        page.set_input_files('#resume-upload-input', str(item.path))
        try:
            capture = _wait_for_complete(page, timeout_ms)
        except Exception as exc:
            timed_out = 'timeout' in str(exc).lower()
            # One retry for transient network blips during upload/parse wait
            if not timed_out and _is_retryable_error(exc):
                log.append(f'parse_wait_retry: {exc}')
                time.sleep(2)
                try:
                    page.close()
                except Exception:
                    pass
                page = context.new_page()
                _open_harness(page, base_url, log)
                t0 = time.perf_counter()
                page.set_input_files('#resume-upload-input', str(item.path))
                try:
                    capture = _wait_for_complete(page, timeout_ms)
                except Exception as exc2:
                    timed_out = 'timeout' in str(exc2).lower()
                    frontend_error = str(exc2)
                    capture = page.evaluate('() => window.__RESUME_VALIDATION__ || {}')
                    log.append(f'wait_failed_after_retry: {exc2}')
            else:
                frontend_error = str(exc)
                capture = page.evaluate('() => window.__RESUME_VALIDATION__ || {}')
                log.append(f'wait_failed: {exc}')

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        if capture and not capture.get('elapsedMs'):
            capture['elapsedMs'] = elapsed_ms

        try:
            page.locator('#autofill-form').scroll_into_view_if_needed()
            screenshot_bytes = page.locator('#autofill-form').screenshot(type='png')
            log.append('screenshot_ok')
        except Exception as exc:
            log.append(f'screenshot_failed: {exc}')
            try:
                screenshot_bytes = page.screenshot(type='png', full_page=True)
            except Exception as exc2:
                log.append(f'full_screenshot_failed: {exc2}')
                screenshot_bytes = None

        capture = dict(capture or {})
        capture['timed_out'] = timed_out
        capture['frontend_error'] = frontend_error
        capture['screenshot_ok'] = bool(screenshot_bytes)
        if elapsed_ms and not capture.get('elapsedMs'):
            capture['elapsedMs'] = elapsed_ms

        evaluation = evaluate_case(capture)
        passed = evaluation['passed']
        paths = write_case_artifacts(
            dirs,
            case_id=item.case_id,
            filename=item.rel_name,
            passed=passed,
            parse_payload=capture.get('parsePayload'),
            form_state=capture.get('form'),
            evaluation=evaluation,
            log_lines=log,
            screenshot_bytes=screenshot_bytes,
        )

        return {
            'case_id': item.case_id,
            'filename': item.rel_name,
            'ext': item.ext,
            'size': item.size,
            'passed': passed,
            'unsupported': False,
            'category': evaluation.get('category') or '',
            'signature': evaluation.get('signature') or '',
            'confidence': evaluation.get('confidence'),
            'elapsed_ms': evaluation.get('elapsed_ms') or capture.get('elapsedMs'),
            'field_accuracy': evaluation.get('field_accuracy'),
            'grounded_ok': evaluation.get('grounded_ok'),
            'grounded_total': evaluation.get('grounded_total'),
            'validation_errors': evaluation.get('validation_errors'),
            'parity_issues': evaluation.get('parity_issues'),
            'grounding_issues': evaluation.get('grounding_issues'),
            'paths': paths,
            'parsed_id': evaluation.get('parsed_id'),
            'partial': evaluation.get('partial'),
            'raw_text_chars': evaluation.get('raw_text_chars'),
        }
    except Exception as exc:
        log.append(f'fatal: {exc}')
        # One full retry for connection refused at top level
        if _is_retryable_error(exc):
            log.append('fatal_retry_once')
            try:
                try:
                    page.close()
                except Exception:
                    pass
                page = context.new_page()
                time.sleep(2)
                _open_harness(page, base_url, log)
                t0 = time.perf_counter()
                page.set_input_files('#resume-upload-input', str(item.path))
                try:
                    capture = _wait_for_complete(page, timeout_ms)
                    timed_out = False
                    frontend_error = None
                except Exception as exc2:
                    timed_out = 'timeout' in str(exc2).lower()
                    frontend_error = str(exc2)
                    capture = page.evaluate('() => window.__RESUME_VALIDATION__ || {}')
                    log.append(f'wait_failed_after_fatal_retry: {exc2}')
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                try:
                    screenshot_bytes = page.locator('#autofill-form').screenshot(type='png')
                except Exception:
                    screenshot_bytes = None
                capture = dict(capture or {})
                capture['timed_out'] = timed_out
                capture['frontend_error'] = frontend_error
                capture['screenshot_ok'] = bool(screenshot_bytes)
                capture['elapsedMs'] = elapsed_ms
                evaluation = evaluate_case(capture)
                paths = write_case_artifacts(
                    dirs,
                    case_id=item.case_id,
                    filename=item.rel_name,
                    passed=evaluation['passed'],
                    parse_payload=capture.get('parsePayload'),
                    form_state=capture.get('form'),
                    evaluation=evaluation,
                    log_lines=log,
                    screenshot_bytes=screenshot_bytes,
                )
                return {
                    'case_id': item.case_id,
                    'filename': item.rel_name,
                    'ext': item.ext,
                    'size': item.size,
                    'passed': evaluation['passed'],
                    'unsupported': False,
                    'category': evaluation.get('category') or '',
                    'signature': evaluation.get('signature') or '',
                    'confidence': evaluation.get('confidence'),
                    'elapsed_ms': evaluation.get('elapsed_ms') or elapsed_ms,
                    'field_accuracy': evaluation.get('field_accuracy'),
                    'grounded_ok': evaluation.get('grounded_ok'),
                    'grounded_total': evaluation.get('grounded_total'),
                    'paths': paths,
                }
            except Exception as exc3:
                log.append(f'fatal_retry_failed: {exc3}')
                exc = exc3

        evaluation = evaluate_case({
            'status': 'error',
            'form': {},
            'parsePayload': None,
            'parseError': str(exc),
            'timed_out': 'timeout' in str(exc).lower(),
            'frontend_error': str(exc),
            'screenshot_ok': False,
        })
        paths = write_case_artifacts(
            dirs,
            case_id=item.case_id,
            filename=item.rel_name,
            passed=False,
            parse_payload=None,
            form_state=None,
            evaluation=evaluation,
            log_lines=log,
            screenshot_bytes=None,
        )
        return {
            'case_id': item.case_id,
            'filename': item.rel_name,
            'ext': item.ext,
            'size': item.size,
            'passed': False,
            'unsupported': False,
            'category': evaluation.get('category') or 'Frontend',
            'signature': evaluation.get('signature') or f'fatal:{exc}',
            'confidence': None,
            'elapsed_ms': None,
            'field_accuracy': 0.0,
            'grounded_ok': 0,
            'grounded_total': 0,
            'paths': paths,
        }
    finally:
        context.close()


def _process_item_in_subprocess(payload: dict) -> dict:
    """One Playwright browser per process (sync API is not thread-safe)."""
    from playwright.sync_api import sync_playwright

    item = CorpusItem(
        path=Path(payload['path']),
        rel_name=payload['rel_name'],
        ext=payload['ext'],
        size=payload['size'],
        supported=True,
        case_id=payload['case_id'],
    )
    out_dir = Path(payload['out_dir'])
    dirs = ensure_report_dirs(out_dir)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=payload.get('headless', True))
        try:
            return process_one(
                item=item,
                base_url=payload['base_url'],
                timeout_ms=payload['timeout_ms'],
                dirs=dirs,
                browser=browser,
            )
        finally:
            browser.close()


def run_corpus(
    items: list[CorpusItem],
    *,
    out_dir: Path,
    base_url: str,
    workers: int = 2,
    timeout_ms: int = 180_000,
    checkpoint_path: Path | None = None,
    already_done: dict[str, dict] | None = None,
    on_result: Callable[[dict], None] | None = None,
    headless: bool = True,
) -> list[dict]:
    from playwright.sync_api import sync_playwright

    dirs = ensure_report_dirs(out_dir)
    checkpoint_path = checkpoint_path or (out_dir / 'checkpoint.jsonl')
    already_done = already_done or {}
    results: list[dict] = []

    pending = [it for it in items if it.case_id not in already_done]
    for _cid, row in already_done.items():
        results.append(row)

    if not pending:
        return results

    def _emit(row: dict) -> None:
        append_checkpoint(checkpoint_path, row)
        results.append(row)
        if on_result:
            on_result(row)

    if workers <= 1:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            try:
                for item in pending:
                    row = process_one(
                        item=item,
                        base_url=base_url,
                        timeout_ms=timeout_ms,
                        dirs=dirs,
                        browser=browser,
                    )
                    _emit(row)
            finally:
                browser.close()
        return results

    payloads = [
        {
            'path': str(it.path),
            'rel_name': it.rel_name,
            'ext': it.ext,
            'size': it.size,
            'case_id': it.case_id,
            'out_dir': str(out_dir),
            'base_url': base_url,
            'timeout_ms': timeout_ms,
            'headless': headless,
        }
        for it in pending
    ]

    # Process pool: each worker owns its own Playwright greenlet/browser.
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_process_item_in_subprocess, pl): pl['case_id'] for pl in payloads}
        for fut in as_completed(futs):
            try:
                row = fut.result()
            except Exception as exc:
                cid = futs[fut]
                row = {
                    'case_id': cid,
                    'filename': cid,
                    'passed': False,
                    'unsupported': False,
                    'category': 'Frontend',
                    'signature': f'process_error:{exc}',
                    'confidence': None,
                    'elapsed_ms': None,
                    'field_accuracy': 0.0,
                    'grounded_ok': 0,
                    'grounded_total': 0,
                    'paths': {},
                }
            _emit(row)

    return results
