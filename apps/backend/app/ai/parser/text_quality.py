"""Deterministic extracted-text quality classification.

OCR fallback uses GOOD / WEAK / GARBAGE / EMPTY rather than `if text == ""`.
`looks_like_garbage_extract` is the shared garbage heuristic (also used by
pdfplumber). Do not fork a second detector.
"""
from __future__ import annotations

import re

from app.ai.parser.extraction_result import QUALITY_RANK, TextQuality

MIN_TEXT_CHARS = 30
PAGE_OCR_TEXT_THRESHOLD = 80
PAGE_SPARSE_TEXT_WITH_IMAGES = 200

_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
_PHONE_RE = re.compile(r'\b[6-9]\d{9}\b|\+\d[\d\s\-()]{8,}\d')
_RESUME_TOKEN_RE = re.compile(
    r'(?i)\b(?:experience|education|skills|summary|engineer|developer|'
    r'bachelor|master|university|college|resume|curriculum)\b'
)
_CID_RE = re.compile(r'\(cid:\d+\)', re.I)
_REPEATED_SYMBOL_RE = re.compile(r'([^\w\s])\1{7,}')


def _alnum_ratio(t: str) -> float:
    if not t:
        return 0.0
    alnum = sum(1 for c in t if c.isalnum())
    return alnum / max(len(t), 1)


def has_identity_or_resume_tokens(t: str) -> bool:
    if not t:
        return False
    return bool(_EMAIL_RE.search(t) or _PHONE_RE.search(t) or _RESUME_TOKEN_RE.search(t))


def looks_like_garbage_extract(s: str, *, min_chars: int | None = None) -> bool:
    """Narrow heuristic: enough chars but almost no signal (bad OCR / junk text layer)."""
    floor = MIN_TEXT_CHARS if min_chars is None else min_chars
    t = (s or '').strip()
    if len(t) < floor:
        return True
    if len(t) > 400:
        return False
    ratio = _alnum_ratio(t)
    has_token = has_identity_or_resume_tokens(t)
    return ratio < 0.35 and not has_token


def _is_encoding_garbage(t: str) -> bool:
    """PDF encoding junk / replacement floods / meaningless symbol runs."""
    if not t:
        return False
    if len(_CID_RE.findall(t)) >= 3 or t.lower().count('cid:') >= 3:
        return True
    repl = t.count('\ufffd')
    if repl / max(len(t), 1) >= 0.08:
        return True
    if _REPEATED_SYMBOL_RE.search(t) and _alnum_ratio(t) < 0.25:
        return True
    return False


def classify_text_quality(
    text: str,
    *,
    image_count: int = 0,
    page_threshold: int = PAGE_OCR_TEXT_THRESHOLD,
    sparse_with_images: int = PAGE_SPARSE_TEXT_WITH_IMAGES,
) -> TextQuality:
    """Classify extracted text as GOOD, WEAK, GARBAGE, or EMPTY."""
    t = (text or '').strip()
    if not t:
        return TextQuality.EMPTY

    has_token = has_identity_or_resume_tokens(t)
    ratio = _alnum_ratio(t)
    word_count = len(t.split())

    if _is_encoding_garbage(t) and not has_token:
        return TextQuality.GARBAGE

    # Mid-length junk (existing heuristic) — not EMPTY, not a short legit resume.
    if (
        MIN_TEXT_CHARS <= len(t) <= 400
        and looks_like_garbage_extract(t)
        and not has_token
    ):
        return TextQuality.GARBAGE

    # Short but clearly a resume/contact page — do not OCR unnecessarily.
    if has_token and ratio >= 0.35:
        return TextQuality.GOOD

    if len(t) < page_threshold and not has_token:
        return TextQuality.WEAK

    if image_count > 0 and len(t) < sparse_with_images and not has_token:
        return TextQuality.WEAK
    if image_count >= 3 and len(t) < 400 and not has_token:
        return TextQuality.WEAK

    if ratio >= 0.35 or word_count >= 8:
        return TextQuality.GOOD

    return TextQuality.WEAK


def quality_needs_ocr(quality: TextQuality) -> bool:
    return quality != TextQuality.GOOD


def prefer_better_text(
    digital: str,
    digital_quality: TextQuality,
    ocr: str,
    ocr_quality: TextQuality,
    *,
    ocr_confidence: float | None = None,
) -> tuple[str, TextQuality, str]:
    """Pick digital vs OCR. Rank first, then length. Returns (text, quality, source)."""
    d = (digital or '').strip()
    o = (ocr or '').strip()
    dr = QUALITY_RANK[digital_quality]
    orank = QUALITY_RANK[ocr_quality]
    if orank > dr:
        return o, ocr_quality, 'ocr'
    if dr > orank:
        return d, digital_quality, 'digital'
    if not d and o:
        return o, ocr_quality, 'ocr'
    if not o and d:
        return d, digital_quality, 'digital'
    if len(o) > len(d) * 1.1:
        return o, ocr_quality, 'ocr'
    if ocr_confidence is not None and ocr_confidence >= 0.75 and len(o) >= len(d):
        return o, ocr_quality, 'ocr'
    if d:
        return d, digital_quality, 'digital'
    return o, ocr_quality, 'ocr'
