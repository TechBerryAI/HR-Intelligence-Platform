"""Completeness / coverage gates for document intelligence."""

from app.ai.document_intelligence.coverage.jd_coverage import (
    CoverageReport,
    detect_jd_evidence,
    recover_jd_profile_gaps,
)
from app.ai.document_intelligence.coverage.resume_coverage import (
    recover_resume_profile_gaps,
    resume_has_recoverable_gaps,
)

__all__ = [
    'CoverageReport',
    'detect_jd_evidence',
    'recover_jd_profile_gaps',
    'recover_resume_profile_gaps',
    'resume_has_recoverable_gaps',
]
