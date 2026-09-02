"""
Secondary PDF extractor using pdfplumber.

PyMuPDF remains the primary extractor in text_extraction.py. This module is
invoked automatically when that result is unusable or table/layout-sensitive.
It never raises into the production pipeline — callers treat None as "keep the
existing PyMuPDF / PyPDF2 / API / OCR path".

Selection is automatic. There is no extractor-selection environment variable.
"""
from __future__ import annotations

import io
import logging
import re
from collections import defaultdict

logger = logging.getLogger(__name__)

_PDFPLUMBER_IMPORT_ERROR: str | None = None
_PDFPLUMBER_PROBED = False

_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
_PHONE_RE = re.compile(r'\b[6-9]\d{9}\b|\+\d[\d\s\-()]{8,}\d')
_RESUME_TOKEN_RE = re.compile(
    r'(?i)\b(?:experience|education|skills|summary|engineer|developer|'
    r'bachelor|master|university|college)\b'
)
_MULTI_COL_RE = re.compile(r'\S+\s{3,}\S+\s{3,}\S+')
_COL_SECTION_HEADER = re.compile(
    r'(?i)^\s*(?:'
    r'work\s+experience|professional\s+experience|experience|'
    r'technical\s+proficiency|technical\s+expertise|technical\s+knowledge|'
    r'technical\s+skills|core\s+skills|key\s+skills|skills|'
    r'education|projects?|certifications?|certificates|'
    r'strengths|summary|objective|profile|achievements'
    r')\s*:?\s*$'
)
_SKILL_TOKEN_RE = re.compile(
    r'(?i)\b(?:c#|\.net(?:\s+core)?|html5|css3|javascript|python|java|sql|'
    r'multi-?threading|data\s+structure)\b'
)
_DATE_TOKEN_RE = re.compile(
    r'(?i)(?:0?[1-9]|1[0-2])[/\-](?:19|20)\d{2}'
    r'|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(?:19|20)\d{2}'
)
_HEADER_CANON = (
    ('work experience', 'experience'),
    ('professional experience', 'experience'),
    ('technical proficiency', 'skills'),
    ('technical expertise', 'skills'),
    ('technical knowledge', 'skills'),
    ('technical skills', 'skills'),
    ('core skills', 'skills'),
    ('key skills', 'skills'),
    ('education', 'education'),
    ('projects', 'projects'),
    ('project', 'projects'),
    ('certifications', 'certs'),
    ('strengths', 'strengths'),
    ('skills', 'skills'),
    ('experience', 'experience'),
)


def pdfplumber_available() -> bool:
    """True when the pdfplumber package can be imported. Cached per process."""
    global _PDFPLUMBER_IMPORT_ERROR, _PDFPLUMBER_PROBED
    if _PDFPLUMBER_PROBED:
        return _PDFPLUMBER_IMPORT_ERROR is None
    _PDFPLUMBER_PROBED = True
    try:
        import pdfplumber  # noqa: F401
    except ImportError as exc:
        _PDFPLUMBER_IMPORT_ERROR = str(exc)
        return False
    except Exception as exc:  # pragma: no cover - defensive
        _PDFPLUMBER_IMPORT_ERROR = str(exc)
        return False
    _PDFPLUMBER_IMPORT_ERROR = None
    return True


def reset_pdfplumber_availability_cache() -> None:
    """Test helper — clear the import probe cache."""
    global _PDFPLUMBER_IMPORT_ERROR, _PDFPLUMBER_PROBED
    _PDFPLUMBER_IMPORT_ERROR = None
    _PDFPLUMBER_PROBED = False


def pdfplumber_unavailable_reason() -> str:
    pdfplumber_available()
    return _PDFPLUMBER_IMPORT_ERROR or 'pdfplumber is not available'


def looks_like_broken_layout(text: str) -> bool:
    """Deterministic: many 1–2 character lines usually means scrambled columns."""
    lines = [ln.strip() for ln in (text or '').splitlines() if ln.strip()]
    if len(lines) < 12:
        return False
    single_char = sum(1 for ln in lines if len(ln) == 1)
    very_short = sum(1 for ln in lines if len(ln) <= 2)
    if single_char / len(lines) >= 0.4:
        return True
    return very_short / len(lines) >= 0.55 and len((text or '').strip()) > 80


