"""
Text Extraction from PDF, DOCX, and image files.

Prefers PyMuPDF for digital PDF text. pdfplumber is an automatic secondary
extractor for table-heavy / poor-quality digital PDFs (see
pdfplumber_extractor.py); the system chooses it — there is no extractor env flag.
Falls back to OCR for scanned/image PDFs and
direct image uploads. OCR uses RapidOCR (pip-only via requirements.txt);
optional system Tesseract is a secondary fallback. Optional PARSING_API is last resort.
"""
from __future__ import annotations

import contextvars
import io
import logging
import os
import re
import shutil
import sys
import threading
from dataclasses import dataclass
from typing import Any

import requests
from docx import Document

from app.ai.parser.extraction_result import (
    STATUS_FAILED,
    STATUS_OCR_FAILED,
    STATUS_OCR_RECOVERED,
    STATUS_OCR_UNAVAILABLE,
    STATUS_OCR_WEAK,
    STATUS_OK,
    QUALITY_RANK,
    ExtractionResult,
    PageExtractionResult,
    TextQuality,
)
from app.ai.parser.text_quality import (
    IMAGE_COVERAGE_OCR_THRESHOLD,
    MIN_TEXT_CHARS,
    PAGE_OCR_TEXT_THRESHOLD,
    STRONG_DIGITAL_PAGE_CHARS,
    classify_text_quality,
    looks_like_garbage_extract,
    prefer_better_text,
    quality_needs_ocr,
)
from app.core.timing import timing

logger = logging.getLogger(__name__)

PARSING_API_URL = os.getenv('PARSING_API_URL', 'http://localhost:4000')
PARSING_API_KEY = os.getenv('PARSING_API_KEY', 'your-api-key-here')
PARSING_API_FALLBACK = os.getenv('PARSING_API_FALLBACK', 'true').lower() in (
    '1',
    'true',
    'yes',
)
# Connect timeout kept short so a dead localhost:4000 fails fast in bulk.
PARSING_API_CONNECT_TIMEOUT = float(os.getenv('PARSING_API_CONNECT_TIMEOUT', '1.5'))
PARSING_API_READ_TIMEOUT = float(os.getenv('PARSING_API_READ_TIMEOUT', '30'))
PDF_MAX_PAGES = max(0, int(os.getenv('PDF_MAX_PAGES', '0')))
OCR_ENABLED = os.getenv('OCR_ENABLED', 'true').lower() in ('1', 'true', 'yes')
OCR_LANG = os.getenv('OCR_LANG', 'eng')
OCR_DPI = max(72, int(os.getenv('OCR_DPI', '250')))
# Try a lower DPI first for speed; escalate when OCR text is thin.
# HCIP_OCR_DPI_START is set by the CPU/GPU hardware profile when OCR_DPI_FAST is unset.
OCR_DPI_FAST = max(72, int(os.getenv('OCR_DPI_FAST', os.getenv('HCIP_OCR_DPI_START', '180'))))
# Bound concurrent RapidOCR/Tesseract inference (bulk workers stay parallel for digital I/O).
OCR_MAX_CONCURRENT = max(1, int(os.getenv('OCR_MAX_CONCURRENT', '1')))
# Cap rendered / OCR image long side so RapidOCR is not fed 6k–10k px rasters.
OCR_MAX_SIDE = max(720, int(os.getenv('OCR_MAX_SIDE', '2800')))
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

IMAGE_EXTENSIONS = frozenset({'png', 'jpg', 'jpeg', 'webp', 'tif', 'tiff', 'bmp'})

# Invisible / formatting chars common in Word→PDF exports (ZWSP, soft hyphen, BOM, etc.)
_INVISIBLE_CHARS_RE = __import__('re').compile(
    r'[\u200b\u200c\u200d\u2060\ufeff\u00ad\u180e]'
)

_FIELD_LABEL_RE = __import__('re').compile(
    r'(?i)^(job\s*title|title|position|designation|role|location|work\s*location|'
    r'experience|work\s*experience|exp\.?|salary|ctc|compensation|employment\s*type|'
    r'job\s*type|company|department|skills?|required\s*skills?|primary\s*skills?|'
    r'qualification|notice\s*period|reports?\s*to)\b'
)


def _ocr_dpi_fast() -> int:
    """Runtime fast DPI so CPU hardware profile (HCIP_OCR_DPI_START) actually applies."""
    return max(72, int(os.getenv('OCR_DPI_FAST', os.getenv('HCIP_OCR_DPI_START', '180'))))


def last_extract_max_dpi() -> int:
    """Deprecated. Process-global DPI is no longer recorded; always returns 0.

    Callers must pass ExtractionResult.final_dpi into should_retry_high_dpi_extract.
    """
    return 0


_pdf_extractor: contextvars.ContextVar[str] = contextvars.ContextVar('pdf_extractor', default='')
_pdf_fallback_reason: contextvars.ContextVar[str] = contextvars.ContextVar(
    'pdf_fallback_reason', default=''
)
_pymupdf_document: contextvars.ContextVar[ExtractionResult | None] = contextvars.ContextVar(
    'pymupdf_document', default=None
)


def last_pdf_extractor() -> str:
    """Extractor chosen for the current thread's latest extract_text_from_pdf()."""
    return _pdf_extractor.get()


def last_pdf_fallback_reason() -> str:
    """Why pdfplumber was considered for the current thread's latest PDF extract."""
    return _pdf_fallback_reason.get()


def _remember_pdf_choice(source: str, reason: str = '') -> None:
    _pdf_extractor.set(source)
    _pdf_fallback_reason.set(reason)


_SCAN_EXTS = frozenset({'pdf', 'png', 'jpg', 'jpeg', 'webp', 'tif', 'tiff', 'bmp'})


def should_retry_high_dpi_extract(
    filename: str,
    raw_text: str,
    *,
    extract_failed: bool = False,
    max_dpi_used: int | None = None,
) -> bool:
    """True when a full-file 300 DPI extract is still worth running."""
    ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
    if ext not in _SCAN_EXTS:
        return False
    if ext in IMAGE_EXTENSIONS:
        # Raster bytes do not change with a DPI argument.
        return False
    if not ocr_engines_available():
        return False
    dpi = 0 if max_dpi_used is None else int(max_dpi_used or 0)
    if dpi >= 300:
        return False
    text_length = len((raw_text or '').strip())
    quality = classify_text_quality(raw_text)
    if text_length >= MIN_TEXT_CHARS and quality == TextQuality.GOOD:
        return False
    # WEAK PDFs (thin OCR, overlay+scan) still benefit from a 300 DPI pass.
    if quality == TextQuality.WEAK:
        return True
    garbage = quality in (TextQuality.GARBAGE, TextQuality.EMPTY) or looks_like_garbage_extract(
        raw_text
    )
    return bool(extract_failed or not raw_text or text_length < MIN_TEXT_CHARS or garbage)


_TABULAR_HEADER_HINT = __import__('re').compile(
    r'(?i)\b(?:organization|organisation|designation|company|employer|'
    r'degree|university|college|board|from|to|year|percentage|cgpa)\b'
)
_TABULAR_DATE_HINT = __import__('re').compile(
    r'(?i)\b(?:(?:19|20)\d{2}|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|'
    r'till\s*date|present|current)\b'
)


def _row_is_tabular_record(cells: list[str]) -> bool:
    """True when a row should keep cell relationships (not Label: Value)."""
    if len(cells) >= 3:
        blob = ' '.join(cells)
        if _TABULAR_HEADER_HINT.search(blob) or _TABULAR_DATE_HINT.search(blob):
            return True
        return True
    return False


def _serialize_table_row(cells: list[str], *, force_pipes: bool = False) -> str:
    """Turn table cells into structured lines.

    Two-cell Label/Value rows stay ``Label: Value``. Employment/education
    tables keep ``cell | cell | cell`` so parsers can map columns.
    """
    cleaned = [(__import__('re').sub(r'\s+', ' ', (c or '').strip())) for c in cells]
    cleaned = [c for c in cleaned if c]
    if not cleaned:
        return ''
    if len(cleaned) == 1:
        return cleaned[0]
    if force_pipes or _row_is_tabular_record(cleaned):
        return ' | '.join(cleaned)
    label, *rest = cleaned
    value = ' | '.join(rest)
    if _FIELD_LABEL_RE.match(label) or label.endswith(':'):
        label = label.rstrip(':').strip()
        return f'{label}: {value}'
    if len(cleaned) == 2 and len(label.split()) <= 4:
        label = label.rstrip(':').strip()
        return f'{label}: {value}'
    return ' | '.join(cleaned)


