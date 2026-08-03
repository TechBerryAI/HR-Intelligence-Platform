"""Deterministic contact field extraction."""
from app.ai.document_intelligence.deterministic import (
    extract_email,
    extract_github,
    extract_linkedin,
    extract_phone,
    extract_portfolio,
    extract_simple_location,
)

__all__ = [
    'extract_email',
    'extract_github',
    'extract_linkedin',
    'extract_phone',
    'extract_portfolio',
    'extract_simple_location',
]
