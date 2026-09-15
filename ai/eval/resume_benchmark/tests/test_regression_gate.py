"""Regression gate: the parser may not get worse than the locked thresholds.

Skipped automatically when the gold corpus has not been ingested on this
machine (it holds real candidate documents and is never committed). Opt in
explicitly in CI or locally:

    RESUME_BENCHMARK_GATE=1 pytest ai/eval/resume_benchmark/tests/test_regression_gate.py -v
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from resume_benchmark.config import (  # noqa: E402
    BACKEND,
    CORPUS_MANIFEST,
    FIELDS,
    THRESHOLDS_FILE,
    load_thresholds,
)

pytestmark = pytest.mark.skipif(
    not CORPUS_MANIFEST.exists(),
    reason=f'no gold corpus at {CORPUS_MANIFEST} - run ingest.py first',
)

GATE_ENABLED = os.getenv('RESUME_BENCHMARK_GATE', '').strip().lower() in {'1', 'true', 'yes', 'on'}


@pytest.fixture(scope='module')
def benchmark_payload() -> dict:
    if not GATE_ENABLED:
        pytest.skip('set RESUME_BENCHMARK_GATE=1 to run the full benchmark (minutes)')
    for path in (str(BACKEND), str(BACKEND / 'app')):
        if path not in sys.path:
            sys.path.insert(0, path)

    from resume_benchmark.predict import ocr_status

    ocr_available, ocr_detail = ocr_status()
    if not ocr_available:
        # Scanned resumes would score zero, failing the gate for a reason that
        # has nothing to do with the parser.
        pytest.skip(
            f'no OCR engine in this interpreter ({ocr_detail}); the thresholds were '
            'locked with OCR available. Run with apps/backend/venv.'
        )

    from resume_benchmark.ingest import load_case_gold, load_manifest
    from resume_benchmark.predict import predict_all
    from resume_benchmark.report import build_summary
    from resume_benchmark.scoring import case_accuracy, score_case
    from resume_benchmark.triage import field_rollup

    manifest = load_manifest()
    case_ids = [c['case_id'] for c in manifest['cases']]
    workers = int(os.getenv('RESUME_BENCHMARK_WORKERS', '4'))
    predictions = predict_all(case_ids, workers=workers, progress=False)

    case_results = []
    for pred in predictions:
        results = score_case(load_case_gold(pred['case_id']), pred.get('prediction') or {}, FIELDS)
        case_results.append({
            'case_id': pred['case_id'],
            'accuracy': case_accuracy(results, FIELDS),
            'error': pred.get('error', ''),
            'fields': [r.to_dict() for r in results],
        })
    return {
        'summary': build_summary(case_results, {'allow_semantic': False}),
        'fields': field_rollup(case_results),
        'cases': case_results,
    }


def test_thresholds_file_covers_every_scored_field():
    thresholds = load_thresholds()
    if not thresholds:
        pytest.skip('no thresholds locked yet - run with --write-thresholds')
    locked = set((thresholds.get('fields') or {}))
    # Fields whose gold column is empty across the corpus never get a score.
    assert locked <= {f.key for f in FIELDS}
    assert {'fullName', 'email', 'phone', 'skills', 'education', 'experiences'} <= locked


def test_no_regression_against_locked_thresholds(benchmark_payload):
    from resume_benchmark.report import compare_to_thresholds

    thresholds = load_thresholds()
    if not thresholds:
        pytest.skip('no thresholds locked yet - run with --write-thresholds')
    violations = compare_to_thresholds(benchmark_payload, thresholds)
    assert not violations, 'benchmark regressed:\n  ' + '\n  '.join(violations)


def test_every_case_still_produces_a_prediction(benchmark_payload):
    """Extraction failures are allowed only where the threshold file records them."""
    thresholds = load_thresholds()
    allowed = int((thresholds.get('overall') or {}).get('max_cases_failed', 0))
    failed = [c['case_id'] for c in benchmark_payload['cases'] if c.get('error')]
    assert len(failed) <= allowed, f'new parse failures: {failed}'