def _dedupe_append(parts: list[str], block: str) -> None:
    block = (block or '').strip()
    if not block:
        return
    norm = __import__('re').sub(r'\s+', ' ', block.lower())
    for existing in parts:
        if norm and norm in __import__('re').sub(r'\s+', ' ', existing.lower()):
            return
    parts.append(block)


def _extract_pdf_page_tables(page) -> str:
    """Serialize PyMuPDF find_tables() rows as Label: Value lines."""
    try:
        finder = page.find_tables()
    except Exception:
        return ''
    tables = getattr(finder, 'tables', None) or []
    lines: list[str] = []
    for table in tables:
        try:
            rows = table.extract() or []
        except Exception:
            continue
        for row in rows:
            if not row:
                continue
            cells = [str(c or '') for c in row]
            serialized = _serialize_table_row(cells)
            if serialized:
                lines.append(serialized)
    return '\n'.join(lines).strip()


def normalize_extracted_text(text: str) -> str:
    """
    Strip PDF/Word invisible characters that break name/header matching.
    Zero-width spaces after names (e.g. 'DHRUTI JADEJA\\u200b') are common.
    NUL bytes from some PDF extractors must be removed here — the HTTP path
    already stripped them before persist, so in-process parse must see the
    same working text or experience rows diverge (Class D).
    """
    if not text:
        return ''
    t = _INVISIBLE_CHARS_RE.sub('', text)
    t = t.replace('\x00', '')
    t = t.replace('\xa0', ' ').replace('\u202f', ' ')
    return t


_rapidocr_engine: Any = None
_rapidocr_lock = threading.Lock()
# Lazily sized so the hardware profile (apply_hardware_env) can set
# OCR_MAX_CONCURRENT after this module is imported but before first OCR.
_ocr_inference_sema: threading.Semaphore | None = None
_ocr_sema_lock = threading.Lock()


def _get_ocr_inference_sema() -> threading.Semaphore:
    """Shared OCR inference semaphore, sized from env on first use."""
    global _ocr_inference_sema
    if _ocr_inference_sema is None:
        with _ocr_sema_lock:
            if _ocr_inference_sema is None:
                limit = max(1, int(os.getenv('OCR_MAX_CONCURRENT', str(OCR_MAX_CONCURRENT))))
                _ocr_inference_sema = threading.Semaphore(limit)
    return _ocr_inference_sema
# Cached probe: (available, engine_name_or_reason)
_ocr_engine_status: tuple[bool, str] | None = None


@dataclass
class OcrAttempt:
    text: str = ''
    engine: str = ''
    confidence: float | None = None


_last_ocr_attempt: contextvars.ContextVar[OcrAttempt | None] = contextvars.ContextVar(
    'last_ocr_attempt', default=None
)


def _tesseract_available() -> bool:
    return bool(shutil.which('tesseract'))


def reset_ocr_engine_status_cache() -> None:
    """Test helper — clear the OCR availability probe cache."""
    global _ocr_engine_status
    _ocr_engine_status = None


def get_ocr_engine_status() -> tuple[bool, str]:
    """
    Return (available, detail). Probes once per process.

    available=True when RapidOCR import works or system Tesseract + pytesseract exist.
    """
    global _ocr_engine_status
    if _ocr_engine_status is not None:
        return _ocr_engine_status
    if not OCR_ENABLED:
        _ocr_engine_status = (False, 'OCR_ENABLED=false')
        return _ocr_engine_status
    try:
        import rapidocr_onnxruntime  # noqa: F401  # type: ignore

        _ocr_engine_status = (True, 'rapidocr')
        return _ocr_engine_status
    except ImportError:
        pass
    except Exception as exc:
        logger.debug('RapidOCR probe failed: %s', exc)
    if _tesseract_available():
        try:
            import pytesseract  # noqa: F401

            _ocr_engine_status = (True, 'tesseract')
            return _ocr_engine_status
        except ImportError:
            _ocr_engine_status = (
                False,
                'tesseract binary found but pytesseract is not installed',
            )
            return _ocr_engine_status
    _ocr_engine_status = (
        False,
        'RapidOCR not installed and Tesseract unavailable '
        '(pip install rapidocr-onnxruntime, or install system Tesseract)',
    )
    return _ocr_engine_status


def ocr_engines_available() -> bool:
    """True when at least one local OCR engine can run."""
    ok, _ = get_ocr_engine_status()
    return ok


def ocr_unavailable_reason() -> str:
    _, detail = get_ocr_engine_status()
    return detail


def ocr_health_status() -> str:
    """ok | degraded | unavailable — for /health?deps=1 (does not fail /ready)."""
    if not OCR_ENABLED:
        return 'unavailable'
    ok, detail = get_ocr_engine_status()
    if not ok:
        return 'unavailable'
    if detail == 'rapidocr':
        return 'ok'
    return 'degraded'


def log_ocr_readiness() -> None:
    """Log OCR engine availability at process startup. Never logs document text."""
    ok, detail = get_ocr_engine_status()
    health = ocr_health_status()
    py = f'{sys.version_info.major}.{sys.version_info.minor}'
    extra = ''
    if sys.version_info >= (3, 13) and detail != 'rapidocr':
        extra = (
            ' Python 3.13+ has no RapidOCR wheels; use Python 3.11/3.12 for pip RapidOCR '
            'or install system Tesseract.'
        )
    msg = (
        f'[OCR] status={health} engine={detail} python={py} '
        f'enabled={str(OCR_ENABLED).lower()}.{extra}'
    )
    if health == 'ok':
        logger.info(msg)
    else:
        logger.warning(msg)
    print(msg)


def _ocr_intra_op_threads() -> int:
    """
    ONNX intra-op threads per OCR inference.

    Splits CPU cores across OCR_MAX_CONCURRENT slots so concurrent OCR does not
    oversubscribe the machine (N slots x all-cores threads).
    """
    raw = (os.getenv('OCR_INTRA_OP_THREADS') or '').strip()
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    cpus = os.cpu_count() or 1
    slots = max(1, int(os.getenv('OCR_MAX_CONCURRENT', str(OCR_MAX_CONCURRENT))))
    return max(1, cpus // slots)


def _get_rapidocr_engine() -> Any:
    """Lazy-load RapidOCR once (shared by extract + layout detections)."""
    global _rapidocr_engine
    if _rapidocr_engine is not None:
        return _rapidocr_engine
    from rapidocr_onnxruntime import RapidOCR  # type: ignore

    with _rapidocr_lock:
        if _rapidocr_engine is None:
            threads = _ocr_intra_op_threads()
            for kwargs in (
                {
                    'use_angle_cls': True,
                    'intra_op_num_threads': threads,
                    'inter_op_num_threads': 1,
                },
                {'use_angle_cls': True},
                {},
            ):
                try:
                    _rapidocr_engine = RapidOCR(**kwargs)
                    break
                except (TypeError, ValueError, KeyError):
                    continue
            if _rapidocr_engine is None:
                _rapidocr_engine = RapidOCR()
        return _rapidocr_engine


def run_rapidocr_inference(arr: Any) -> Any:
    """Run RapidOCR on a numpy image under the shared inference semaphore."""
    engine = _get_rapidocr_engine()
    with _get_ocr_inference_sema():
        result, _ = engine(arr)
    return result


def _ocr_max_side() -> int:
    return max(720, int(os.getenv('OCR_MAX_SIDE', str(OCR_MAX_SIDE))))


def _maybe_downscale_image_bytes(image_bytes: bytes) -> bytes:
    """Downscale so the long side is at most OCR_MAX_SIDE (RapidOCR empty on huge rasters)."""
    if not image_bytes:
        return image_bytes
    try:
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes))
        width, height = image.size
        long_side = max(width, height)
        cap = _ocr_max_side()
        if long_side <= cap or long_side <= 0:
            return image_bytes
        scale = cap / float(long_side)
        new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')
        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            resample = Image.LANCZOS
        resized = image.resize(new_size, resample)
        buf = io.BytesIO()
        resized.save(buf, format='PNG')
        return buf.getvalue()
    except Exception:
        return image_bytes


