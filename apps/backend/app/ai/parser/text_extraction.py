"""
Text Extraction from PDF, DOCX, and image files.

Prefers PyMuPDF for digital PDF text; falls back to OCR for scanned/image PDFs
and direct image uploads. OCR uses RapidOCR (pip-only via requirements.txt);
optional system Tesseract is a secondary fallback. Optional PARSING_API is last resort.
"""
from __future__ import annotations

import io
import logging
import os
import shutil
from typing import Any

import requests
from docx import Document

logger = logging.getLogger(__name__)

PARSING_API_URL = os.getenv('PARSING_API_URL', 'http://localhost:4000')
PARSING_API_KEY = os.getenv('PARSING_API_KEY', 'your-api-key-here')
PDF_MAX_PAGES = max(0, int(os.getenv('PDF_MAX_PAGES', '0')))
OCR_ENABLED = os.getenv('OCR_ENABLED', 'true').lower() in ('1', 'true', 'yes')
OCR_LANG = os.getenv('OCR_LANG', 'eng')
OCR_DPI = max(72, int(os.getenv('OCR_DPI', '250')))
# Try a lower DPI first for speed; escalate when OCR text is thin.
OCR_DPI_FAST = max(72, int(os.getenv('OCR_DPI_FAST', '180')))
MIN_TEXT_CHARS = 30
# Per-page digital text below this triggers OCR.
PAGE_OCR_TEXT_THRESHOLD = 80
# If digital text is below this and page has images, prefer OCR.
PAGE_SPARSE_TEXT_WITH_IMAGES = 200
RESUME_LAYOUT_ENABLED = os.getenv('RESUME_LAYOUT_ENABLED', 'true').lower() in (
    '1',
    'true',
    'yes',
)

IMAGE_EXTENSIONS = frozenset({'png', 'jpg', 'jpeg', 'webp', 'tif', 'tiff', 'bmp'})

# Invisible / formatting chars common in Word→PDF exports (ZWSP, soft hyphen, BOM, etc.)
_INVISIBLE_CHARS_RE = __import__('re').compile(
    r'[\u200b\u200c\u200d\u2060\ufeff\u00ad\u180e]'
)


def normalize_extracted_text(text: str) -> str:
    """
    Strip PDF/Word invisible characters that break name/header matching.
    Zero-width spaces after names (e.g. 'DHRUTI JADEJA\\u200b') are common.
    """
    if not text:
        return ''
    t = _INVISIBLE_CHARS_RE.sub('', text)
    t = t.replace('\xa0', ' ').replace('\u202f', ' ')
    return t


_rapidocr_engine: Any = None


def _tesseract_available() -> bool:
    return bool(shutil.which('tesseract'))


def _get_rapidocr_engine() -> Any:
    """Lazy-load RapidOCR (bundled ONNX models via pip)."""
    global _rapidocr_engine
    if _rapidocr_engine is not None:
        return _rapidocr_engine
    from rapidocr_onnxruntime import RapidOCR

    _rapidocr_engine = RapidOCR()
    return _rapidocr_engine


def _ocr_with_rapidocr(image_bytes: bytes) -> str:
    """OCR via RapidOCR (pip-installable, no system binary)."""
    import numpy as np
    from PIL import Image

    from app.ai.parser.layout.preprocess import preprocess_image_bytes

    processed = preprocess_image_bytes(image_bytes)
    image = Image.open(io.BytesIO(processed))
    if image.mode not in ('RGB', 'L'):
        image = image.convert('RGB')
    arr = np.array(image)
    engine = _get_rapidocr_engine()
    result, _ = engine(arr)
    if not result:
        return ''
    return _join_ocr_detections_reading_order(result)


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


def _ocr_with_tesseract(image_bytes: bytes, *, lang: str | None = None) -> str:
    """OCR via system Tesseract + pytesseract (optional fallback)."""
    import pytesseract
    from PIL import Image

    from app.ai.parser.layout.preprocess import preprocess_image_bytes

    processed = preprocess_image_bytes(image_bytes)
    image = Image.open(io.BytesIO(processed))
    if image.mode not in ('RGB', 'L'):
        image = image.convert('RGB')
    text = pytesseract.image_to_string(image, lang=lang or OCR_LANG)
    return (text or '').strip()


