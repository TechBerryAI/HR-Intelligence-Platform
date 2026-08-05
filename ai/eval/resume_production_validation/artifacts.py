"""Write validation artifacts under validation-report/."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def ensure_report_dirs(out_dir: Path) -> dict[str, Path]:
    dirs = {
        'root': out_dir,
        'screenshots': out_dir / 'screenshots',
        'screenshots_passed': out_dir / 'screenshots' / 'passed',
        'screenshots_failed': out_dir / 'screenshots' / 'failed',
        'parsed_json': out_dir / 'parsed-json',
        'logs': out_dir / 'logs',
        'grouped': out_dir / 'grouped-failures',
    }
    for p in dirs.values():
        p.mkdir(parents=True, exist_ok=True)
    return dirs


def safe_name(name: str, max_len: int = 80) -> str:
    cleaned = re.sub(r'[^A-Za-z0-9._-]+', '_', name).strip('_')
    return (cleaned or 'case')[:max_len]


def write_case_artifacts(
    dirs: dict[str, Path],
    *,
    case_id: str,
    filename: str,
    passed: bool,
    parse_payload: dict | None,
    form_state: dict | None,
    evaluation: dict,
    log_lines: list[str],
    screenshot_bytes: bytes | None,
) -> dict[str, str]:
    sid = safe_name(case_id)
    paths: dict[str, str] = {}

    payload = {
        'case_id': case_id,
        'filename': filename,
        'passed': passed,
        'evaluation': evaluation,
        'form_state': form_state,
        'parse_payload': parse_payload,
    }
    # Always store JSON for failed; also store a compact index entry for all via caller
    json_path = dirs['parsed_json'] / f'{sid}.json'
    if not passed or parse_payload is not None:
        json_path.write_text(json.dumps(payload, indent=2, default=str), encoding='utf-8')
        paths['parsed_json'] = str(json_path.relative_to(dirs['root']))

    log_path = dirs['logs'] / f'{sid}.log'
    log_path.write_text('\n'.join(log_lines) + '\n', encoding='utf-8')
    paths['log'] = str(log_path.relative_to(dirs['root']))

    if screenshot_bytes:
        shot_dir = dirs['screenshots_passed'] if passed else dirs['screenshots_failed']
        shot_path = shot_dir / f'{sid}.png'
        shot_path.write_bytes(screenshot_bytes)
        paths['screenshot'] = str(shot_path.relative_to(dirs['root']))

    return paths


def append_checkpoint(checkpoint_path: Path, row: dict[str, Any]) -> None:
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    with checkpoint_path.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(row, default=str) + '\n')


def load_checkpoint(checkpoint_path: Path) -> dict[str, dict]:
    done: dict[str, dict] = {}
    if not checkpoint_path.exists():
        return done
    with checkpoint_path.open(encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            cid = row.get('case_id')
            if cid:
                done[cid] = row
    return done


_INFRA_SIGNATURE_MARKERS = (
    'err_connection_refused',
    'err_network_changed',
    'err_connection_reset',
    'err_empty_response',
    'err_aborted',
    'net::err_',
    'timeout',
    'process_error:',
    'frontend:page.goto',
    'frontend:page.wait',
)


def is_infra_failure_row(row: dict) -> bool:
    """True for checkpoint rows that should be retested after service outages."""
    if row.get('passed') or row.get('unsupported'):
        return False
    cat = (row.get('category') or '').strip()
    sig = (row.get('signature') or '').lower()
    if cat in ('Frontend', 'Timeout'):
        return True
    return any(m in sig for m in _INFRA_SIGNATURE_MARKERS)


def invalidate_infra_checkpoint(checkpoint_path: Path) -> tuple[dict[str, dict], int]:
    """
    Drop Frontend/Timeout/infra rows from checkpoint so they are re-queued.
    Rewrites checkpoint.jsonl in place. Returns (kept_by_id, dropped_count).
    """
    if not checkpoint_path.exists():
        return {}, 0
    kept: dict[str, dict] = {}
    dropped = 0
    lines_out: list[str] = []
    with checkpoint_path.open(encoding='utf-8') as fh:
        for line in fh:
            raw = line.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            cid = row.get('case_id')
            if not cid:
                continue
            if is_infra_failure_row(row):
                dropped += 1
                continue
            kept[cid] = row
            lines_out.append(json.dumps(row, default=str))
    checkpoint_path.write_text(
        ('\n'.join(lines_out) + '\n') if lines_out else '',
        encoding='utf-8',
    )
    return kept, dropped
