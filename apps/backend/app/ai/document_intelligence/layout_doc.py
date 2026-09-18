"""
Layout-aware intermediate resume representation.

Plain text always works. PDF bytes may add page/line/bbox metadata via PyMuPDF
dict extraction without replacing extract_text_from_pdf_pymupdf().
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.ai.document_intelligence.bullets import (
    is_bullet_line,
    split_inline_bullets,
    strip_bullet_prefix,
)

_HEADING_NOISE = re.compile(
    r'(?i)^(developed|designed|built|worked|responsible|managed|implemented)\b'
)


@dataclass
class LayoutLine:
    text: str
    page: int = 1
    line_no: int = 0
    bbox: tuple[float, float, float, float] | None = None
    font_size: float | None = None
    font_name: str = ''
    is_bullet: bool = False
    is_heading_candidate: bool = False
    column: int | None = None


@dataclass
class LayoutTable:
    page: int
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    bbox: tuple[float, float, float, float] | None = None


@dataclass
class LayoutDocument:
    """Normalized document the section parsers can reason about."""

    lines: list[LayoutLine] = field(default_factory=list)
    tables: list[LayoutTable] = field(default_factory=list)
    source: str = 'plain_text'  # plain_text | pdf_dict
    page_count: int = 1

    def normalized_text(self) -> str:
        """Reading-order text with one logical item per line (bullets kept)."""
        return '\n'.join(ln.text for ln in self.lines if (ln.text or '').strip())

    def heading_labels(self) -> list[str]:
        return [ln.text for ln in self.lines if ln.is_heading_candidate]


def _looks_like_heading(text: str) -> bool:
    s = (text or '').strip().strip(':').strip()
    if not s or len(s) > 72:
        return False
    if _HEADING_NOISE.match(s):
        return False
    words = s.split()
    if len(words) > 8:
        return False
    if s.endswith('.') and len(words) > 3:
        return False
    try:
        from app.ai.parser.layout.heuristic import normalize_section_header

        return bool(normalize_section_header(s))
    except Exception:
        return False


def from_plain_text(text: str) -> LayoutDocument:
    """Build a layout document from extracted text (no coordinates)."""
    raw = split_inline_bullets(text or '')
    lines: list[LayoutLine] = []
    for i, raw_ln in enumerate(raw.splitlines(), start=1):
        t = raw_ln.rstrip()
        if not t.strip():
            continue
        lines.append(
            LayoutLine(
                text=t.strip(),
                line_no=i,
                is_bullet=is_bullet_line(t),
                is_heading_candidate=_looks_like_heading(strip_bullet_prefix(t)),
            )
        )
    return LayoutDocument(lines=lines, source='plain_text', page_count=1)


def from_pdf_bytes(file_data: bytes, *, max_pages: int = 40) -> LayoutDocument | None:
    """
    Optional PyMuPDF dict pass for coordinates/fonts/tables.

    Does not replace extract_text_from_pdf_pymupdf. Returns None on failure
    so callers keep the existing digital-text path.
    """
    if not file_data or not file_data.startswith(b'%PDF'):
        return None
    try:
        import fitz
    except ImportError:
        return None
    try:
        doc = fitz.open(stream=file_data, filetype='pdf')
    except Exception:
        return None
    lines: list[LayoutLine] = []
    tables: list[LayoutTable] = []
    line_no = 0
    try:
        n_pages = min(len(doc), max_pages)
        for page_i in range(n_pages):
            page = doc[page_i]
            try:
                tabs = page.find_tables()
                for t in tabs or []:
                    extracted = t.extract() or []
                    if len(extracted) < 2:
                        continue
                    headers = [str(c or '').strip() for c in extracted[0]]
                    body = [
                        [str(c or '').strip() for c in row]
                        for row in extracted[1:]
                    ]
                    # Reject page-sized fake tables (two-column / sidebar layouts)
                    if any(len(c) > 400 or c.count('\n') >= 8 for c in headers):
                        continue
                    if any(len(c) > 400 or c.count('\n') >= 8 for row in body for c in row):
                        continue
                    tables.append(
                        LayoutTable(
                            page=page_i + 1,
                            headers=headers,
                            rows=body,
                            bbox=tuple(t.bbox) if getattr(t, 'bbox', None) else None,
                        )
                    )
            except Exception:
                pass
            d = page.get_text('dict') or {}
            for block in d.get('blocks') or []:
                if block.get('type') != 0:
                    continue
                for ln in block.get('lines') or []:
                    spans = ln.get('spans') or []
                    if not spans:
                        continue
                    text = ''.join(str(s.get('text') or '') for s in spans).strip()
                    if not text:
                        continue
                    bbox = ln.get('bbox')
                    size = None
                    font = ''
                    if spans:
                        try:
                            size = float(spans[0].get('size') or 0) or None
                        except (TypeError, ValueError):
                            size = None
                        font = str(spans[0].get('font') or '')
                    line_no += 1
                    for piece in split_inline_bullets(text).splitlines():
                        piece = piece.strip()
                        if not piece:
                            continue
                        lines.append(
                            LayoutLine(
                                text=piece,
                                page=page_i + 1,
                                line_no=line_no,
                                bbox=tuple(bbox) if bbox else None,
                                font_size=size,
                                font_name=font,
                                is_bullet=is_bullet_line(piece),
                                is_heading_candidate=_looks_like_heading(piece),
                            )
                        )
    finally:
        doc.close()
    if not lines:
        return None
    return LayoutDocument(
        lines=lines,
        tables=tables,
        source='pdf_dict',
        page_count=max((ln.page for ln in lines), default=1),
    )


_SIDEBAR_CUE = re.compile(
    r'(?i)\b(?:skills?|languages?|tools?|databases?|contact|phone|email|'
    r'mobile|linkedin|hobbies|strengths|personal\s+details)\b'
)
_MAIN_CUE = re.compile(
    r'(?i)\b(?:experience|education|company|employer|organization|duration|'
    r'responsibilities|currently\s+working|worked\s+with|bachelor|university)\b'
)
_DATE_TOKEN_RE = re.compile(
    r'(?i)(?:'
    r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(?:19|20)\d{2}'
    r'|(?:0?[1-9]|1[0-2])[/\-](?:19|20)\d{2}'
    r'|(?:19|20)\d{2}'
    r'|present|current|now|ongoing|till\s*date'
    r')'
)
_RAIL_TITLE_NOISE = re.compile(
    r'(?i)\b(?:engineer|developer|manager|analyst|intern|experience|education|'
    r'skills|python|javascript|summary|project)\b'
)
_RAIL_ORG_NOISE = re.compile(
    r'(?i)\b(?:pvt|ltd|llc|inc|university|college|limited)\b'
)


def _line_width(ln: LayoutLine) -> float:
    if not ln.bbox:
        return 0.0
    return max(0.0, ln.bbox[2] - ln.bbox[0])


def _column_score(lines: list[LayoutLine], cue: re.Pattern[str]) -> float:
    if not lines:
        return 0.0
    hits = sum(1 for ln in lines if cue.search(ln.text or ''))
    return hits / max(len(lines), 1)


def _is_date_range_line(text: str) -> bool:
    """True for a compact employment/education date or date-range line."""
    s = (text or '').strip()
    if not s or len(s) > 80:
        return False
    if not _DATE_TOKEN_RE.search(s):
        return False
    leftover = _DATE_TOKEN_RE.sub(' ', s)
    leftover = re.sub(r'[-–—to/(),.|]+', ' ', leftover)
    leftover = ' '.join(leftover.split())
    return len(leftover.split()) <= 3


def _is_job_headerish_line(text: str) -> bool:
    s = (text or '').strip()
    if not s or _is_date_range_line(s):
        return False
    if s[:1] in '•·*-●' or (s[:1].isdigit() and '.' in s[:3]):
        return False
    words = s.split()
    if not (1 <= len(words) <= 8) or s.endswith('.'):
        return False
    return True


def _count_adjacent_job_dates(text: str) -> int:
    """How often a short header sits next to a date range (good reading order)."""
    lines = [ln.strip() for ln in (text or '').splitlines() if ln.strip()]
    n = 0
    for i in range(len(lines) - 1):
        a, b = lines[i], lines[i + 1]
        if _is_job_headerish_line(a) and _is_date_range_line(b):
            n += 1
        elif _is_date_range_line(a) and _is_job_headerish_line(b):
            n += 1
    return n


def _is_date_location_rail_line(text: str) -> bool:
    """Dates or short locations that sit in a right-hand employment rail."""
    s = (text or '').strip()
    if not s or len(s) > 70 or s[:1] in '•·*-●':
        return False
    if _is_date_range_line(s):
        return True
    words = s.split()
    if not (1 <= len(words) <= 5) or s.endswith('.'):
        return False
    if _RAIL_TITLE_NOISE.search(s) or _RAIL_ORG_NOISE.search(s):
        return False
    if ',' in s:
        return True
    return bool(
        s[:1].isupper()
        and all((not w[:1].isalpha()) or w[:1].isupper() for w in words)
    )


_SKILLS_HEADING_LINE = re.compile(
    r'(?i)^(?:(?:technical|key|core|soft|professional|relevant|other)\s+)?'
    r'(?:skills?|languages?|certifications?|competencies)\s*:?\s*$'
)


def _column_has_skills_heading(col: list[LayoutLine]) -> bool:
    return any(_SKILLS_HEADING_LINE.match((ln.text or '').strip()) for ln in col)


def _column_is_date_location_rail(col: list[LayoutLine]) -> bool:
    """True when a column is mostly dates/cities, not a skills-only sidebar."""
    if len(col) < 3:
        return False
    hits = sum(1 for ln in col if _is_date_location_rail_line(ln.text or ''))
    date_hits = sum(1 for ln in col if _is_date_range_line(ln.text or ''))
    bullets = sum(
        1
        for ln in col
        if (ln.text or '').lstrip()[:1] in '•·*-●' or len(ln.text or '') > 90
    )
    skillish = sum(
        1
        for ln in col
        if _SIDEBAR_CUE.search(ln.text or '') and len((ln.text or '').split()) <= 5
    )
    # A skills/languages column with a few year tokens is not an employment rail.
    if skillish >= 2 and date_hits < 3:
        return False
    if _column_has_skills_heading(col) and date_hits < 3:
        return False
    return (
        date_hits >= 3
        and hits / len(col) >= 0.45
        and bullets <= max(1, int(len(col) * 0.25))
    )


def _interleave_date_rail(
    header: list[LayoutLine],
    main: list[LayoutLine],
    rail: list[LayoutLine],
) -> list[str]:
    """Pair same-Y date/location rail lines with the experience column.

    Leftover sidebar text (skills, languages, contact) stays after the main
    column instead of being woven into job bodies.
    """

    def _sort_col(col: list[LayoutLine]) -> list[LayoutLine]:
        return sorted(col, key=lambda ln: (ln.bbox[1] if ln.bbox else 0.0, ln.bbox[0] if ln.bbox else 0.0))

    main_s = _sort_col(main)
    rail_s = _sort_col(rail)
    date_lines = [ln for ln in rail_s if _is_date_location_rail_line(ln.text or '')]
    other_lines = [ln for ln in rail_s if not _is_date_location_rail_line(ln.text or '')]
    used: set[int] = set()
    out: list[str] = []
    out.extend(ln.text for ln in _sort_col(header))
    if header:
        out.append('')
    for ln in main_s:
        out.append(ln.text)
        if not ln.bbox:
            continue
        y = ln.bbox[1]
        for i, rl in enumerate(date_lines):
            if i in used or not rl.bbox:
                continue
            if abs(rl.bbox[1] - y) <= 16:
                out.append(rl.text)
                used.add(i)
    leftover_dates = [date_lines[i] for i in range(len(date_lines)) if i not in used]
    for ln in leftover_dates:
        out.append(ln.text)
    if other_lines:
        out.append('')
        out.extend(ln.text for ln in other_lines)
    return out


def _reconstruct_page_regions(rows: list[LayoutLine]) -> list[str]:
    """HEADER → MAIN → SIDEBAR when geometry supports it; else reading order."""
    boxed = [ln for ln in rows if ln.bbox]
    if len(boxed) < 8:
        return [ln.text for ln in rows]
    min_x = min(ln.bbox[0] for ln in boxed)
    max_x = max(ln.bbox[2] for ln in boxed)
    min_y = min(ln.bbox[1] for ln in boxed)
    max_y = max(ln.bbox[3] for ln in boxed)
    width = max_x - min_x
    height = max_y - min_y
    if width < 200 or height < 80:
        return [ln.text for ln in rows]

    header_cut = min_y + height * 0.18
    sizes = [ln.font_size or 0.0 for ln in boxed if ln.font_size]
    median_size = sorted(sizes)[len(sizes) // 2] if sizes else 0.0
    header: list[LayoutLine] = []
    body: list[LayoutLine] = []
    for ln in boxed:
        y0 = ln.bbox[1]
        span_w = _line_width(ln)
        large = bool(ln.font_size and median_size and ln.font_size >= median_size * 1.25)
        fullish = span_w >= width * 0.55
        if y0 <= header_cut and (fullish or large or span_w >= width * 0.35):
            header.append(ln)
        else:
            body.append(ln)
    if len(header) < 2:
        body = boxed
        header = []

    work = body or boxed
    xs = sorted((ln.bbox[0] + ln.bbox[2]) / 2.0 for ln in work)
    if len(xs) < 6:
        ordered = sorted(boxed, key=lambda ln: (ln.bbox[1], ln.bbox[0]))
        return [ln.text for ln in ordered]
    gaps = [(xs[i + 1] - xs[i], (xs[i] + xs[i + 1]) / 2.0) for i in range(len(xs) - 1)]
    gap, gutter = max(gaps, key=lambda g: g[0])
    if gap < max(36.0, width * 0.10):
        ordered = sorted(boxed, key=lambda ln: (ln.bbox[1], ln.bbox[0]))
        return [ln.text for ln in ordered]

    left = [ln for ln in work if (ln.bbox[0] + ln.bbox[2]) / 2.0 < gutter]
    right = [ln for ln in work if (ln.bbox[0] + ln.bbox[2]) / 2.0 >= gutter]
    if len(left) < 3 or len(right) < 3:
        ordered = sorted(boxed, key=lambda ln: (ln.bbox[1], ln.bbox[0]))
        return [ln.text for ln in ordered]

    def _sort_col(col: list[LayoutLine]) -> list[LayoutLine]:
        return sorted(col, key=lambda ln: (ln.bbox[1], ln.bbox[0]))

    # Date/location rail: pair same-Y dates with the experience column.
    # Do not y-sort the whole page — that weaves skills/contact sidebars into jobs.
    left_rail = _column_is_date_location_rail(left)
    right_rail = _column_is_date_location_rail(right)
    if left_rail and not right_rail:
        return _interleave_date_rail(header, right, left)
    if right_rail and not left_rail:
        return _interleave_date_rail(header, left, right)
    if left_rail and right_rail:
        out: list[str] = []
        out.extend(ln.text for ln in _sort_col(header))
        if header:
            out.append('')
        out.extend(ln.text for ln in sorted(work, key=lambda ln: (ln.bbox[1], ln.bbox[0])))
        return out

    def _col_width(col: list[LayoutLine]) -> float:
        return max(ln.bbox[2] for ln in col) - min(ln.bbox[0] for ln in col)

    left_w, right_w = _col_width(left), _col_width(right)
    left_sidebar = left_w < right_w * 0.62
    right_sidebar = right_w < left_w * 0.62
    if left_sidebar and not right_sidebar:
        sidebar, main = left, right
    elif right_sidebar and not left_sidebar:
        sidebar, main = right, left
    else:
        left_side = _column_score(left, _SIDEBAR_CUE) - _column_score(left, _MAIN_CUE)
        right_side = _column_score(right, _SIDEBAR_CUE) - _column_score(right, _MAIN_CUE)
        if left_side >= right_side:
            sidebar, main = left, right
        else:
            sidebar, main = right, left

    out: list[str] = []
    out.extend(ln.text for ln in _sort_col(header))
    if header:
        out.append('')
    out.extend(ln.text for ln in _sort_col(main))
    out.append('')
    out.extend(ln.text for ln in _sort_col(sidebar))
    return out


def _skills_heading_count(text: str) -> int:
    return sum(
        1
        for ln in (text or '').splitlines()
        if _SKILLS_HEADING_LINE.match(ln.strip())
    )


def maybe_reorder_two_column(extracted_text: str, file_data: bytes | None) -> str | None:
    """HEADER / MAIN / SIDEBAR reading order when PDF boxes show regions.

    Uses gutter + column width + content cues. Does not bisect at page midpoint.
    """
    if not file_data:
        return None
    doc = from_pdf_bytes(file_data)
    if not doc or not doc.lines:
        return None
    boxed = [ln for ln in doc.lines if ln.bbox and (ln.text or '').strip()]
    if len(boxed) < 8:
        return None
    page_groups: dict[int, list[LayoutLine]] = {}
    for ln in boxed:
        page_groups.setdefault(ln.page, []).append(ln)
    out: list[str] = []
    for page in sorted(page_groups):
        out.extend(_reconstruct_page_regions(page_groups[page]))
        out.append('')
    text = '\n'.join(out).strip()
    if len(text) < max(30, int(len(extracted_text or '') * 0.45)):
        return None
    # Keep the original extract when it already pairs job headers with dates
    # and reconstruction would detach them (common Naukri/Harvard date rails).
    orig_adj = _count_adjacent_job_dates(extracted_text or '')
    new_adj = _count_adjacent_job_dates(text)
    # If the extract already pairs short headers with dates, leave it alone.
    # Reconstruction can invent extra pairs while destroying experience bodies.
    if orig_adj >= 2:
        return None
    if new_adj <= orig_adj:
        return None
    # Never destroy a Skills/Languages sidebar just to create more date pairs.
    orig_skills = _skills_heading_count(extracted_text or '')
    new_skills = _skills_heading_count(text)
    if orig_skills and new_skills < orig_skills:
        return None
    return text


def normalize_extracted_resume_text(
    text: str,
    *,
    file_data: bytes | None = None,
) -> str:
    """
    Preserve bullet boundaries in extracted text.

    Never replaces the primary PyMuPDF/pdfplumber extract with dict-order text.
    PDF layout metadata is available via from_pdf_bytes() for table harvest.
    """
    from app.ai.document_intelligence.bullets import split_inline_bullets, restore_inferred_list_markers

    return restore_inferred_list_markers(split_inline_bullets(text or ''))


def education_tables(doc: LayoutDocument) -> list[LayoutTable]:
    out = []
    for t in doc.tables:
        hdr = ' '.join(t.headers).lower()
        if re.search(r'(?i)\b(?:degree|qualification|institution|university|college|cgpa|percentage|year)\b', hdr):
            if len([h for h in t.headers if h]) >= 2:
                out.append(t)
    return out
