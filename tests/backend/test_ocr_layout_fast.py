"""Layout OCR should not re-OCR blank pages block-by-block."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.parser.layout import detector as det


def test_empty_rapidocr_skips_opencv_block_ocr():
    calls = []

    def ocr_fn(blob):
        calls.append(blob)
        return 'should-not-run'

    with patch.object(det, 'preprocess_image_bytes', return_value=b'img'), \
         patch.object(det, 'is_layout_enabled', return_value=True), \
         patch.object(det, 'is_jd_layout_enabled', return_value=True), \
         patch.object(det, '_rapidocr_detections', return_value=[]), \
         patch.object(det, '_opencv_then_ocr') as opencv:
        text, source = det.ocr_image_with_layout(b'img', ocr_fn=ocr_fn)

    assert text == ''
    assert source == 'empty'
    opencv.assert_not_called()
    assert calls == []


def test_empty_rapidocr_with_ink_runs_opencv_once():
    import io
    from PIL import Image, ImageDraw

    img = Image.new('RGB', (200, 200), (255, 255, 255))
    ImageDraw.Draw(img).rectangle((20, 20, 180, 180), fill=(10, 10, 10))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    ink = buf.getvalue()

    calls = []

    def ocr_fn(blob):
        calls.append(blob)
        return 'should-not-run'

    with patch.object(det, 'preprocess_image_bytes', return_value=ink), \
         patch.object(det, 'is_layout_enabled', return_value=True), \
         patch.object(det, 'is_jd_layout_enabled', return_value=True), \
         patch.object(det, '_rapidocr_detections', return_value=[]), \
         patch.object(det, '_opencv_then_ocr', return_value='faint line') as opencv:
        text, source = det.ocr_image_with_layout(ink, ocr_fn=ocr_fn)

    opencv.assert_called_once()
    assert 'faint line' in text
    assert source == 'opencv_blocks'
    assert calls == []


def test_engine_failure_still_tries_block_ocr():
    def ocr_fn(_blob):
        return 'from-plain'

    with patch.object(det, 'preprocess_image_bytes', return_value=b'img'), \
         patch.object(det, 'is_layout_enabled', return_value=True), \
         patch.object(det, 'is_jd_layout_enabled', return_value=True), \
         patch.object(det, '_rapidocr_detections', return_value=None), \
         patch.object(det, '_opencv_then_ocr', return_value=''):
        text, source = det.ocr_image_with_layout(b'img', ocr_fn=ocr_fn)

    assert text == 'from-plain'
    assert source == 'plain_ocr'