def _ocr_image_bytes_plain(image_bytes: bytes, *, lang: str | None = None) -> str:
    """Run RapidOCR then Tesseract without layout structuring."""
    errors: list[str] = []

    try:
        text = _ocr_with_rapidocr(image_bytes)
        if text:
            return text
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
                return text
            errors.append('Tesseract returned empty text')
        except Exception as exc:
            errors.append(f'Tesseract failed: {exc}')

    detail = '; '.join(errors) if errors else 'no OCR engine available'
    raise ValueError(
        f'OCR failed ({detail}). Install RapidOCR with Python 3.10–3.12 '
        f'(pip install rapidocr-onnxruntime), or install system Tesseract as a fallback.'
    )


def _ocr_image_bytes(image_bytes: bytes, *, lang: str | None = None) -> str:
    """
    Run OCR on raw image bytes.

    Primary: RapidOCR (+ OpenCV preprocess, optional layout).
    Secondary: system Tesseract if available.
    """
    if not OCR_ENABLED:
        raise ValueError('OCR is disabled (OCR_ENABLED=false)')

    if RESUME_LAYOUT_ENABLED:
        try:
            from app.ai.parser.layout.detector import ocr_image_with_layout

            text, source = ocr_image_with_layout(
                image_bytes,
                ocr_fn=lambda b: _ocr_image_bytes_plain(b, lang=lang),
            )
            if text and text.strip():
                logger.debug('Layout OCR source=%s chars=%s', source, len(text))
                return text.strip()
        except Exception as exc:
            logger.warning('Layout OCR failed, falling back to plain OCR: %s', exc)

    return _ocr_image_bytes_plain(image_bytes, lang=lang)


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
    """Render a PyMuPDF page to PNG bytes."""
    import fitz

    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    return pix.tobytes('png')


def _page_needs_ocr(page, digital_text: str) -> bool:
    """True when digital text is thin or the page is image-heavy with sparse text."""
    text_len = len((digital_text or '').strip())
    image_count = 0
    try:
        image_count = len(page.get_images(full=True) or [])
    except Exception:
        image_count = 0

    if text_len < PAGE_OCR_TEXT_THRESHOLD:
        return True
    if image_count > 0 and text_len < PAGE_SPARSE_TEXT_WITH_IMAGES:
        return True
    # Large image count with modest text often means scanned page + junk text layer
    if image_count >= 3 and text_len < 400:
        return True
    return False


