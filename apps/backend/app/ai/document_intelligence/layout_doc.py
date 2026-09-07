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
