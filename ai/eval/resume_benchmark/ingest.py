"""Build the gold corpus from the benchmark spreadsheet + resume files.

    python ai/eval/resume_benchmark/ingest.py \
        --xlsx "actual resume result.xlsx" --resumes "resume testing"

Re-run this whenever the spreadsheet gains rows or a cell is corrected. It is
idempotent: cases are keyed by file name, and existing extracted text is reused
unless ``--reextract`` is passed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

if __package__ in (None, ''):  # direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = 'resume_benchmark'

from .config import (  # noqa: E402
    CASES_DIR,
    CORPUS_DIR,
    CORPUS_MANIFEST,
    FIELDS,
    FILENAME_COLUMN,
    GOLD_COLUMNS,
)
from .gold_parser import audit_row, parse_section  # noqa: E402

SECTION_KEYS = ('education', 'experiences', 'certifications')


def _case_id(filename: str) -> str:
    stem = Path(filename).stem
    slug = ''.join(c if c.isalnum() else '_' for c in stem).strip('_').lower()[:48]
    digest = hashlib.sha1(filename.encode('utf-8')).hexdigest()[:6]
    return f'{slug}__{digest}'


def read_rows(xlsx: Path, sheet: str | None = None) -> list[dict]:
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover - environment guard
        raise SystemExit('openpyxl is required: pip install openpyxl') from exc

    wb = openpyxl.load_workbook(xlsx, data_only=True, read_only=True)
    ws = wb[sheet] if sheet else wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise SystemExit(f'{xlsx} has no rows')
    header = [str(h).strip() if h is not None else '' for h in rows[0]]
    missing = [c for c in (FILENAME_COLUMN, *GOLD_COLUMNS) if c not in header]
    if missing:
        raise SystemExit(f'spreadsheet is missing columns: {missing}\nfound: {header}')
    out: list[dict] = []
    for raw in rows[1:]:
        if not any(v not in (None, '') for v in raw):
            continue
        record = {k: v for k, v in zip(header, raw) if k}
        if not str(record.get(FILENAME_COLUMN) or '').strip():
            continue
        out.append(record)
    wb.close()
    return out


def _gold_payload(row: dict) -> dict:
    gold: dict = {}
    for spec in FIELDS:
        value = row.get(spec.gold_column)
        text = '' if value is None else str(value).strip()
        gold[spec.key] = text
    sections = {}
    for key in SECTION_KEYS:
        column = next(f.gold_column for f in FIELDS if f.key == key)
        entries = parse_section(key, row.get(column))
        sections[key] = [e.to_dict() for e in entries]
    gold['_sections'] = sections
    return gold


def build(
    xlsx: Path,
    resumes_dir: Path,
    *,
    sheet: str | None = None,
    copy_binaries: bool = True,
) -> dict:
    rows = read_rows(xlsx, sheet)
    available = {p.name: p for p in resumes_dir.rglob('*') if p.is_file()}
    lowered = {name.lower(): p for name, p in available.items()}

    CASES_DIR.mkdir(parents=True, exist_ok=True)
    cases: list[dict] = []
    unmatched: list[str] = []
    audit: dict[str, list[str]] = {}

    for row in rows:
        filename = str(row[FILENAME_COLUMN]).strip()
        source = available.get(filename) or lowered.get(filename.lower())
        if source is None:
            unmatched.append(filename)
            continue

        case_id = _case_id(filename)
        case_dir = CASES_DIR / case_id
        case_dir.mkdir(parents=True, exist_ok=True)

        target = case_dir / f'source{source.suffix.lower()}'
        if copy_binaries and (not target.exists() or target.stat().st_size != source.stat().st_size):
            shutil.copy2(source, target)

        gold = _gold_payload(row)
        (case_dir / 'gold.json').write_text(
            json.dumps(gold, indent=2, ensure_ascii=False), encoding='utf-8'
        )
        (case_dir / 'gold_raw.json').write_text(
            json.dumps({k: (None if v is None else str(v)) for k, v in row.items()},
                       indent=2, ensure_ascii=False),
            encoding='utf-8',
        )

        issues = audit_row(row)
        if issues:
            audit[case_id] = issues

        cases.append({
            'case_id': case_id,
            'file_name': filename,
            'source_path': str(target if copy_binaries else source),
            'suffix': source.suffix.lower(),
            'bytes': source.stat().st_size,
            'gold_issues': issues,
            'filled_fields': sum(1 for spec in FIELDS if gold.get(spec.key)),
        })

    manifest = {
        'version': 1,
        'xlsx': str(xlsx),
        'resumes_dir': str(resumes_dir),
        'case_count': len(cases),
        'unmatched_rows': unmatched,
        'gold_issue_count': sum(len(v) for v in audit.values()),
        'gold_issues': audit,
        'cases': cases,
    }
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    CORPUS_MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8'
    )
    return manifest


def load_manifest() -> dict:
    if not CORPUS_MANIFEST.exists():
        raise SystemExit(
            f'No gold corpus at {CORPUS_MANIFEST}.\n'
            'Run: python ai/eval/resume_benchmark/ingest.py --xlsx <file> --resumes <dir>'
        )
    return json.loads(CORPUS_MANIFEST.read_text(encoding='utf-8'))


def load_case_gold(case_id: str) -> dict:
    return json.loads((CASES_DIR / case_id / 'gold.json').read_text(encoding='utf-8'))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--xlsx', required=True, type=Path, help='benchmark spreadsheet')
    ap.add_argument('--resumes', required=True, type=Path, help='directory of resume files')
    ap.add_argument('--sheet', default=None)
    ap.add_argument('--no-copy', action='store_true', help='reference files in place')
    args = ap.parse_args()

    if not args.xlsx.exists():
        raise SystemExit(f'not found: {args.xlsx}')
    if not args.resumes.exists():
        raise SystemExit(f'not found: {args.resumes}')

    manifest = build(
        args.xlsx.resolve(),
        args.resumes.resolve(),
        sheet=args.sheet,
        copy_binaries=not args.no_copy,
    )
    print(f'corpus     : {CORPUS_DIR}')
    print(f'cases      : {manifest["case_count"]}')
    if manifest['unmatched_rows']:
        print(f'UNMATCHED  : {len(manifest["unmatched_rows"])} rows had no resume file')
        for name in manifest['unmatched_rows'][:10]:
            print(f'             - {name}')
    if manifest['gold_issues']:
        print(f'GOLD ISSUES: {manifest["gold_issue_count"]} across '
              f'{len(manifest["gold_issues"])} cases (see manifest.json)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
