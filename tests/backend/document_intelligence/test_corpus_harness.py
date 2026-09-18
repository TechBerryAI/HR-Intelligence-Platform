"""Run the real-resume corpus harness when files are present."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[3] / 'apps' / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault('RESUME_SKIP_LLM_WHEN_DETERMINISTIC', 'true')
os.environ.setdefault('DOCUMENT_INTELLIGENCE_SEMANTIC_AI', 'false')
os.environ.setdefault('PARSING_API_FALLBACK', 'false')

sys.path.insert(0, str(Path(__file__).resolve().parent))
from corpus_harness import corpus_files, run_corpus  # noqa: E402


@pytest.mark.skipif(not corpus_files(), reason='real resume corpus directory not present')
def test_real_corpus_structural_fields(tmp_path):
    reports = run_corpus(artifact_dir=tmp_path)
    assert reports, 'corpus directory had no pdf/docx files'
    for report in reports:
        if report.get('source_unavailable'):
            # Image-only / empty extracts are reported, not fabricated.
            continue
        form = report.get('form') or {}
        if report.get('extract_has_labeled_job') or report.get('extract_has_pipe_job'):
            assert form.get('experiences'), (
                f"{report['file']}: employment evidence in extract but Form DTO experiences empty"
            )
        if report.get('extract_has_degree'):
            assert form.get('education') or form.get('experiences'), (
                f"{report['file']}: education evidence in extract but no education/experience rows"
            )
        if report.get('extract_has_email'):
            assert form.get('email') or form.get('fullName'), (
                f"{report['file']}: contact evidence in extract but identity empty"
            )
