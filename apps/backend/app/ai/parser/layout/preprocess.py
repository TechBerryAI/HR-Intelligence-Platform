"""OpenCV image preprocess for OCR: grayscale, denoise, deskew, binarize."""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

OCR_PREPROCESS = os.getenv('OCR_PREPROCESS', 'true').lower() in ('1', 'true', 'yes')


def preprocess_image_bytes(image_bytes: bytes) -> bytes:
    """
    Deskew / denoise / contrast-boost PNG/JPEG bytes for OCR.

    Returns processed PNG bytes, or original bytes if OpenCV unavailable / disabled.
    """
    if not OCR_PREPROCESS or not image_bytes:
        return image_bytes

    try:
        import cv2
        import numpy as np
    except ImportError:
        logger.debug('opencv-python-headless not installed; skipping OCR preprocess')
        return image_bytes

    try:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return image_bytes

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)
        gray = _deskew(gray)
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
        )
        if float(np.mean(binary < 128)) < 0.02 or float(np.mean(binary < 128)) > 0.85:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            gray = clahe.apply(gray)
            out = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        else:
            out = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

        ok, encoded = cv2.imencode('.png', out)
        if not ok:
            return image_bytes
        return encoded.tobytes()
    except Exception as exc:
        logger.warning('OpenCV preprocess failed: %s', exc)
        return image_bytes


def _deskew(gray: Any) -> Any:
    """Estimate skew via minAreaRect on ink pixels; rotate if |angle| > 0.5°."""
    import cv2
    import numpy as np

    thr = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thr > 0))
    if coords.size < 100:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < 0.5 or abs(angle) > 15:
        return gray
    h, w = gray.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(
        gray, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
