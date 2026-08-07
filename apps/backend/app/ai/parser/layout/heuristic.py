"""Heuristic document layout: section headers + reading-order OCR boxes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.parser.enrichment.resume_text_inference import SECTION_HEADERS, is_section_header_line

_HEADER_ALIASES = {
    'work experience': 'Experience',
    'professional experience': 'Experience',
    'employment': 'Experience',
    'work history': 'Experience',
    'technical skills': 'Skills',
    'core skills': 'Skills',
    'key skills': 'Skills',
    'skills and abilities': 'Skills',
    'skills & abilities': 'Skills',
    'academic background': 'Education',
    'academic details': 'Education',
    'academics': 'Education',
    'educational qualifications': 'Education',
    'educational qualification': 'Education',
    'educational background': 'Education',
    'qualifications': 'Education',
    'certificates': 'Certifications',
    'certifications and licenses': 'Certifications',
    'certifications & licenses': 'Certifications',
    'professional summary': 'Summary',
    'objective': 'Summary',
    'profile': 'Summary',
    'about me': 'Summary',
}


@dataclass
class LayoutRegion:
    label: str  # title | plain_text | list | table | section:<Name> | unknown
    bbox: tuple[float, float, float, float]  # x0,y0,x1,y1
    text: str = ''
    score: float = 0.0


def normalize_section_header(line: str) -> str | None:
    """Return canonical section title if line is a resume section header."""
    stripped = (line or '').strip().strip(':').strip('*').strip()
    if not stripped or len(stripped) > 60:
        return None
    low = stripped.lower()
    if low in _HEADER_ALIASES:
        return _HEADER_ALIASES[low]
    if low in SECTION_HEADERS:
        return stripped.title() if low not in ('cv', 'resume') else None
    if is_section_header_line(stripped):
        return _HEADER_ALIASES.get(low, stripped.title())
    return None


def structure_text_by_headers(text: str) -> str:
    """
    Re-emit resume text with clear section headers on their own lines.
    Improves rules extraction without a vision model.
    """
    if not (text or '').strip():
        return text or ''

    lines = [ln.rstrip() for ln in text.splitlines()]
    out: list[str] = []
    current: str | None = None
    body: list[str] = []

    def flush() -> None:
        nonlocal body, current
        if current:
            out.append(current)
            out.extend(body)
            out.append('')
        elif body:
            out.extend(body)
            out.append('')
        body = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if body and body[-1] != '':
                body.append('')
            continue
        header = normalize_section_header(stripped)
        if header:
            flush()
            current = header
            continue
        body.append(stripped)

    flush()
    return '\n'.join(out).strip()


def regions_from_ocr_detections(detections: list) -> list[LayoutRegion]:
    """
    Build layout regions from RapidOCR [box, text, score] rows using section headers.
    """
    rows: list[tuple[float, float, float, float, str, float]] = []
    for item in detections or []:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        text = str(item[1] or '').strip()
        if not text:
            continue
        box = item[0]
        try:
            xs = [float(p[0]) for p in box]
            ys = [float(p[1]) for p in box]
            x0, x1 = min(xs), max(xs)
            y0, y1 = min(ys), max(ys)
        except Exception:
            continue
        score = float(item[2]) if len(item) > 2 else 0.0
        rows.append((x0, y0, x1, y1, text, score))

    rows.sort(key=lambda r: (round(r[1] / 14.0) * 14.0, r[0]))

    regions: list[LayoutRegion] = []
    current_label = 'unknown'
    buf: list[str] = []
    bbox: list[float] | None = None

    def flush() -> None:
        nonlocal buf, bbox, current_label
        if not buf:
            return
        regions.append(
            LayoutRegion(
                label=f'section:{current_label}' if current_label != 'unknown' else 'plain_text',
                bbox=tuple(bbox) if bbox else (0.0, 0.0, 0.0, 0.0),  # type: ignore[arg-type]
                text='\n'.join(buf),
                score=0.0,
            )
        )
        buf = []
        bbox = None

    for x0, y0, x1, y1, text, score in rows:
        header = normalize_section_header(text)
        if header:
            flush()
            current_label = header
            regions.append(
                LayoutRegion(
                    label=f'section:{header}',
                    bbox=(x0, y0, x1, y1),
                    text=header,
                    score=score,
                )
            )
            continue
        buf.append(text)
        if bbox is None:
            bbox = [x0, y0, x1, y1]
        else:
            bbox[0] = min(bbox[0], x0)
            bbox[1] = min(bbox[1], y0)
            bbox[2] = max(bbox[2], x1)
            bbox[3] = max(bbox[3], y1)

    flush()
    return regions


def regions_to_section_text(regions: list[LayoutRegion]) -> str:
    """Join layout regions into section-scoped text for rules extraction."""
    parts: list[str] = []
    for reg in regions:
        label = reg.label
        text = (reg.text or '').strip()
        if not text:
            continue
        if label.startswith('section:'):
            section = label.split(':', 1)[1]
            # Avoid duplicating bare header-only regions
            if text.lower() == section.lower():
                parts.append(section)
            else:
                parts.append(section)
                parts.append(text)
        elif label == 'title':
            parts.append(text)
        else:
            parts.append(text)
    return structure_text_by_headers('\n'.join(parts))


def opencv_block_regions(image_bgr: Any) -> list[LayoutRegion]:
    """
    Coarse text-block proposals via OpenCV morphology (no YOLO weights).
    Labels remain unknown; callers OCR each crop or fall back to full-page OCR.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return []

    if image_bgr is None:
        return []
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if len(image_bgr.shape) == 3 else image_bgr
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    thr = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 15
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 8))
    merged = cv2.morphologyEx(thr, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = gray.shape[:2]
    min_area = (h * w) * 0.002
    boxes: list[LayoutRegion] = []
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        if bw * bh < min_area:
            continue
        if bh < 12 or bw < 40:
            continue
        boxes.append(
            LayoutRegion(
                label='plain_text',
                bbox=(float(x), float(y), float(x + bw), float(y + bh)),
            )
        )
    boxes.sort(key=lambda r: (round(r.bbox[1] / 20.0) * 20.0, r.bbox[0]))
    return boxes
