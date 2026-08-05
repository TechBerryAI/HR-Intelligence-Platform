"""Completeness / coverage gates for document intelligence."""

from app.ai.document_intelligence.coverage.jd_coverage import (
    CoverageReport,
    detect_jd_evidence,
    recover_jd_profile_gaps,
)

__all__ = [
    'CoverageReport',
    'detect_jd_evidence',
    'recover_jd_profile_gaps',
]
