"""Observable evidence scoring for association decisions.

Confidence is derived from signals in the document, not an LLM percentage.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.ai.document_intelligence.association.taxonomy import (
    EVIDENCE_MISSING,
    EVIDENCE_NEAR_OK,
    EVIDENCE_OK,
    EVIDENCE_REVIEW,
)

# Signal weights — section/record evidence outranks weak proximity.
SIGNAL_WEIGHTS = {
    'explicit_label': 0.28,
    'section_boundary': 0.18,
    'record_boundary': 0.18,
    'same_block': 0.16,
    'entity_pattern': 0.12,
    'date_proximity': 0.10,
    'neighbor_consistency': 0.08,
    'heading_hierarchy': 0.08,
    'layout_proximity': 0.06,
}


@dataclass
class Evidence:
    signals: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def add(self, signal: str, note: str = '') -> None:
        if signal and signal not in self.signals:
            self.signals.append(signal)
        if note:
            self.notes.append(note)

    @property
    def score(self) -> float:
        total = sum(SIGNAL_WEIGHTS.get(s, 0.04) for s in self.signals)
        return round(min(1.0, total), 3)

    @property
    def level(self) -> str:
        s = self.score
        if s >= 0.72:
            return EVIDENCE_OK
        if s >= 0.42:
            return EVIDENCE_NEAR_OK
        if s > 0.0:
            return EVIDENCE_REVIEW
        return EVIDENCE_MISSING

    def as_dict(self) -> dict:
        return {
            'signals': list(self.signals),
            'score': self.score,
            'level': self.level,
            'notes': list(self.notes)[:8],
        }


def overlap_ratio(left: str, right: str) -> float:
    """Token overlap in [0, 1]. Empty values score 0."""
    a = {t for t in _tokens(left) if len(t) > 1}
    b = {t for t in _tokens(right) if len(t) > 1}
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def contains_normalized(haystack: str, needle: str) -> bool:
    n = _norm(needle)
    h = _norm(haystack)
    return bool(n) and n in h


def _norm(value: str) -> str:
    return ' '.join((value or '').lower().split())


def _tokens(value: str) -> list[str]:
    return [t for t in _norm(value).replace('/', ' ').replace('|', ' ').split() if t]