def extract_text_from_pdf_pymupdf(file_data: bytes, *, dpi: int | None = None) -> str:
    """
    Extract text from PDF via PyMuPDF, with per-page OCR when needed.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise ValueError('PyMuPDF (pymupdf) is not installed') from exc

    # Explicit dpi from caller wins; otherwise adaptive fast → full
    forced_dpi = max(72, int(dpi)) if dpi is not None else None
    fast_dpi = forced_dpi or max(72, min(OCR_DPI_FAST, OCR_DPI))
    full_dpi = forced_dpi or OCR_DPI

    doc = fitz.open(stream=file_data, filetype='pdf')
    try:
        page_count = len(doc)
        if PDF_MAX_PAGES:
            page_count = min(page_count, PDF_MAX_PAGES)

        text_parts: list[str] = []
        used_ocr = False
        max_dpi_used = fast_dpi

        for page_num in range(page_count):
            page = doc[page_num]
            digital = (page.get_text('text') or '').strip()

            if _page_needs_ocr(page, digital):
                if OCR_ENABLED:
                    try:
                        png = _render_page_png(page, dpi=fast_dpi)
                        ocr_text = _ocr_image_bytes(png)
                        # Escalate DPI when fast pass is too thin
                        if (
                            forced_dpi is None
                            and full_dpi > fast_dpi
                            and len((ocr_text or '').strip()) < PAGE_OCR_TEXT_THRESHOLD
                        ):
                            png = _render_page_png(page, dpi=full_dpi)
                            ocr_text = _ocr_image_bytes(png)
                            max_dpi_used = max(max_dpi_used, full_dpi)
                        if ocr_text:
                            text_parts.append(ocr_text)
                            used_ocr = True
                            continue
                    except ValueError as ocr_err:
                        logger.warning(
                            'OCR failed for PDF page %s: %s', page_num + 1, ocr_err
                        )
                        # Do not treat thin digital junk as success when OCR was needed
                        if digital and len(digital) >= PAGE_OCR_TEXT_THRESHOLD:
                            text_parts.append(digital)
                        continue
                elif digital and len(digital) >= PAGE_OCR_TEXT_THRESHOLD:
                    text_parts.append(digital)
            elif digital:
                text_parts.append(digital)

        extracted = '\n\n'.join(text_parts).strip()
        if RESUME_LAYOUT_ENABLED and extracted:
            try:
                from app.ai.parser.layout.detector import enhance_resume_text

                extracted = enhance_resume_text(extracted)
            except Exception as exc:
                logger.debug('enhance_resume_text skipped: %s', exc)

        if len(extracted) < MIN_TEXT_CHARS:
            raise ValueError(
                'Insufficient text extracted - PDF may be image-based or corrupted'
            )
        if used_ocr:
            logger.info(
                'Extracted %s characters from PDF (%s pages, OCR used, dpi=%s)',
                len(extracted),
                page_count,
                max_dpi_used,
            )
        return extracted
    finally:
        doc.close()


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
        response = requests.post(endpoint, files=files, headers=headers, timeout=60)

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


def extract_text_from_pdf(file_data: bytes, *, dpi: int | None = None) -> str:
    """Extract text from PDF: PyMuPDF (+OCR) → PyPDF2 → raise."""
    try:
        return extract_text_from_pdf_pymupdf(file_data, dpi=dpi)
    except ValueError as e:
        # If PyMuPDF missing, try PyPDF2; otherwise re-raise for OCR/API fallback chain.
        if 'pymupdf' in str(e).lower() or 'PyMuPDF' in str(e):
            logger.warning('PyMuPDF unavailable, falling back to PyPDF2: %s', e)
            return extract_text_from_pdf_pypdf2(file_data)
        raise
    except Exception as e:
        # Unexpected PyMuPDF errors — try PyPDF2 before failing.
        logger.warning('PyMuPDF extraction error, trying PyPDF2: %s', e)
        try:
            return extract_text_from_pdf_pypdf2(file_data)
        except Exception:
            raise ValueError(f'Failed to extract text from PDF: {e}') from e


def extract_text_from_docx(file_data: bytes) -> str:
    """Extract text from DOCX file (paragraphs + tables)."""
    try:
        docx_file = io.BytesIO(file_data)
        doc = Document(docx_file)

        text_parts = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        text_parts.append(cell.text)

        return '\n\n'.join(text_parts)
    except Exception as e:
        raise ValueError(f'Failed to extract text from DOCX: {e}') from e


def extract_text(file_data: bytes, filename: str, *, dpi: int | None = None) -> str:
    """
    Extract text from file based on extension.
    Tries local extraction (with OCR) first, falls back to parsing API for PDFs.
    Optional dpi overrides PDF OCR render resolution (e.g. bulk retry at 300).
    """
    ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''

    if ext in IMAGE_EXTENSIONS:
        text = extract_text_from_image(file_data, filename)
    elif ext == 'pdf':
        try:
            text = extract_text_from_pdf(file_data, dpi=dpi)
        except ValueError as e:
            error_msg = str(e)
            if 'Insufficient text' in error_msg or 'Failed to extract' in error_msg or 'OCR' in error_msg:
                logger.info('Local PDF extraction failed, trying parsing API fallback...')
                try:
                    text = extract_text_from_pdf_via_api(file_data, filename)
                except Exception as api_error:
                    raise ValueError(
                        f'Local extraction failed: {error_msg}. '
                        f'API fallback also failed: {api_error}'
                    ) from api_error
            else:
                raise
    elif ext == 'doc':
        raise ValueError('Legacy .doc format is not supported. Please use DOCX or PDF.')
    elif ext == 'docx':
        text = extract_text_from_docx(file_data)
    else:
        raise ValueError(f'Unsupported file type: {ext}')

    if RESUME_LAYOUT_ENABLED and text and ext != 'pdf':
        # PDF path already enhances inside pymupdf extractor
        try:
            from app.ai.parser.layout.detector import enhance_resume_text

            text = enhance_resume_text(text)
        except Exception as exc:
            logger.debug('enhance_resume_text skipped: %s', exc)
    return normalize_extracted_text(text or '')
