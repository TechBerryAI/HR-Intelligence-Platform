"""Failure taxonomy for resume field association.

These labels are for debugging and golden tests. They are not a public API
status and must not replace existing coverage values
(filled / recovered / missing_with_evidence / missing_no_evidence).
"""
from __future__ import annotations

EXTRACTION_MISSING = 'EXTRACTION_MISSING'
EXTRACTION_INCORRECT = 'EXTRACTION_INCORRECT'
ENTITY_MISASSOCIATION = 'ENTITY_MISASSOCIATION'
SECTION_MISCLASSIFICATION = 'SECTION_MISCLASSIFICATION'
RECORD_BOUNDARY_ERROR = 'RECORD_BOUNDARY_ERROR'
FIELD_CONTAMINATION = 'FIELD_CONTAMINATION'
CROSS_RECORD_LEAK = 'CROSS_RECORD_LEAK'
UNSUPPORTED_INFERENCE = 'UNSUPPORTED_INFERENCE'
NORMALIZATION_ERROR = 'NORMALIZATION_ERROR'
OCR_ORDER_ERROR = 'OCR_ORDER_ERROR'

TAXONOMY = (
    EXTRACTION_MISSING,
    EXTRACTION_INCORRECT,
    ENTITY_MISASSOCIATION,
    SECTION_MISCLASSIFICATION,
    RECORD_BOUNDARY_ERROR,
    FIELD_CONTAMINATION,
    CROSS_RECORD_LEAK,
    UNSUPPORTED_INFERENCE,
    NORMALIZATION_ERROR,
    OCR_ORDER_ERROR,
)

# Field-level verdicts used by golden tests (measurable association errors).
CORRECT = 'correct'
MISSING = 'missing'
PARTIAL = 'partial'
INCORRECT = 'incorrect'
MISASSOCIATED = 'misassociated'
NOT_STATED = 'not_stated'
REVIEW = 'review'

# Internal evidence levels — map onto existing coverage where possible.
EVIDENCE_OK = 'OK'
EVIDENCE_NEAR_OK = 'NEAR_OK'
EVIDENCE_REVIEW = 'REVIEW'
EVIDENCE_MISSING = 'MISSING'
