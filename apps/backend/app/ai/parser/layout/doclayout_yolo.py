"""
Optional DocLayout-YOLO wrapper for document region detection.

Enabled when RESUME_LAYOUT_ENABLED=true and doclayout-yolo (or ultralytics YOLO
with DocLayout weights) is installed. Soft-fails to None so heuristic layout runs.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

from app.ai.parser.layout.heuristic import LayoutRegion

logger = logging.getLogger(__name__)

# DocStructBench-style class ids used by DocLayout-YOLO
_CLASS_LABELS = {
    0: 'title',
    1: 'plain_text',
    2: 'abandon',
    3: 'figure',
    4: 'figure_caption',
    5: 'table',
    6: 'table_caption',
    7: 'table_footnote',
    8: 'isolate_formula',
    9: 'formula_caption',
}

DOCLAYOUT_WEIGHTS = os.getenv(
    'DOCLAYOUT_WEIGHTS',
    'doclayout_yolo_docstructbench_imgsz1024.pt',
)
DOCLAYOUT_CONF = float(os.getenv('DOCLAYOUT_CONF', '0.25'))


@lru_cache(maxsize=1)
def _load_model() -> Any | None:
    """Lazy-load DocLayout-YOLO once per process."""
    try:
        from doclayout_yolo import YOLOv10  # type: ignore
    except ImportError:
        try:
            from ultralytics import YOLO as YOLOv10  # type: ignore
        except ImportError:
            logger.info(
                'DocLayout-YOLO not installed; using heuristic layout only. '
                'Optional: pip install doclayout-yolo'
            )
            return None

    weights = DOCLAYOUT_WEIGHTS
    try:
        model = YOLOv10(weights)
        logger.info('Loaded DocLayout model from %s', weights)
        return model
    except Exception as exc:
        logger.warning('Failed to load DocLayout weights %s: %s', weights, exc)
        return None


def detect_doclayout_regions(image_bgr: Any) -> list[LayoutRegion] | None:
    """
    Run DocLayout-YOLO on a BGR image.

    Returns None if the model is unavailable (caller should use heuristics).
    """
    model = _load_model()
    if model is None or image_bgr is None:
        return None

    try:
        results = model.predict(image_bgr, conf=DOCLAYOUT_CONF, verbose=False)
    except Exception as exc:
        logger.warning('DocLayout predict failed: %s', exc)
        return None

    if not results:
        return []

    regions: list[LayoutRegion] = []
    result = results[0]
    boxes = getattr(result, 'boxes', None)
    if boxes is None:
        return []

    try:
        xyxy = boxes.xyxy.cpu().numpy()
        cls = boxes.cls.cpu().numpy()
        conf = boxes.conf.cpu().numpy()
    except Exception:
        return []

    for i in range(len(xyxy)):
        x0, y0, x1, y1 = (float(v) for v in xyxy[i])
        class_id = int(cls[i])
        label = _CLASS_LABELS.get(class_id, 'plain_text')
        if label in ('abandon', 'figure', 'isolate_formula', 'formula_caption'):
            continue
        regions.append(
            LayoutRegion(
                label=label,
                bbox=(x0, y0, x1, y1),
                score=float(conf[i]),
            )
        )

    regions.sort(key=lambda r: (round(r.bbox[1] / 16.0) * 16.0, r.bbox[0]))
    return regions