def _rotate_image_bytes(image_bytes: bytes, degrees: int) -> bytes:
    from PIL import Image

    image = Image.open(io.BytesIO(image_bytes))
    if image.mode not in ('RGB', 'L'):
        image = image.convert('RGB')
    rotated = image.rotate(
        degrees,
        expand=True,
        fillcolor=(255, 255, 255) if image.mode != 'L' else 255,
    )
    buf = io.BytesIO()
    rotated.save(buf, format='PNG')
    return buf.getvalue()


def _ocr_text_is_weak(text: str) -> bool:
    stripped = (text or '').strip()
    if len(stripped) < MIN_TEXT_CHARS:
        return True
    quality = classify_text_quality(stripped)
    return quality in (TextQuality.EMPTY, TextQuality.GARBAGE, TextQuality.WEAK)


def _mean_ocr_confidence(detections: list | None) -> float | None:
    scores: list[float] = []
    for item in detections or []:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        try:
            scores.append(float(item[2]))
        except (TypeError, ValueError):
            continue
    if not scores:
        return None
    return sum(scores) / len(scores)


def _ocr_with_rapidocr(image_bytes: bytes, *, preprocess: bool = True) -> tuple[str, float | None]:
    """OCR via RapidOCR (pip-installable, no system binary)."""
    import numpy as np
    from PIL import Image

    from app.ai.parser.layout.preprocess import preprocess_image_bytes

    processed = preprocess_image_bytes(image_bytes) if preprocess else image_bytes
    processed = _maybe_downscale_image_bytes(processed)
    image = Image.open(io.BytesIO(processed))
    if image.mode not in ('RGB', 'L'):
        image = image.convert('RGB')
    arr = np.array(image)
    result = run_rapidocr_inference(arr)
    if not result:
        return '', None
    return _join_ocr_detections_reading_order(result), _mean_ocr_confidence(result)


def _box_sort_key(box: Any) -> tuple[float, float]:
    """Sort key from RapidOCR box: top-to-bottom, then left-to-right."""
    try:
        # box is usually [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
        ys = [float(p[1]) for p in box]
        xs = [float(p[0]) for p in box]
        y = min(ys)
        x = min(xs)
        # Bucket Y so nearby same-line detections stay left-to-right
        return (round(y / 12.0) * 12.0, x)
    except Exception:
        return (0.0, 0.0)


def _join_ocr_detections_reading_order(detections: list) -> str:
    """Join RapidOCR [box, text, score] items in reading order."""
    rows: list[tuple[tuple[float, float], str]] = []
    for item in detections or []:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        text = item[1]
        if not text or not str(text).strip():
            continue
        box = item[0] if len(item) >= 1 else None
        rows.append((_box_sort_key(box), str(text).strip()))
    rows.sort(key=lambda r: r[0])
    return '\n'.join(text for _, text in rows).strip()


def _ocr_with_tesseract(
    image_bytes: bytes, *, lang: str | None = None, preprocess: bool = True
) -> str:
    """OCR via system Tesseract + pytesseract (optional fallback)."""
    import pytesseract
    from PIL import Image

    from app.ai.parser.layout.preprocess import preprocess_image_bytes

    processed = preprocess_image_bytes(image_bytes) if preprocess else image_bytes
    processed = _maybe_downscale_image_bytes(processed)
    image = Image.open(io.BytesIO(processed))
    if image.mode not in ('RGB', 'L'):
        image = image.convert('RGB')
    with _get_ocr_inference_sema():
        text = pytesseract.image_to_string(image, lang=lang or OCR_LANG)
    return (text or '').strip()


def _ocr_attempt_plain(image_bytes: bytes, *, lang: str | None = None) -> OcrAttempt:
    """Run RapidOCR then Tesseract without layout structuring."""
    errors: list[str] = []

    try:
        text, conf = _ocr_with_rapidocr(image_bytes)
        if text:
            return OcrAttempt(text=text, engine='rapidocr', confidence=conf)
        errors.append('RapidOCR returned empty text')
    except ImportError as exc:
        errors.append(
            f'RapidOCR not installed ({exc}). Run: pip install -r requirements.txt'
        )
    except Exception as exc:
        errors.append(f'RapidOCR failed: {exc}')
        logger.warning('RapidOCR failed, trying Tesseract if available: %s', exc)

    if _tesseract_available():
        try:
            text = _ocr_with_tesseract(image_bytes, lang=lang)
            if text:
                return OcrAttempt(text=text, engine='tesseract', confidence=None)
            errors.append('Tesseract returned empty text')
        except Exception as exc:
            errors.append(f'Tesseract failed: {exc}')

    detail = '; '.join(errors) if errors else 'no OCR engine available'
    raise ValueError(
        f'OCR failed ({detail}). Install RapidOCR with Python 3.10–3.12 '
        f'(pip install rapidocr-onnxruntime), or install system Tesseract as a fallback.'
    )


def _ocr_image_bytes_plain(image_bytes: bytes, *, lang: str | None = None) -> str:
    """Run RapidOCR then Tesseract without layout structuring."""
    return _ocr_attempt_plain(image_bytes, lang=lang).text


def _ocr_with_recovery(
    image_bytes: bytes,
    *,
    lang: str | None = None,
    skip_preprocessed: bool = False,
) -> OcrAttempt:
    """RapidOCR+preprocess → RapidOCR raw → Tesseract → 90/180/270 rotations."""
    errors: list[str] = []
    best = OcrAttempt()

    def consider(attempt: OcrAttempt) -> bool:
        nonlocal best
        text = (attempt.text or '').strip()
        if not text:
            return False
        attempt.text = text
        _, _, src = prefer_better_text(
            best.text,
            classify_text_quality(best.text),
            attempt.text,
            classify_text_quality(attempt.text),
            ocr_confidence=attempt.confidence,
        )
        if src == 'ocr' or not (best.text or '').strip():
            best = attempt
        elif len(text) > len(best.text or ''):
            best = attempt
        quality = classify_text_quality(best.text)
        return quality == TextQuality.GOOD and len(best.text) >= MIN_TEXT_CHARS

    if not skip_preprocessed:
        try:
            text, conf = _ocr_with_rapidocr(image_bytes, preprocess=True)
            if consider(OcrAttempt(text=text, engine='rapidocr', confidence=conf)):
                return best
        except ImportError as exc:
            errors.append(
                f'RapidOCR not installed ({exc}). Run: pip install -r requirements.txt'
            )
        except Exception as exc:
            errors.append(f'RapidOCR failed: {exc}')
            logger.warning('RapidOCR failed, trying raw / Tesseract: %s', exc)

    if _ocr_text_is_weak(best.text):
        try:
            text, conf = _ocr_with_rapidocr(image_bytes, preprocess=False)
            if consider(OcrAttempt(text=text, engine='rapidocr_raw', confidence=conf)):
                return best
        except ImportError as exc:
            errors.append(f'RapidOCR not installed ({exc})')
        except Exception as exc:
            errors.append(f'RapidOCR raw failed: {exc}')

    if _ocr_text_is_weak(best.text) and _tesseract_available():
        try:
            text = _ocr_with_tesseract(image_bytes, lang=lang, preprocess=False)
            if consider(OcrAttempt(text=text, engine='tesseract', confidence=None)):
                return best
        except Exception as exc:
            errors.append(f'Tesseract failed: {exc}')

    # Rotations only when we still lack usable text (not for every WEAK page).
    needs_rotate = len((best.text or '').strip()) < MIN_TEXT_CHARS or classify_text_quality(
        best.text
    ) in (TextQuality.EMPTY, TextQuality.GARBAGE)
    if needs_rotate:
        for degrees in (90, 180, 270):
            try:
                rotated = _rotate_image_bytes(image_bytes, degrees)
                text, conf = _ocr_with_rapidocr(rotated, preprocess=False)
                if consider(
                    OcrAttempt(text=text, engine=f'rotated_{degrees}', confidence=conf)
                ):
                    return best
                if _tesseract_available() and _ocr_text_is_weak(text):
                    ttext = _ocr_with_tesseract(rotated, lang=lang, preprocess=False)
                    if consider(
                        OcrAttempt(
                            text=ttext,
                            engine=f'tesseract_rotated_{degrees}',
                            confidence=None,
                        )
                    ):
                        return best
            except Exception as exc:
                errors.append(f'rotate_{degrees} failed: {type(exc).__name__}')
                continue

    if (best.text or '').strip():
        return best

    detail = '; '.join(errors) if errors else 'no OCR engine available'
    raise ValueError(
        f'OCR failed ({detail}). Install RapidOCR with Python 3.10–3.12 '
        f'(pip install rapidocr-onnxruntime), or install system Tesseract as a fallback.'
    )


