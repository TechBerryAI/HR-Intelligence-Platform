"""Traceable field model — every populated value carries provenance."""
from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar('T')


class TraceableField(BaseModel, Generic[T]):
    """
    Every field that may populate a form must carry:
    value, confidence, source, validator, reason.
    Invalid / unproven values must not silently reach the UI.
    """

    value: Optional[T] = None
    confidence: float = 0.0
    source: str = 'unknown'
    """Origin: deterministic | knowledge | semantic_ai | derived | user"""
    validator: str = 'none'
    """Validator id that approved the value (or 'none' if empty)."""
    reason: str = ''
    """Human-readable justification; empty when value is None."""
    canonical_path: str = ''
    """Canonical model path, e.g. personal.full_name"""

    def is_populated(self) -> bool:
        if self.value is None:
            return False
        if isinstance(self.value, str) and not self.value.strip():
            return False
        if isinstance(self.value, (list, dict)) and not self.value:
            return False
        return True

    def proven(self, *, min_confidence: float = 0.5) -> bool:
        return self.is_populated() and self.confidence >= min_confidence and bool(self.validator)


def empty_field(canonical_path: str = '', *, reason: str = 'unmapped') -> TraceableField[Any]:
    return TraceableField(
        value=None,
        confidence=0.0,
        source='none',
        validator='none',
        reason=reason,
        canonical_path=canonical_path,
    )


def field(
    value: Any,
    *,
    canonical_path: str,
    source: str,
    validator: str,
    confidence: float,
    reason: str = '',
) -> TraceableField[Any]:
    if value is None or (isinstance(value, str) and not str(value).strip()):
        return empty_field(canonical_path, reason=reason or 'empty')
    return TraceableField(
        value=value,
        confidence=float(confidence),
        source=source,
        validator=validator,
        reason=reason or f'{source}:{validator}',
        canonical_path=canonical_path,
    )
