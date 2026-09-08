"""Unit tests for centralized extract-text quality classification."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.parser.extraction_result import TextQuality
from app.ai.parser.text_quality import (
    classify_text_quality,
    looks_like_garbage_extract,
    prefer_better_text,
)


def test_empty_text_is_empty():
    assert classify_text_quality('') is TextQuality.EMPTY
    assert classify_text_quality('   \n') is TextQuality.EMPTY


def test_short_resume_with_email_is_good():
    text = 'Alex Example\nalex@example.com\n+1 555 0100\nSkills: Python'
    assert classify_text_quality(text) is TextQuality.GOOD


def test_garbage_symbols_classified_garbage():
    junk = ':::: **** #### ' * 16
    assert looks_like_garbage_extract(junk) is True
    assert classify_text_quality(junk) is TextQuality.GARBAGE


def test_cid_encoding_garbage():
    junk = '(cid:12) (cid:34) (cid:56) (cid:78) more cid:99 cid:01'
    assert classify_text_quality(junk) is TextQuality.GARBAGE


def test_weak_short_text_without_tokens():
    assert classify_text_quality('hello world again') is TextQuality.WEAK


def test_good_long_digital_body():
    body = 'Experience at Example Corp developing Python services. ' * 8
    assert classify_text_quality(body) is TextQuality.GOOD


def test_sparse_image_page_is_weak():
    text = 'a few words on a scanned page here'
    assert classify_text_quality(text, image_count=2) is TextQuality.WEAK


def test_prefer_ocr_over_empty_digital():
    text, quality, source = prefer_better_text(
        '',
        TextQuality.EMPTY,
        'Scanned resume Experience education skills ' + ('y' * 20),
        TextQuality.GOOD,
    )
    assert source == 'ocr'
    assert quality is TextQuality.GOOD
    assert 'Scanned' in text


def test_prefer_good_digital_over_weak_ocr():
    digital = 'Alex Example alex@example.com Experience Python SQL education'
    text, quality, source = prefer_better_text(
        digital,
        TextQuality.GOOD,
        '????',
        TextQuality.GARBAGE,
    )
    assert source == 'digital'
    assert quality is TextQuality.GOOD
    assert text == digital.strip()


def test_overlay_with_high_image_coverage_is_weak():
    overlay = 'Experience\nCurriculum Vitae'
    assert classify_text_quality(overlay) is TextQuality.GOOD
    assert classify_text_quality(overlay, image_coverage=0.9) is TextQuality.WEAK


def test_long_digital_stays_good_even_with_image_coverage():
    body = 'Experience at Example Corp developing Python services. ' * 8
    assert len(body.strip()) > 400
    assert classify_text_quality(body, image_coverage=0.9) is TextQuality.GOOD
