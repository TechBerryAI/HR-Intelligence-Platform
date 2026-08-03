"""Shared types for the Intelligence Engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


StageCallback = Callable[['StageEvent'], None]


@dataclass
class SectionSpan:
    """Typed document section between layout/text and field parsers."""

    label: str
    start: int
    end: int
    text: str
    source: str = 'heuristic'  # heuristic | layout | ocr


@dataclass
class StageEvent:
    """Observable pipeline stage for progress UX."""

    stage: str
    status: str  # started | completed | skipped | failed
    message: str = ''
    detail: dict[str, Any] = field(default_factory=dict)
    job_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'stage': self.stage,
            'status': self.status,
            'message': self.message,
            'detail': self.detail,
            'job_id': self.job_id,
        }


# Regex-friendly fields: deterministic always wins over LLM when both present
RESUME_DETERMINISTIC_PERSON_KEYS = (
    'email',
    'phone',
    'linkedin',
    'github',
    'portfolio',
    'website',
    'twitter',
)

JD_DETERMINISTIC_KEYS = (
    'title',
    'company',
    'location',
    'salary_range',
    'employment_type',
    'min_experience_years',
    'max_experience_years',
)