def _min_pool_gray(arr, max_side: int = 120):
    """Min-pool grayscale so thin/light strokes survive downsampling."""
    import numpy as np

    if arr.ndim != 2 or arr.size == 0:
        return arr
    height, width = int(arr.shape[0]), int(arr.shape[1])
    long_side = max(height, width)
    if long_side <= max_side:
        return arr
    block_h = max(1, int(np.ceil(height / max_side)))
    block_w = max(1, int(np.ceil(width / max_side)))
    cropped_h = (height // block_h) * block_h
    cropped_w = (width // block_w) * block_w
    if cropped_h <= 0 or cropped_w <= 0:
        return arr
    cropped = arr[:cropped_h, :cropped_w]
    return cropped.reshape(
        cropped_h // block_h, block_h, cropped_w // block_w, block_w
    ).min(axis=(1, 3))


def _png_has_ink(image_bytes: bytes) -> bool:
    """True when a rendered page has enough visual content to be worth OCR.

    Blank / near-white pages still cost 10–15s of RapidOCR today. Detecting
    them after the cheap render (~100ms) does not skip Extract / Layout stages.

    Dense dark ink uses the legacy 0.2% threshold on a min-pooled grid.
    Sparse/light scans (thin strokes, luma often 200–240) are kept when
    paper-relative cells show line-like occupancy rather than isolated specks.
    """
    if not image_bytes or len(image_bytes) < 64:
        return False
    try:
        import numpy as np
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes))
        gray = image.convert('L')
        arr = np.asarray(gray, dtype=np.uint8)
        if arr.size == 0:
            return False
        lo, hi = int(arr.min()), int(arr.max())
        if hi - lo < 12:
            return False

        pooled = _min_pool_gray(arr, max_side=120)
        pixels = int(pooled.size)
        if pixels <= 0:
            return False

        # Fast path: clearly-dark cells (legacy 0.2% cutoff).
        dark = int((pooled < 200).sum())
        if dark > pixels * 0.002:
            return True

        paper = int(pooled.max())
        ink_cut = max(0, paper - 12)
        content = pooled <= ink_cut
        content_count = int(content.sum())
        if content_count <= 0:
            return False

        occupied_rows = int((content.sum(axis=1) >= 3).sum())
        occupied_cols = int((content.sum(axis=0) >= 3).sum())
        content_ratio = content_count / pixels
        # Sparse/light structured content: spread like text lines, not specks.
        if occupied_rows >= 4 and occupied_cols >= 6 and content_ratio >= 0.0005:
            return True
        return False
    except Exception:
        return True


def _ocr_image_bytes(image_bytes: bytes, *, lang: str | None = None) -> str:
    """
    Run OCR on raw image bytes.

    Primary: RapidOCR (+ OpenCV preprocess, optional layout).
    Secondary: system Tesseract if available.
    Fail-fast when no OCR engine is installed (avoids per-page layout retries).
    """
    if not OCR_ENABLED:
        raise ValueError('OCR is disabled (OCR_ENABLED=false)')

    if not ocr_engines_available():
        raise ValueError(
            f'OCR engines unavailable: {ocr_unavailable_reason()}. '
            'Install RapidOCR with Python 3.10–3.12 '
            '(pip install rapidocr-onnxruntime), or install system Tesseract.'
        )

    if RESUME_LAYOUT_ENABLED:
        try:
            from app.ai.parser.layout.detector import ocr_image_with_layout

            text, source = ocr_image_with_layout(
                image_bytes,
                ocr_fn=lambda b: _ocr_image_bytes_plain(b, lang=lang),
            )
            if text and text.strip():
                logger.debug('Layout OCR source=%s chars=%s', source, len(text))
                _last_ocr_attempt.set(
                    OcrAttempt(text=text.strip(), engine=source or 'rapidocr')
                )
                return text.strip()
            # Blank page: layout already ran RapidOCR. Do not spend 12s again.
            if source == 'empty':
                raise ValueError(
                    'OCR failed (RapidOCR returned empty text). Install RapidOCR with '
                    'Python 3.10–3.12 (pip install rapidocr-onnxruntime), or install '
                    'system Tesseract as a fallback.'
                )
            # source == needs_recovery (ink but RapidOCR []): recovery ladder.
        except ValueError:
            raise
        except Exception as exc:
            logger.warning('Layout OCR failed, falling back to recovery OCR: %s', exc)

    attempt = _ocr_with_recovery(
        image_bytes,
        lang=lang,
        skip_preprocessed=RESUME_LAYOUT_ENABLED,
    )
    _last_ocr_attempt.set(attempt)
    return attempt.text


def extract_text_from_image(file_data: bytes, filename: str = 'image.png') -> str:
    """Extract text from a standalone image via OCR."""
    text = _ocr_image_bytes(file_data)
    if len(text) < MIN_TEXT_CHARS:
        raise ValueError(
            f'OCR extracted only {len(text)} characters from image {filename}. '
            'The image may be blank, too low-resolution, or unreadable.'
        )
    logger.info('OCR extracted %s characters from image %s', len(text), filename)
    return text


def _render_page_png(page, dpi: int = OCR_DPI) -> bytes:
    """Render a PyMuPDF page to PNG bytes, capped to OCR_MAX_SIDE, RGB."""
    import fitz

    rect = page.rect
    long_side_pts = max(float(rect.width or 0), float(rect.height or 0)) or 1.0
    zoom = dpi / 72.0
    max_zoom = _ocr_max_side() / long_side_pts
    if max_zoom > 0:
        zoom = min(zoom, max_zoom)
    matrix = fitz.Matrix(zoom, zoom)
    kwargs: dict[str, Any] = {'matrix': matrix, 'alpha': False}
    cs_rgb = getattr(fitz, 'csRGB', None)
    if cs_rgb is not None:
        kwargs['colorspace'] = cs_rgb
    pix = page.get_pixmap(**kwargs)
    return pix.tobytes('png')


def _page_image_count(page) -> int:
    try:
        return len(page.get_images(full=True) or [])
    except Exception:
        return 0


def _page_image_coverage(page) -> float:
    """Fraction of the page covered by embedded images (0..1)."""
    try:
        rect = page.rect
        page_area = abs(float(rect.width) * float(rect.height)) or 1.0
        infos: list = []
        getter = getattr(page, 'get_image_info', None)
        if callable(getter):
            try:
                raw = getter()
                infos = list(raw) if isinstance(raw, (list, tuple)) else []
            except Exception:
                infos = []
        covered = 0.0
        parsed = 0
        for info in infos:
            bbox = None
            if isinstance(info, dict):
                bbox = info.get('bbox')
                if bbox is None and all(k in info for k in ('x0', 'y0', 'x1', 'y1')):
                    bbox = (info['x0'], info['y0'], info['x1'], info['y1'])
            else:
                bbox = getattr(info, 'bbox', None)
            if bbox is None or len(bbox) < 4:
                continue
            try:
                x0, y0, x1, y1 = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
            except (TypeError, ValueError):
                continue
            covered += abs((x1 - x0) * (y1 - y0))
            parsed += 1
        if parsed:
            return min(1.0, covered / page_area)
        # Infos existed but no bboxes — treat as a full-page scan.
        if infos:
            return 1.0
        count = _page_image_count(page)
        return 1.0 if count >= 1 else 0.0
    except Exception:
        count = _page_image_count(page)
        return 1.0 if count >= 1 else 0.0


