"""
Resume layout facade: DocLayout-YOLO (optional) + OpenCV/heuristic section structure.
"""
from __future__ import annotations

import io
import logging
import os
from typing import Any

from app.ai.parser.layout.heuristic import (
    LayoutRegion,
    normalize_section_header,
    opencv_block_regions,
    regions_from_ocr_detections,
    regions_to_section_text,
    structure_text_by_headers,
)
from app.ai.parser.layout.preprocess import preprocess_image_bytes

logger = logging.getLogger(__name__)

RESUME_LAYOUT_ENABLED = os.getenv('RESUME_LAYOUT_ENABLED', 'true').lower() in (
    '1',
    'true',
    'yes',
)
JD_LAYOUT_ENABLED = os.getenv('JD_LAYOUT_ENABLED', 'true').lower() in (
    '1',
    'true',
    'yes',
)


def is_layout_enabled() -> bool:
    """
    Live layout gate for resumes. Operator RESUME_LAYOUT_ENABLED wins when set;
    otherwise HCIP_ENABLE_DOCLAYOUT (set by hardware profile) applies.
    """
    if 'RESUME_LAYOUT_ENABLED' in os.environ:
        return os.getenv('RESUME_LAYOUT_ENABLED', 'true').lower() in ('1', 'true', 'yes')
    return os.getenv('HCIP_ENABLE_DOCLAYOUT', 'true').lower() in ('1', 'true', 'yes')


def is_jd_layout_enabled() -> bool:
    """JD layout gate (default on). Falls back to HCIP_ENABLE_DOCLAYOUT when unset."""
    if 'JD_LAYOUT_ENABLED' in os.environ:
        return os.getenv('JD_LAYOUT_ENABLED', 'true').lower() in ('1', 'true', 'yes')
    return os.getenv('HCIP_ENABLE_DOCLAYOUT', 'true').lower() in ('1', 'true', 'yes')


def enhance_resume_text(raw_text: str) -> str:
    """Structure plain extracted text for rules parsing (always cheap)."""
    if not is_layout_enabled():
        return raw_text or ''
    return structure_text_by_headers(raw_text or '')


def enhance_jd_text(raw_text: str) -> str:
    """Structure JD text for section detection (headers → clear lines)."""
    if not is_jd_layout_enabled():
        return raw_text or ''
    return structure_text_by_headers(raw_text or '')


def ocr_image_with_layout(
    image_bytes: bytes,
    *,
    ocr_fn,
    for_jd: bool | None = None,
) -> tuple[str, str]:
    """
    OCR a page image with optional DocLayout / OpenCV region guidance.

    ocr_fn: callable(image_bytes) -> str  (typically RapidOCR path)

    Returns (text, source) where source is 'doclayout' | 'opencv_blocks' | 'heuristic_ocr' | 'plain_ocr'.
    """
    processed = preprocess_image_bytes(image_bytes)
    if for_jd is True:
        layout_on = is_jd_layout_enabled()
    elif for_jd is False:
        layout_on = is_layout_enabled()
    else:
        # Shared PDF/image OCR path — enable if either resume or JD layout is on
        layout_on = is_layout_enabled() or is_jd_layout_enabled()

    if not layout_on:
        return (ocr_fn(processed) or '', 'plain_ocr')

    detections = _rapidocr_detections(processed)
    if detections:
        regions = regions_from_ocr_detections(detections)
        text = regions_to_section_text(regions)
        if text.strip():
            # Try DocLayout only to refine multi-column order when available
            refined = _refine_with_doclayout(processed, detections)
            if refined and len(refined.strip()) >= len(text.strip()) * 0.6:
                return refined, 'doclayout'
            return text, 'heuristic_ocr'

    # RapidOCR found nothing. One OpenCV block pass only when the page still has ink
    # (blank pages used to cost ~12s). Engine failure (None) still falls through.
    if detections is None or (
        detections == [] and _layout_image_has_ink(image_bytes)
    ):
        blocks = _opencv_then_ocr(processed, ocr_fn)
        if blocks.strip():
            return structure_text_by_headers(blocks), 'opencv_blocks'
        if detections is None:
            return (ocr_fn(processed) or '', 'plain_ocr')

    return ('', 'empty')


def _layout_image_has_ink(image_bytes: bytes) -> bool:
    try:
        from app.ai.parser.text_extraction import _png_has_ink

        return bool(_png_has_ink(image_bytes))
    except Exception:
        return False


def _rapidocr_detections(image_bytes: bytes) -> list | None:
    """One RapidOCR pass shared with text_extraction (do not construct a second engine)."""
    try:
        import numpy as np
        from PIL import Image
        from app.ai.parser.text_extraction import _get_rapidocr_engine
    except ImportError:
        return None

    try:
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')
        arr = np.array(image)
        engine = _get_rapidocr_engine()
        result, _ = engine(arr)
        return result or []
    except Exception as exc:
        logger.debug('RapidOCR detections failed: %s', exc)
        return None


def _refine_with_doclayout(image_bytes: bytes, detections: list) -> str | None:
    try:
        import cv2
        import numpy as np
        from app.ai.parser.layout.doclayout_yolo import detect_doclayout_regions
    except ImportError:
        return None

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None

    layout_regions = detect_doclayout_regions(img)
    if not layout_regions:
        return None

    # Assign OCR text snippets to nearest layout box by IoU / center
    ocr_items: list[tuple[tuple[float, float, float, float], str]] = []
    for item in detections or []:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        text = str(item[1] or '').strip()
        if not text:
            continue
        try:
            xs = [float(p[0]) for p in item[0]]
            ys = [float(p[1]) for p in item[0]]
            ocr_items.append(((min(xs), min(ys), max(xs), max(ys)), text))
        except Exception:
            continue

    enriched: list[LayoutRegion] = []
    for reg in layout_regions:
        snippets: list[str] = []
        rx0, ry0, rx1, ry1 = reg.bbox
        rcx, rcy = (rx0 + rx1) / 2, (ry0 + ry1) / 2
        for (x0, y0, x1, y1), text in ocr_items:
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            if rx0 <= cx <= rx1 and ry0 <= cy <= ry1:
                snippets.append(text)
        blob = '\n'.join(snippets).strip()
        header = normalize_section_header(blob.split('\n', 1)[0]) if blob else None
        label = f'section:{header}' if header else reg.label
        enriched.append(
            LayoutRegion(label=label, bbox=reg.bbox, text=blob, score=reg.score)
        )

    return regions_to_section_text(enriched) or None


def _opencv_then_ocr(image_bytes: bytes, ocr_fn) -> str:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return ''

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return ''

    regions = opencv_block_regions(img)
    if not regions:
        return ''

    parts: list[str] = []
    h, w = img.shape[:2]
    for reg in regions:
        x0, y0, x1, y1 = (int(v) for v in reg.bbox)
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(w, x1), min(h, y1)
        if x1 - x0 < 20 or y1 - y0 < 12:
            continue
        crop = img[y0:y1, x0:x1]
        ok, encoded = cv2.imencode('.png', crop)
        if not ok:
            continue
        try:
            piece = (ocr_fn(encoded.tobytes()) or '').strip()
        except Exception:
            piece = ''
        if piece:
            parts.append(piece)
    return '\n\n'.join(parts)