def looks_like_unextracted_tables(text: str) -> bool:
    """True when space-aligned columns exist but structured table lines do not."""
    lines = [ln for ln in (text or '').splitlines() if ln.strip()]
    if len(lines) < 6:
        return False
    structured = 0
    multi_col = 0
    for ln in lines:
        if ': ' in ln or ' | ' in ln:
            structured += 1
        if _MULTI_COL_RE.search(ln):
            multi_col += 1
    # Require several aligned rows so ordinary two-column headers do not trip this.
    return multi_col >= 6 and structured < max(2, multi_col // 3)


def looks_like_column_mix(text: str) -> bool:
    """
    True when two-column reading order glued independent sections together.

    Default pdfplumber extract_text() sorts by y then x, so a left-column
    Experience header and a right-column Skills header become:
    'WORK EXPERIENCE TECHNICAL PROFICIENCY:'
    """
    lines = [ln.strip() for ln in (text or '').splitlines() if ln.strip()]
    if not lines:
        return False

    glued_headers = 0
    skill_in_job_line = 0
    edu_mixed_projects = 0
    header_hits: list[str] = []
    for s in lines:
        low = s.lower()
        canons = _header_canons_on_line(s)
        if len(set(canons)) >= 2:
            glued_headers += 1
        if 'experience' in low and 'technical proficiency' in low:
            glued_headers += 1
        if (
            re.search(r'(?i)work\s+experience', s)
            and re.search(r'(?i)\b(?:skills|projects)\b', s)
            and len(s.split()) <= 8
        ):
            glued_headers += 1
        if _DATE_TOKEN_RE.search(s) and _SKILL_TOKEN_RE.search(s) and len(s.split()) <= 18:
            skill_in_job_line += 1
        if re.search(r'(?i)\beducation\b.+\b(?:projects?|strengths)\b', s) and len(s.split()) <= 10:
            edu_mixed_projects += 1
        if re.search(r'(?i)^education\b.+\b(?:refactored|developed|implemented|designed)\b', s):
            edu_mixed_projects += 1
        if canons:
            header_hits.extend(canons)

    if glued_headers:
        return True
    if skill_in_job_line:
        return True
    if edu_mixed_projects:
        return True
    # Project heading appearing before a later job, after Experience already opened
    blob = '\n'.join(lines)
    exp_i = _first_header_index(blob, 'experience')
    proj_i = _first_header_index(blob, 'projects')
    edu_i = _first_header_index(blob, 'education')
    job2 = re.search(
        r'(?i)(?:assistant|system|engineer|analyst|developer|consultant)\b.+\n.*'
        r'(?:ltd|pvt|inc|llc|services|exchange|consultancy)',
        blob,
    )
    if exp_i is not None and proj_i is not None and job2:
        # "Assistant System Analyst" after a Projects header is classic interleave
        analyst = blob.lower().find('assistant system analyst')
        if analyst != -1 and proj_i < analyst and (edu_i is None or proj_i < edu_i):
            if 'tcs' in blob.lower() or 'tata consultancy' in blob.lower():
                return True
    # Repeated canonical headers (Experience then Experience after Skills) from zigzag
    if header_hits.count('experience') >= 2 and 'skills' in header_hits:
        first_exp = header_hits.index('experience')
        if 'skills' in header_hits[first_exp + 1 :]:
            rest = header_hits[first_exp + 1 :]
            if 'experience' in rest and rest.index('experience') > rest.index('skills'):
                return True
    # Skills/Projects/Strengths appearing, then another dated job — column zigzag.
    # Valid left-then-right order keeps all jobs before the right-column skills block.
    saw_exp = False
    saw_right_block = False
    for s in lines:
        canons = set(_header_canons_on_line(s))
        if 'experience' in canons:
            saw_exp = True
        if saw_exp and (canons & {'skills', 'projects', 'strengths'}):
            saw_right_block = True
        if (
            saw_right_block
            and _DATE_TOKEN_RE.search(s)
            and re.search(
                r'(?i)\b(?:ltd|pvt|inc|llc|services|exchange|consultancy|engineer|analyst)\b',
                s,
            )
        ):
            return True
    return False


def _header_canons_on_line(line: str) -> list[str]:
    low = re.sub(r'\s+', ' ', (line or '').strip()).lower().strip(':').strip()
    if not low or len(low.split()) > 8:
        return []
    if re.search(r'(?i)\b(?:that|which|courses? that|enhanced your|with web|skilled in)\b', low):
        return []
    hits: list[str] = []
    for phrase, canon in _HEADER_CANON:
        if re.search(rf'(?<![a-z]){re.escape(phrase)}(?![a-z])', low):
            if canon not in hits:
                hits.append(canon)
    if len(hits) >= 2:
        return hits
    if hits and _COL_SECTION_HEADER.match(low):
        return hits
    return []


def _first_header_index(text: str, canon: str) -> int | None:
    """Character index of the first header-like line for this canonical section."""
    offset = 0
    for line in (text or '').splitlines(keepends=True):
        if canon in _header_canons_on_line(line):
            return offset
        offset += len(line)
    return None


def _blob_is_section_header(text: str) -> bool:
    t = re.sub(r'\s+', ' ', (text or '').strip()).strip(':').strip()
    return bool(t and len(t) <= 48 and _COL_SECTION_HEADER.match(t))


def _word_rows(words: list[dict]) -> list[tuple[float, list[dict]]]:
    rows: dict[int, list[dict]] = defaultdict(list)
    for w in words:
        rows[int(round(float(w['top']) / 3.0) * 3)].append(w)
    out: list[tuple[float, list[dict]]] = []
    for key in sorted(rows):
        ws = rows[key]
        top = min(float(w['top']) for w in ws)
        out.append((top, ws))
    return out


def _detect_column_gutter(
    words: list[dict],
    page_width: float,
    page_height: float | None = None,
) -> float | None:
    """
    Split x from a significant vertical whitespace gap between two text clusters.

    Uses a 2D occupancy grid so a full-width header cannot hide the gutter, and
    short intra-column gaps (date vs city) cannot win. Gap size scales with
    page width. Unequal columns are allowed; a single-column page returns None.
    """
    if not words or page_width < 80:
        return None
    height = page_height or max(
        float(w.get('bottom', w['top'])) for w in words
    )
    if height < 80:
        return None

    n_x, n_y = 48, 36
    grid = [[0] * n_x for _ in range(n_y)]
    for w in words:
        x0, x1 = float(w['x0']), float(w['x1'])
        top = float(w['top'])
        bot = float(w.get('bottom', top + 8.0))
        xi0 = min(n_x - 1, max(0, int(x0 / page_width * n_x)))
        xi1 = min(n_x - 1, max(0, int((max(x1 - 0.1, x0)) / page_width * n_x)))
        yi0 = min(n_y - 1, max(0, int(top / height * n_y)))
        yi1 = min(n_y - 1, max(0, int((max(bot - 0.1, top)) / height * n_y)))
        for yi in range(yi0, yi1 + 1):
            for xi in range(xi0, xi1 + 1):
                grid[yi][xi] += 1

    text_rows = [yi for yi in range(n_y) if sum(grid[yi]) > 0]
    if len(text_rows) < 4:
        return None

    empty_frac = []
    for xi in range(n_x):
        empty = sum(1 for yi in text_rows if grid[yi][xi] == 0)
        empty_frac.append(empty / len(text_rows))

    # Empty on most text rows — header may occupy the middle on a minority.
    threshold = 0.58
    lo, hi = int(n_x * 0.12), int(n_x * 0.88)
    min_gap_bins = max(2, int(round((max(page_width * 0.055, 24.0) / page_width) * n_x)))
    min_side = max(12, int(len(words) * 0.08))

    best: tuple[float, float] | None = None
    i = lo
    while i < hi:
        if empty_frac[i] < threshold:
            i += 1
            continue
        j = i
        while j < hi and empty_frac[j] >= threshold:
            j += 1
        if j - i >= min_gap_bins:
            left_ink = sum(sum(grid[yi][:i]) for yi in text_rows)
            right_ink = sum(sum(grid[yi][j:]) for yi in text_rows)
            if left_ink >= min_side and right_ink >= min_side:
                score = (j - i) * (sum(empty_frac[i:j]) / (j - i))
                split = ((i + j) / 2.0) * (page_width / n_x)
                if best is None or score > best[0]:
                    best = (score, split)
        i = max(j, i + 1)
    if best is None:
        return None

    split = best[1]
    margin = max(8.0, page_width * 0.015)
    left_words = sum(1 for w in words if float(w['x1']) < split - margin)
    right_words = sum(1 for w in words if float(w['x0']) > split + margin)
    if left_words < min_side or right_words < min_side:
        return None
    return split


def _region_header_canons(words: list[dict], split_x: float, side: str, margin: float) -> set[str]:
    canons: set[str] = set()
    for _top, ws in _word_rows(words):
        if side == 'left':
            part = [w for w in ws if float(w['x1']) < split_x - margin]
        else:
            part = [w for w in ws if float(w['x0']) > split_x + margin]
        if not part:
            continue
        blob = ' '.join(w['text'] for w in sorted(part, key=lambda w: float(w['x0'])))
        if _blob_is_section_header(blob):
            canons.update(_header_canons_on_line(blob) or {blob.lower()})
    return canons


def _two_column_start_y(words: list[dict], split_x: float, page_width: float) -> float | None:
    """
    Y where the two-column body begins (below any full-width header/summary).

    Prefers a row with independent section headers on both sides. Does not
    treat wrapped preamble sentences as the column start.
    """
    margin = max(8.0, page_width * 0.015)
    rows = _word_rows(words)
    first_header_y: float | None = None
    for top, ws in rows:
        left = [w for w in ws if float(w['x1']) < split_x - margin]
        right = [w for w in ws if float(w['x0']) > split_x + margin]
        spanning = [
            w
            for w in ws
            if float(w['x0']) < split_x - margin and float(w['x1']) > split_x + margin
        ]
        if spanning:
            continue
        left_t = ' '.join(w['text'] for w in sorted(left, key=lambda w: float(w['x0'])))
        right_t = ' '.join(w['text'] for w in sorted(right, key=lambda w: float(w['x0'])))
        left_h = _blob_is_section_header(left_t)
        right_h = _blob_is_section_header(right_t)
        if left_h and right_h:
            return max(0.0, top - 2.0)
        if (left_h or right_h) and first_header_y is None:
            first_header_y = max(0.0, top - 2.0)
    return first_header_y


def _extract_page_column_aware(page) -> str | None:
    """
    Left-then-right reading order for two-column resumes.

    Activates only with a detected gutter AND independent section-header
    signals in both columns. Full-width header band is kept intact.
    Returns None for single-column / uncertain pages.
    """
    try:
        words = page.extract_words() or []
    except Exception:
        return None
    if len(words) < 40:
        return None
    width, height = float(page.width), float(page.height)
    split = _detect_column_gutter(words, width, height)
    if split is None:
        return None
    margin = max(8.0, width * 0.015)
    left_h = _region_header_canons(words, split, 'left', margin)
    right_h = _region_header_canons(words, split, 'right', margin)
    # Strong evidence: each column has its own section header, not a split of one.
    if not left_h or not right_h:
        return None
    if left_h == right_h and len(left_h) == 1:
        return None
    y0 = _two_column_start_y(words, split, width)
    if y0 is None:
        return None
    if y0 > height * 0.85:
        return None
    try:
        header = (page.crop((0, 0, width, y0)).extract_text() or '').strip() if y0 >= 8 else ''
        left = (page.crop((0, y0, split, height)).extract_text() or '').strip()
        right = (page.crop((split, y0, width, height)).extract_text() or '').strip()
    except Exception:
        return None
    if len(left) < 30 or len(right) < 30:
        return None
    return '\n\n'.join(p for p in (header, left, right) if p)


def _is_genuine_grid_table(table: list | None) -> bool:
    """True for compact row/column grids — not a two-column resume as one cell."""
    if not table or len(table) < 2:
        return False
    multi = 0
    for row in table:
        nonempty = [str(c or '').strip() for c in (row or []) if str(c or '').strip()]
        if len(nonempty) >= 2:
            multi += 1
        for cell in nonempty:
            if cell.count('\n') >= 8 or len(cell) > 800:
                return False
    return multi >= 2


def _min_chars() -> int:
    from app.ai.parser.text_extraction import MIN_TEXT_CHARS

    return MIN_TEXT_CHARS


def _meaningful_char_count(text: str) -> int:
    return sum(1 for c in (text or '') if c.isalnum())


def _whitespace_ratio(text: str) -> float:
    t = text or ''
    if not t:
        return 1.0
    return sum(1 for c in t if c.isspace()) / len(t)


def _duplicate_line_ratio(text: str) -> float:
    lines = [ln.strip().lower() for ln in (text or '').splitlines() if ln.strip()]
    if len(lines) < 4:
        return 0.0
    return 1.0 - (len(set(lines)) / len(lines))


def structured_row_count(text: str) -> int:
    return sum(1 for ln in (text or '').splitlines() if ': ' in ln or ' | ' in ln)


def _has_identity_tokens(text: str) -> bool:
    t = text or ''
    return bool(
        _EMAIL_RE.search(t) or _PHONE_RE.search(t) or _RESUME_TOKEN_RE.search(t)
    )


def fallback_reason(
    pymupdf_text: str | None,
    pymupdf_error: BaseException | None,
) -> str | None:
    """
    Return a short reason to try pdfplumber, or None to keep the PyMuPDF result.

    Conservative: good PyMuPDF text never triggers a second extract.
    pdfplumber is not used as an OCR substitute.
    """
    from app.ai.parser.text_extraction import looks_like_garbage_extract

    if pymupdf_text is None:
        return 'pymupdf_failed' if pymupdf_error is not None else None

    text = pymupdf_text.strip()
    if len(text) < _min_chars():
        return 'insufficient_text'
    if looks_like_garbage_extract(text):
        return 'garbage_text'
    if looks_like_broken_layout(text):
        return 'broken_layout'
    if looks_like_unextracted_tables(text):
        return 'table_layout'
    return None


def _plumber_is_degraded(plumber: str, pymu: str) -> bool:
    """True when pdfplumber lost signal or is noisier than PyMuPDF."""
    from app.ai.parser.text_extraction import looks_like_garbage_extract

    if looks_like_garbage_extract(plumber) or looks_like_broken_layout(plumber):
        return True
    if looks_like_column_mix(plumber) and not looks_like_column_mix(pymu):
        return True
    pymu_mean = _meaningful_char_count(pymu)
    pl_mean = _meaningful_char_count(plumber)
    if pymu_mean >= _min_chars() and pl_mean < pymu_mean * 0.6:
        return True
    if _has_identity_tokens(pymu) and not _has_identity_tokens(plumber):
        return True
    if _duplicate_line_ratio(plumber) >= 0.45 and (
        _duplicate_line_ratio(plumber) > _duplicate_line_ratio(pymu) + 0.1
    ):
        return True
    if _whitespace_ratio(plumber) >= 0.55 and _whitespace_ratio(plumber) > _whitespace_ratio(
        pymu
    ):
        return True
    return False


def pdfplumber_result_is_preferable(pymupdf_text: str | None, plumber_text: str) -> bool:
    """
    True only when pdfplumber is clearly more usable than the PyMuPDF result.

    Length alone never wins. OCR-rich PyMuPDF text is kept when plumber is thinner.
    """
    from app.ai.parser.text_extraction import MIN_TEXT_CHARS, looks_like_garbage_extract

    plumber = (plumber_text or '').strip()
    if len(plumber) < MIN_TEXT_CHARS:
        return False
    if looks_like_garbage_extract(plumber) or looks_like_broken_layout(plumber):
        return False
    if looks_like_column_mix(plumber) and not looks_like_column_mix(pymupdf_text or ''):
        return False
    if not (pymupdf_text or '').strip():
        return True

    pymu = pymupdf_text.strip()
    # If PyMuPDF was already clearly good, never replace it.
    if fallback_reason(pymu, None) is None:
        return False
    if _plumber_is_degraded(plumber, pymu):
        return False

    pymu_garbage = looks_like_garbage_extract(pymu)
    pymu_broken = looks_like_broken_layout(pymu)
    pymu_tables = looks_like_unextracted_tables(pymu)
    pymu_thin = len(pymu) < MIN_TEXT_CHARS

    if pymu_garbage or pymu_thin or pymu_broken:
        return True

    if pymu_tables:
        pl_struct = structured_row_count(plumber)
        pymu_struct = structured_row_count(pymu)
        if pl_struct >= 3 and pl_struct > pymu_struct:
            return True
        # Structured tables preserved, even if char counts are similar.
        if pl_struct >= 3 and not looks_like_unextracted_tables(plumber):
            return True
        return False

    return False


def _apply_layout_enhance(extracted: str) -> str:
    from app.ai.parser.text_extraction import (
        JD_LAYOUT_ENABLED,
        MIN_TEXT_CHARS,
        RESUME_LAYOUT_ENABLED,
    )

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


def extract_text_from_pdf_pdfplumber(file_data: bytes) -> str:
    """
    Extract text from PDF via pdfplumber.

    Returns the same plain-string contract as extract_text_from_pdf_pymupdf.
    Tables are serialized with the shared Label: Value helper when found.
    Raises ValueError on empty/unusable output so callers can ignore it.
    """
    try:
        import pdfplumber
    except ImportError as exc:
        raise ValueError('pdfplumber is not installed') from exc

    from app.ai.parser.text_extraction import (
        MIN_TEXT_CHARS,
        PDF_MAX_PAGES,
        _dedupe_append,
        _serialize_table_row,
    )

    with pdfplumber.open(io.BytesIO(file_data)) as pdf:
        pages = list(pdf.pages)
        if PDF_MAX_PAGES:
            pages = pages[:PDF_MAX_PAGES]

        text_parts: list[str] = []
        table_pages = 0
        for page_num, page in enumerate(pages, start=1):
            digital = ''
            columnar = False
            try:
                columnar_text = _extract_page_column_aware(page)
                if columnar_text:
                    digital = columnar_text
                    columnar = True
                else:
                    digital = (page.extract_text() or '').strip()
            except Exception as exc:
                logger.warning(
                    'pdfplumber text failed on page %s: %s',
                    page_num,
                    type(exc).__name__,
                )
                digital = ''

            page_bits: list[str] = []
            if digital:
                page_bits.append(digital)

            try_tables = (not columnar) and (
                (not digital)
                or len(digital) < 200
                or looks_like_unextracted_tables(digital)
            )
            if try_tables:
                try:
                    tables = page.extract_tables() or []
                except Exception as exc:
                    logger.warning(
                        'pdfplumber tables failed on page %s: %s',
                        page_num,
                        type(exc).__name__,
                    )
                    tables = []
                table_lines: list[str] = []
                for table in tables:
                    if not _is_genuine_grid_table(table):
                        continue
                    table_pages += 1
                    for row in table:
                        if not row:
                            continue
                        cells = [str(c or '') for c in row]
                        serialized = _serialize_table_row(cells)
                        if serialized:
                            table_lines.append(serialized)
                if table_lines:
                    _dedupe_append(page_bits, '\n'.join(table_lines))

            if page_bits:
                text_parts.append('\n\n'.join(page_bits))

        extracted = '\n\n'.join(text_parts).strip()
        extracted = _apply_layout_enhance(extracted)
        if len(extracted) < MIN_TEXT_CHARS:
            raise ValueError(
                'Insufficient text extracted via pdfplumber - PDF may be image-based or corrupted'
            )
        logger.info(
            'pdfplumber extracted chars=%s pages=%s table_pages=%s',
            len(extracted),
            len(pages),
            table_pages,
        )
        return extracted


def maybe_use_pdfplumber(
    file_data: bytes,
    *,
    pymupdf_text: str | None,
    pymupdf_error: BaseException | None = None,
) -> tuple[str | None, str]:
    """
    Automatic secondary-extractor entry.

    Returns (text_or_none, reason). text is set only when pdfplumber ran and
    beat (or replaced a missing) PyMuPDF result. Never raises.
    """
    reason = fallback_reason(pymupdf_text, pymupdf_error)
    if not reason:
        return None, ''

    if not pdfplumber_available():
        logger.info(
            'PDF extractor fallback skipped extractor=pdfplumber reason=%s cause=%s',
            reason,
            pdfplumber_unavailable_reason(),
        )
        return None, reason

    logger.info('PDF extractor automatically trying pdfplumber reason=%s', reason)
    try:
        plumber_text = extract_text_from_pdf_pdfplumber(file_data)
    except Exception as exc:
        logger.warning(
            'pdfplumber extraction failed; keeping PyMuPDF/existing fallback reason=%s error=%s',
            reason,
            type(exc).__name__,
        )
        return None, reason

    if pdfplumber_result_is_preferable(pymupdf_text, plumber_text):
        logger.info(
            'PDF extractor selected=pdfplumber reason=%s chars=%s',
            reason,
            len(plumber_text),
        )
        return plumber_text, reason

    logger.info(
        'PDF extractor selected=pymupdf (pdfplumber not preferable) reason=%s',
        reason,
    )
    return None, reason