def _combine_page_text(digital: str, table_text: str) -> str:
    bits: list[str] = []
    if digital:
        bits.append(digital)
    if table_text:
        _dedupe_append(bits, table_text)
    return '\n\n'.join(bits).strip()


def _needs_page_ocr(quality: TextQuality, text: str, image_coverage: float) -> bool:
    """
    True when a PDF page should be OCRed.

    Not-GOOD digital text always OCRs. High image coverage forces OCR too,
    unless the digital layer is GOOD *and* long enough to be trusted (styled
    resumes with photos/backgrounds — OCR there is pure waste).
    """
    if quality_needs_ocr(quality):
        return True
    if image_coverage < IMAGE_COVERAGE_OCR_THRESHOLD:
        return False
    return len((text or '').strip()) < STRONG_DIGITAL_PAGE_CHARS


def _page_needs_ocr(page, digital_text: str) -> bool:
    """True when digital text is not GOOD, or the page is image-heavy."""
    image_count = _page_image_count(page)
    coverage = _page_image_coverage(page)
    quality = classify_text_quality(
        digital_text, image_count=image_count, image_coverage=coverage
    )
    return _needs_page_ocr(quality, digital_text, coverage)


def _digital_page_result(
    page_number: int,
    text: str,
    quality: TextQuality,
    *,
    fallback: str = '',
    warnings: list[str] | None = None,
) -> PageExtractionResult:
    return PageExtractionResult(
        page_number=page_number,
        source='digital',
        text=text,
        quality=quality,
        fallback=fallback,
        warnings=list(warnings or []),
    )


def _ocr_one_pdf_page(
    page,
    *,
    page_number: int,
    digital: str,
    table_text: str,
    digital_quality: TextQuality,
    image_count: int,
    fast_dpi: int,
    full_dpi: int,
    forced_dpi: int | None,
    image_coverage: float = 0.0,
) -> PageExtractionResult:
    """Render + OCR a page, escalate DPI once if still weak, keep the better result."""
    combined_digital = _combine_page_text(digital, table_text)
    warnings: list[str] = []
    dpi_used = fast_dpi
    high_coverage = image_coverage >= IMAGE_COVERAGE_OCR_THRESHOLD

    png = _render_page_png(page, dpi=fast_dpi)
    if not _png_has_ink(png):
        if high_coverage or (
            image_count > 0
            and len(digital) < PAGE_OCR_TEXT_THRESHOLD
            and forced_dpi is None
            and full_dpi > fast_dpi
        ):
            png = _render_page_png(page, dpi=full_dpi)
            dpi_used = full_dpi
            if not _png_has_ink(png) and not high_coverage:
                logger.warning(
                    'PDF page %s ink-skip but has %s images (digital=%s)',
                    page_number,
                    image_count,
                    len(digital),
                )
                return _digital_page_result(
                    page_number,
                    combined_digital,
                    digital_quality,
                    fallback='ink_skip',
                    warnings=['ink_skip_with_images'],
                )
        elif not high_coverage:
            if image_count > 0:
                logger.warning(
                    'PDF page %s ink-skip but has %s images (digital=%s)',
                    page_number,
                    image_count,
                    len(digital),
                )
            else:
                logger.info(
                    'PDF page %s has no ink; skipping OCR (digital=%s)',
                    page_number,
                    len(digital),
                )
            return _digital_page_result(
                page_number,
                combined_digital,
                digital_quality,
                fallback='ink_skip',
            )

    def _run_ocr(png_bytes: bytes) -> OcrAttempt:
        try:
            _last_ocr_attempt.set(None)
            text = _ocr_image_bytes(png_bytes)
            stored = _last_ocr_attempt.get()
            if stored is not None and (stored.text or '').strip():
                return stored
            ok, detail = get_ocr_engine_status()
            return OcrAttempt(text=text or '', engine=detail if ok else '', confidence=None)
        except ValueError as ocr_err:
            logger.warning('OCR failed for PDF page %s: %s', page_number, ocr_err)
            warnings.append(f'ocr_failed:{type(ocr_err).__name__}')
            return OcrAttempt()

    attempt = _run_ocr(png)
    if attempt.engine and attempt.engine not in ('rapidocr', ''):
        warnings.append(f'ocr:{attempt.engine}')
    ocr_quality = classify_text_quality(
        attempt.text, image_count=image_count, image_coverage=image_coverage
    )
    chosen_text, chosen_q, chosen_src = prefer_better_text(
        combined_digital,
        digital_quality,
        attempt.text,
        ocr_quality,
        ocr_confidence=attempt.confidence,
    )
    winning_is_ocr = chosen_src == 'ocr'

    if (
        forced_dpi is None
        and full_dpi > fast_dpi
        and dpi_used < full_dpi
        and chosen_q != TextQuality.GOOD
    ):
        png = _render_page_png(page, dpi=full_dpi)
        if _png_has_ink(png) or high_coverage:
            hi = _run_ocr(png)
            dpi_used = max(dpi_used, full_dpi)
            hi_q = classify_text_quality(
                hi.text, image_count=image_count, image_coverage=image_coverage
            )
            chosen_text, chosen_q, new_src = prefer_better_text(
                chosen_text,
                chosen_q,
                hi.text,
                hi_q,
                ocr_confidence=hi.confidence,
            )
            if new_src == 'ocr':
                winning_is_ocr = True
                attempt = hi
                if hi.engine and hi.engine not in ('rapidocr', ''):
                    warnings.append(f'ocr:{hi.engine}')

    used_ocr = winning_is_ocr and bool((attempt.text or '').strip())
    if used_ocr:
        page_text = chosen_text
        if table_text:
            bits = [page_text]
            _dedupe_append(bits, table_text)
            page_text = '\n\n'.join(bits).strip()
        source = 'ocr'
        engine = attempt.engine
    else:
        page_text = combined_digital
        source = 'digital'
        engine = ''

    return PageExtractionResult(
        page_number=page_number,
        source=source,
        text=page_text,
        used_ocr=used_ocr,
        ocr_engine=engine,
        ocr_confidence=attempt.confidence if used_ocr else None,
        dpi=dpi_used if used_ocr or chosen_q != TextQuality.GOOD else 0,
        quality=chosen_q,
        fallback='' if used_ocr else (warnings[0] if warnings else ''),
        warnings=warnings,
    )


def _apply_pdf_layout_enhance(extracted: str) -> str:
    if not ((RESUME_LAYOUT_ENABLED or JD_LAYOUT_ENABLED) and extracted):
        return extracted
    try:
        from app.ai.parser.layout.detector import (
            enhance_jd_text,
            enhance_resume_text,
            is_jd_layout_enabled,
        )

        if is_jd_layout_enabled():
            structured = enhance_jd_text(extracted)
        else:
            structured = enhance_resume_text(extracted)
        if structured and len(structured.strip()) >= MIN_TEXT_CHARS:
            return structured
    except Exception as exc:
        logger.debug('layout enhance skipped: %s', exc)
    return extracted


def _result_status(result: ExtractionResult) -> str:
    if result.quality == TextQuality.EMPTY and not (result.text or '').strip():
        if any('ocr_unavailable' in (w or '') for w in result.warnings):
            return STATUS_OCR_UNAVAILABLE
        if result.used_ocr:
            return STATUS_OCR_FAILED
        return STATUS_FAILED
    if result.used_ocr:
        if result.quality == TextQuality.GOOD:
            return STATUS_OCR_RECOVERED
        return STATUS_OCR_WEAK
    return STATUS_OK


def _finalize_pdf_result(
    page_results: list[PageExtractionResult],
    *,
    source: str,
    initial_dpi: int,
    final_dpi: int,
    warnings: list[str],
    fallback_reason: str = '',
) -> ExtractionResult:
    text_parts = [p.text for p in page_results if (p.text or '').strip()]
    extracted = _apply_pdf_layout_enhance('\n\n'.join(text_parts).strip())
    extracted = normalize_extracted_text(extracted)
    ocr_pages = [p.page_number for p in page_results if p.used_ocr]
    engines = [p.ocr_engine for p in page_results if p.used_ocr and p.ocr_engine]
    ocr_engine = engines[0] if engines else ''
    for p in page_results:
        for w in p.warnings or []:
            if w.startswith('ocr:') and w not in warnings:
                warnings.append(w)
    quality = classify_text_quality(extracted)
    if fallback_reason:
        warnings = list(warnings) + ([fallback_reason] if fallback_reason else [])
    result = ExtractionResult(
        text=extracted,
        source=source,
        used_ocr=bool(ocr_pages),
        ocr_engine=ocr_engine,
        ocr_pages=ocr_pages,
        initial_dpi=initial_dpi,
        final_dpi=final_dpi,
        quality=quality,
        warnings=warnings,
        page_results=page_results,
        page_count=len(page_results),
    )
    result.status = _result_status(result)
    return result


def extract_pdf_pymupdf_document(
    file_data: bytes,
    *,
    dpi: int | None = None,
    reuse_pages: dict[int, PageExtractionResult] | None = None,
) -> ExtractionResult:
    """
    PyMuPDF extract with per-page OCR. Returns ExtractionResult (may be empty).

    reuse_pages maps 1-based page numbers to prior PageExtractionResults that
    should be kept as-is (high-DPI retries only re-process the weak pages).
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise ValueError('PyMuPDF (pymupdf) is not installed') from exc

    forced_dpi = max(72, int(dpi)) if dpi is not None else None
    fast_dpi = forced_dpi or max(72, min(_ocr_dpi_fast(), OCR_DPI))
    full_dpi = forced_dpi or OCR_DPI

    doc = fitz.open(stream=file_data, filetype='pdf')
    try:
        page_count = len(doc)
        if PDF_MAX_PAGES:
            page_count = min(page_count, PDF_MAX_PAGES)

        page_results: list[PageExtractionResult] = []
        max_dpi_used = 0
        ocr_ok = OCR_ENABLED and ocr_engines_available()
        ocr_skip_logged = False
        warnings: list[str] = []

        for page_num in range(page_count):
            kept = (reuse_pages or {}).get(page_num + 1)
            if kept is not None:
                page_results.append(kept)
                max_dpi_used = max(max_dpi_used, kept.dpi or 0)
                continue
            page = doc[page_num]
            digital = (page.get_text('text') or '').strip()
            table_text = _extract_pdf_page_tables(page)
            image_count = _page_image_count(page)
            image_coverage = _page_image_coverage(page)
            combined = _combine_page_text(digital, table_text)
            digital_quality = classify_text_quality(
                combined, image_count=image_count, image_coverage=image_coverage
            )

            needs_ocr = _needs_page_ocr(digital_quality, combined, image_coverage)
            if not needs_ocr:
                page_results.append(
                    _digital_page_result(page_num + 1, combined, digital_quality)
                )
                continue

            if not ocr_ok:
                if OCR_ENABLED and not ocr_skip_logged:
                    reason = ocr_unavailable_reason()
                    logger.warning(
                        'OCR engines unavailable — skipping per-page OCR for this PDF (%s)',
                        reason,
                    )
                    warnings.append(f'ocr_unavailable:{reason}')
                    ocr_skip_logged = True
                page_results.append(
                    _digital_page_result(
                        page_num + 1,
                        combined,
                        digital_quality,
                        fallback='ocr_unavailable',
                    )
                )
                continue

            try:
                pr = _ocr_one_pdf_page(
                    page,
                    page_number=page_num + 1,
                    digital=digital,
                    table_text=table_text,
                    digital_quality=digital_quality,
                    image_count=image_count,
                    fast_dpi=fast_dpi,
                    full_dpi=full_dpi,
                    forced_dpi=forced_dpi,
                    image_coverage=image_coverage,
                )
                max_dpi_used = max(max_dpi_used, pr.dpi or 0)
                page_results.append(pr)
            except ValueError as ocr_err:
                logger.warning('OCR failed for PDF page %s: %s', page_num + 1, ocr_err)
                if not ocr_engines_available():
                    ocr_ok = False
                    warnings.append(f'ocr_unavailable:{ocr_unavailable_reason()}')
                page_results.append(
                    _digital_page_result(
                        page_num + 1,
                        combined,
                        digital_quality,
                        fallback='ocr_failed',
                    )
                )

        result = _finalize_pdf_result(
            page_results,
            source='pymupdf',
            initial_dpi=fast_dpi if any(p.used_ocr for p in page_results) else 0,
            final_dpi=max_dpi_used,
            warnings=warnings,
        )
        return result
    finally:
        doc.close()


def extract_text_from_pdf_pymupdf(file_data: bytes, *, dpi: int | None = None) -> str:
    """
    Extract text from PDF via PyMuPDF, with per-page OCR when needed.
    """
    result = extract_pdf_pymupdf_document(file_data, dpi=dpi)
    _pymupdf_document.set(result)
    if len((result.text or '').strip()) < MIN_TEXT_CHARS:
        raise ValueError(
            'Insufficient text extracted - PDF may be image-based or corrupted'
        )
    return result.text


def extract_text_from_pdf_pypdf2(file_data: bytes) -> str:
    """Legacy PyPDF2 extraction (fallback when PyMuPDF unavailable)."""
    import PyPDF2

    pdf_file = io.BytesIO(file_data)
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    pages = pdf_reader.pages
    if PDF_MAX_PAGES:
        pages = pages[:PDF_MAX_PAGES]
    text_parts = []
    for page_num, page in enumerate(pages):
        try:
            text = page.extract_text()
            if text and text.strip():
                text_parts.append(text)
        except Exception as e:
            logger.warning('Failed to extract text from page %s: %s', page_num + 1, e)
            continue
    extracted_text = '\n\n'.join(text_parts)
    if len(extracted_text.strip()) < MIN_TEXT_CHARS:
        raise ValueError('Insufficient text extracted - PDF may be image-based or corrupted')
    return extracted_text


def extract_text_from_pdf_via_api(file_data: bytes, filename: str) -> str:
    """Fallback: Extract text from PDF using external parsing API."""
    try:
        endpoint = f"{PARSING_API_URL}/api/v1/parse/resume"
        headers = {}
        if PARSING_API_KEY and PARSING_API_KEY != 'your-api-key-here':
            headers['X-API-Key'] = PARSING_API_KEY

        files = {'file': (filename, file_data, 'application/pdf')}
        response = requests.post(
            endpoint,
            files=files,
            headers=headers,
            timeout=(PARSING_API_CONNECT_TIMEOUT, PARSING_API_READ_TIMEOUT),
        )

        if response.status_code == 200:
            data = response.json()
            raw_text = data.get('raw_text', '')
            if raw_text and len(raw_text.strip()) >= MIN_TEXT_CHARS:
                logger.info(
                    'Successfully extracted %s characters via parsing API',
                    len(raw_text.strip()),
                )
                return raw_text
            raise ValueError('Parsing API returned insufficient text')
        error_data = (
            response.json()
            if response.headers.get('content-type', '').startswith('application/json')
            else {}
        )
        error_msg = error_data.get('error', f'Parsing API returned status {response.status_code}')
        raise ValueError(f'Parsing API error: {error_msg}')
    except requests.exceptions.RequestException as e:
        logger.warning('Parsing API request failed: %s', e)
        raise ValueError(f'Failed to extract text via API: {e}') from e
    except ValueError:
        raise
    except Exception as e:
        logger.warning('Parsing API extraction failed: %s', e)
        raise ValueError(f'Failed to extract text via API: {e}') from e


def _is_pymupdf_missing(exc: BaseException) -> bool:
    msg = str(exc)
    return 'pymupdf' in msg.lower() or 'PyMuPDF' in msg


def log_extraction_summary(result: ExtractionResult, *, ext: str, retry_count: int = 0) -> None:
    """Structured extract log without candidate PII (no text, email, phone, address)."""
    quality = result.quality.value if isinstance(result.quality, TextQuality) else result.quality
    logger.info(
        'extract ext=%s pages=%s ocr_pages=%s ocr_engine=%s initial_dpi=%s final_dpi=%s '
        'quality=%s source=%s status=%s retries=%s warnings=%s',
        ext,
        result.page_count,
        len(result.ocr_pages),
        result.ocr_engine or '-',
        result.initial_dpi,
        result.final_dpi,
        quality,
        result.source or '-',
        result.status,
        retry_count or result.retry_count,
        ';'.join(result.warnings[:8]) or '-',
    )


def extract_pdf_document(file_data: bytes, *, dpi: int | None = None) -> ExtractionResult:
    """Extract PDF into a request-local ExtractionResult (PyMuPDF + OCR → pdfplumber → PyPDF2)."""
    _remember_pdf_choice('')
    _pymupdf_document.set(None)
    pymupdf_result: ExtractionResult | None = None
    pymupdf_error: BaseException | None = None
    unexpected = False

    try:
        text = extract_text_from_pdf_pymupdf(file_data, dpi=dpi)
        stored = _pymupdf_document.get()
        if stored is not None and (stored.text or '') == (text or ''):
            pymupdf_result = stored
        else:
            pymupdf_result = ExtractionResult(
                text=text or '',
                source='pymupdf',
                quality=classify_text_quality(text or ''),
            )
            pymupdf_result.status = _result_status(pymupdf_result)
    except ValueError as e:
        pymupdf_error = e
        stored = _pymupdf_document.get()
        if stored is not None:
            pymupdf_result = stored
        if _is_pymupdf_missing(e):
            logger.warning('PyMuPDF unavailable, falling back to PyPDF2: %s', e)
    except Exception as e:
        pymupdf_error = e
        unexpected = True
        logger.warning('PyMuPDF extraction error, trying PyPDF2: %s', e)

    pymupdf_text = (pymupdf_result.text if pymupdf_result else None)
    used_ocr = bool(pymupdf_result and pymupdf_result.used_ocr)

    plumber_text = None
    plumber_reason = ''
    try:
        from app.ai.parser.pdfplumber_extractor import maybe_use_pdfplumber

        plumber_text, plumber_reason = maybe_use_pdfplumber(
            file_data,
            pymupdf_text=pymupdf_text,
            pymupdf_error=pymupdf_error,
            used_ocr=used_ocr,
        )
    except Exception as exc:
        logger.warning(
            'pdfplumber orchestration failed; ignoring: %s',
            type(exc).__name__,
        )
        plumber_text = None

    if plumber_text:
        quality = classify_text_quality(plumber_text)
        result = ExtractionResult(
            text=normalize_extracted_text(plumber_text),
            source='pdfplumber',
            used_ocr=False,
            quality=quality,
            warnings=[plumber_reason] if plumber_reason else [],
            page_count=pymupdf_result.page_count if pymupdf_result else 0,
            initial_dpi=pymupdf_result.initial_dpi if pymupdf_result else 0,
            final_dpi=pymupdf_result.final_dpi if pymupdf_result else 0,
        )
        result.status = _result_status(result)
        _remember_pdf_choice('pdfplumber', plumber_reason)
        return result

    if pymupdf_result and (pymupdf_result.text or '').strip():
        if plumber_reason:
            pymupdf_result.warnings.append(plumber_reason)
        pymupdf_result.source = pymupdf_result.source or 'pymupdf'
        _remember_pdf_choice('pymupdf', plumber_reason)
        return pymupdf_result

    if pymupdf_error is None:
        if pymupdf_result is not None:
            _remember_pdf_choice('pymupdf', plumber_reason)
            return pymupdf_result
        raise ValueError('Failed to extract text from PDF')

    if unexpected or _is_pymupdf_missing(pymupdf_error):
        try:
            text = extract_text_from_pdf_pypdf2(file_data)
            quality = classify_text_quality(text)
            result = ExtractionResult(
                text=normalize_extracted_text(text),
                source='pypdf2',
                quality=quality,
            )
            result.status = _result_status(result)
            _remember_pdf_choice('pypdf2')
            return result
        except Exception:
            if unexpected:
                raise ValueError(
                    f'Failed to extract text from PDF: {pymupdf_error}'
                ) from pymupdf_error
            raise

    if pymupdf_result is not None:
        _remember_pdf_choice('pymupdf', plumber_reason)
        return pymupdf_result
    raise pymupdf_error


def _iter_docx_blocks(doc):
    """Yield paragraphs and tables in document order (not paragraphs-then-tables)."""
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    body = doc.element.body
    for child in body:
        if child.tag == qn('w:p'):
            yield Paragraph(child, doc)
        elif child.tag == qn('w:tbl'):
            yield Table(child, doc)


def _serialize_docx_table(table) -> list[str]:
    lines: list[str] = []
    force_pipes = False
    for row in table.rows:
        cells = [(cell.text or '').strip() for cell in row.cells]
        deduped: list[str] = []
        for c in cells:
            if not c:
                continue
            if deduped and deduped[-1] == c:
                continue
            deduped.append(c)
        if not force_pipes and len(deduped) >= 3 and _TABULAR_HEADER_HINT.search(' '.join(deduped)):
            force_pipes = True
        serialized = _serialize_table_row(deduped, force_pipes=force_pipes)
        if serialized:
            lines.append(serialized)
    return lines


def extract_text_from_pdf(file_data: bytes, *, dpi: int | None = None) -> str:
    """Extract text from PDF: PyMuPDF (+OCR) → [pdfplumber if needed] → PyPDF2 → raise."""
    result = extract_pdf_document(file_data, dpi=dpi)
    if len((result.text or '').strip()) < MIN_TEXT_CHARS:
        raise ValueError(
            'Insufficient text extracted - PDF may be image-based or corrupted'
        )
    return result.text


def extract_text_from_docx(file_data: bytes) -> str:
    """Extract text from DOCX (document-order blocks + headers/footers + XML fallback)."""
    text_parts: list[str] = []
    try:
        docx_file = io.BytesIO(file_data)
        doc = Document(docx_file)

        try:
            for block in _iter_docx_blocks(doc):
                from docx.table import Table
                from docx.text.paragraph import Paragraph

                if isinstance(block, Paragraph):
                    if block.text.strip():
                        _dedupe_append(text_parts, block.text)
                elif isinstance(block, Table):
                    for serialized in _serialize_docx_table(block):
                        _dedupe_append(text_parts, serialized)
        except Exception:
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    _dedupe_append(text_parts, paragraph.text)
            for table in doc.tables:
                for serialized in _serialize_docx_table(table):
                    _dedupe_append(text_parts, serialized)

        try:
            for section in doc.sections:
                for hf in (section.header, section.footer):
                    if hf is None:
                        continue
                    for paragraph in hf.paragraphs:
                        if paragraph.text.strip():
                            _dedupe_append(text_parts, paragraph.text)
                    for table in getattr(hf, 'tables', []) or []:
                        for serialized in _serialize_docx_table(table):
                            _dedupe_append(text_parts, serialized)
        except Exception:
            pass
    except Exception as e:
        logger.warning('python-docx extraction failed, trying XML fallback: %s', e)

    joined = '\n\n'.join(text_parts).strip()
    if len(joined) >= MIN_TEXT_CHARS:
        return joined

    # Fallback: unzip word/document.xml (handles some corrupted / odd DOCX)
    try:
        import zipfile
        import xml.etree.ElementTree as ET

        with zipfile.ZipFile(io.BytesIO(file_data)) as zf:
            xml_name = 'word/document.xml'
            if xml_name not in zf.namelist():
                raise ValueError('DOCX missing word/document.xml')
            root = ET.fromstring(zf.read(xml_name))
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            chunks = []
            for node in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'):
                if node.text:
                    chunks.append(node.text)
                if node.tail:
                    chunks.append(node.tail)
            # Also collect paragraph breaks roughly
            xml_text = ' '.join(chunks)
            xml_text = re.sub(r'[ \t]+', ' ', xml_text)
            xml_text = re.sub(r'(\s*\n\s*)+', '\n', xml_text).strip()
            if len(xml_text) >= MIN_TEXT_CHARS:
                return xml_text
    except Exception as xml_err:
        logger.warning('DOCX XML fallback failed: %s', xml_err)

    if joined:
        return joined
    raise ValueError('Failed to extract text from DOCX: empty document')


def _force_pdf_ocr(file_data: bytes, *, dpi: int = 300) -> str:
    """Render every PDF page and OCR — last resort for scanned / empty digital layers."""
    if not ocr_engines_available():
        raise ValueError(
            f'Cannot force PDF OCR: {ocr_unavailable_reason()}'
        )
    try:
        import fitz
    except ImportError as exc:
        raise ValueError('PyMuPDF (pymupdf) is not installed') from exc
    doc = fitz.open(stream=file_data, filetype='pdf')
    try:
        page_count = len(doc)
        if PDF_MAX_PAGES:
            page_count = min(page_count, PDF_MAX_PAGES)
        parts: list[str] = []
        for page_num in range(page_count):
            page = doc[page_num]
            png = _render_page_png(page, dpi=dpi)
            coverage = _page_image_coverage(page)
            if not _png_has_ink(png) and coverage < IMAGE_COVERAGE_OCR_THRESHOLD:
                continue
            try:
                attempt = _ocr_with_recovery(png)
            except ValueError:
                continue
            if attempt.text and attempt.text.strip():
                parts.append(attempt.text.strip())
        return '\n\n'.join(parts).strip()
    finally:
        doc.close()


@timing
def extract_document(file_data: bytes, filename: str, *, dpi: int | None = None) -> ExtractionResult:
    """
    Extract text and request-local metadata from a file.

    OCR is a text-acquisition layer only. Callers must pass result.text into the
    existing layout → sections → parsers pipeline.
    """
    ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
    result = ExtractionResult(source=ext)

    if ext in IMAGE_EXTENSIONS:
        try:
            text = extract_text_from_image(file_data, filename)
            result = ExtractionResult(
                text=text,
                source='image',
                used_ocr=True,
                ocr_engine=(get_ocr_engine_status()[1] if ocr_engines_available() else ''),
                ocr_pages=[1],
                initial_dpi=0,
                final_dpi=0,
                quality=classify_text_quality(text),
                page_count=1,
                status=STATUS_OCR_RECOVERED,
            )
        except ValueError as exc:
            msg = str(exc)
            unavailable = 'unavailable' in msg.lower() or 'OCR_ENABLED' in msg
            result = ExtractionResult(
                text='',
                source='image',
                used_ocr=True,
                quality=TextQuality.EMPTY,
                status=STATUS_OCR_UNAVAILABLE if unavailable else STATUS_OCR_FAILED,
                warnings=[type(exc).__name__],
                page_count=1,
            )
            raise
    elif ext == 'pdf':
        try:
            result = extract_pdf_document(file_data, dpi=dpi)
        except ValueError as e:
            error_msg = str(e)
            if 'Insufficient text' in error_msg or 'Failed to extract' in error_msg or 'OCR' in error_msg:
                if not PARSING_API_FALLBACK:
                    raise
                logger.info('Local PDF extraction failed, trying parsing API fallback...')
                try:
                    text = extract_text_from_pdf_via_api(file_data, filename)
                    result = ExtractionResult(
                        text=text,
                        source='api',
                        quality=classify_text_quality(text),
                    )
                    result.status = _result_status(result)
                except Exception as api_error:
                    raise ValueError(
                        f'Local extraction failed: {error_msg}. '
                        f'API fallback also failed: {api_error}'
                    ) from api_error
            else:
                raise
        quality = result.quality
        if quality in (TextQuality.EMPTY, TextQuality.GARBAGE) or len(
            (result.text or '').strip()
        ) < MIN_TEXT_CHARS:
            if ocr_engines_available():
                try:
                    force_dpi = max(dpi or 0, 300)
                    forced = _force_pdf_ocr(file_data, dpi=force_dpi)
                    if len(forced) >= MIN_TEXT_CHARS:
                        forced_q = classify_text_quality(forced)
                        if QUALITY_RANK[forced_q] >= QUALITY_RANK[quality]:
                            ok, detail = get_ocr_engine_status()
                            result.text = forced
                            result.used_ocr = True
                            result.ocr_engine = detail if ok else result.ocr_engine
                            result.final_dpi = max(result.final_dpi, force_dpi)
                            result.quality = forced_q
                            result.source = result.source or 'pymupdf'
                            result.warnings.append('force_pdf_ocr')
                            result.status = _result_status(result)
                except Exception as force_err:
                    logger.warning('Force PDF OCR failed: %s', type(force_err).__name__)
                    result.warnings.append('force_pdf_ocr_failed')
            else:
                logger.warning('Skipping force PDF OCR — %s', ocr_unavailable_reason())
                result.warnings.append(f'ocr_unavailable:{ocr_unavailable_reason()}')
                if result.status == STATUS_OK and not (result.text or '').strip():
                    result.status = STATUS_OCR_UNAVAILABLE
    elif ext == 'doc':
        raise ValueError('Legacy .doc format is not supported. Please use DOCX or PDF.')
    elif ext == 'docx':
        text = extract_text_from_docx(file_data)
        result = ExtractionResult(
            text=text,
            source='docx',
            quality=classify_text_quality(text),
            status=STATUS_OK,
        )
    else:
        raise ValueError(f'Unsupported file type: {ext}')

    if RESUME_LAYOUT_ENABLED and result.text and ext != 'pdf':
        try:
            from app.ai.parser.layout.detector import enhance_resume_text

            enhanced = enhance_resume_text(result.text)
            if enhanced:
                result.text = enhanced
        except Exception as exc:
            logger.debug('enhance_resume_text skipped: %s', exc)

    result.text = normalize_extracted_text(result.text or '')
    result.quality = classify_text_quality(result.text)
    result.status = _result_status(result)
    log_extraction_summary(result, ext=ext or 'unknown')
    if len(result.text.strip()) < MIN_TEXT_CHARS:
        raise ValueError(
            'Insufficient text extracted - PDF may be image-based or corrupted'
            if ext == 'pdf'
            else f'Could not extract sufficient text from document'
        )
    return result


def retry_extract_high_dpi(
    file_data: bytes,
    filename: str,
    prior: ExtractionResult | None,
    *,
    dpi: int = 300,
) -> ExtractionResult:
    """
    High-DPI retry that re-processes only the pages that were not GOOD.

    Pages the first pass already extracted as GOOD are reused verbatim, so a
    10-page resume with one scanned page re-renders/OCRs one page, not ten.
    Falls back to a full extract_document(dpi=...) when prior per-page results
    are unavailable (non-PyMuPDF source, extract exception, non-PDF input).
    """
    ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
    keep: dict[int, PageExtractionResult] = {}
    if ext == 'pdf' and prior is not None and prior.page_results:
        keep = {
            p.page_number: p
            for p in prior.page_results
            if p.quality == TextQuality.GOOD and (p.text or '').strip()
        }
    total_pages = len(prior.page_results) if prior is not None else 0
    if not keep or len(keep) >= total_pages:
        # Nothing reusable (or nothing to redo): plain full-document retry.
        return extract_document(file_data, filename, dpi=dpi)

    try:
        result = extract_pdf_pymupdf_document(file_data, dpi=dpi, reuse_pages=keep)
    except Exception as exc:
        logger.warning(
            'Selective high-DPI retry failed (%s); falling back to full retry',
            type(exc).__name__,
        )
        return extract_document(file_data, filename, dpi=dpi)

    result.text = normalize_extracted_text(result.text or '')
    result.quality = classify_text_quality(result.text)
    result.status = _result_status(result)
    result.retry_count = (prior.retry_count if prior is not None else 0) + 1
    log_extraction_summary(result, ext='pdf')
    if len(result.text.strip()) < MIN_TEXT_CHARS:
        raise ValueError(
            'Insufficient text extracted - PDF may be image-based or corrupted'
        )
    return result


def extract_text(file_data: bytes, filename: str, *, dpi: int | None = None) -> str:
    """
    Extract text from file based on extension.
    Tries local extraction (with OCR) first, falls back to parsing API for PDFs.
    Optional dpi overrides PDF OCR render resolution (e.g. bulk retry at 300).
    """
    return extract_document(file_data, filename, dpi=dpi).text
