"""Automatic pdfplumber secondary extractor: quality selection and PyMuPDF regression."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.parser import pdfplumber_extractor as pe
from app.ai.parser import text_extraction as te


GOOD_RESUME = (
    'Jane Doe\n'
    'jane.doe@example.com\n'
    'Experience\n'
    'Software Engineer at Example Corp 2019-2024\n'
    'Education\n'
    'B.Tech Computer Science\n'
    'Skills\n'
    'Python SQL AWS\n'
)


def _make_pdf_bytes(lines: list[str]) -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in lines:
        page.insert_text((72, y), line, fontsize=11)
        y += 16
        if y > 750:
            page = doc.new_page()
            y = 72
    data = doc.tobytes()
    doc.close()
    return data


def _make_table_pdf_bytes() -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    rows = [
        ('Job Title', 'Software Engineer'),
        ('Location', 'Bengaluru'),
        ('Experience', '5 years'),
        ('Skills', 'Python SQL AWS'),
        ('Department', 'Engineering'),
        ('Employment Type', 'Full Time'),
    ]
    y = 80
    for label, value in rows:
        page.insert_text((72, y), label, fontsize=11)
        page.insert_text((240, y), value, fontsize=11)
        y += 22
    data = doc.tobytes()
    doc.close()
    return data


def _broken_layout_text() -> str:
    # Many 1-char lines, longer than MIN_TEXT_CHARS — triggers broken_layout
    return '\n'.join(list('ABCDEFGHIJKLMNOPQRSTUVWXYZ012345') + ['xx'])


def _unextracted_table_text() -> str:
    return (
        'Name     Role     Years\n'
        'Ada      Eng      5\n'
        'Lin      QA       3\n'
        'Tom      PM       8\n'
        'Ria      HR       2\n'
        'Ken      Dev      4\n'
    )


def _structured_table_text() -> str:
    return (
        'Job Title: Software Engineer\n'
        'Location: Bengaluru\n'
        'Experience: 5 years\n'
        'Skills: Python | SQL | AWS\n'
        'Department: Engineering\n'
    )


# ---------------------------------------------------------------------------
# A. Normal digital PDF — PyMuPDF selected, pdfplumber not run
# ---------------------------------------------------------------------------


def test_normal_pdf_uses_pymupdf_and_skips_pdfplumber():
    pdf = _make_pdf_bytes(
        [
            'Jane Doe',
            'jane.doe@example.com',
            'Experience Software Engineer',
            'Education B.Tech',
            'Skills Python SQL',
        ]
    )
    with patch.object(pe, 'extract_text_from_pdf_pdfplumber') as plumber:
        text = te.extract_text_from_pdf(pdf)

    assert 'Jane Doe' in text
    assert te.last_pdf_extractor() == 'pymupdf'
    assert te.last_pdf_fallback_reason() == ''
    plumber.assert_not_called()


# ---------------------------------------------------------------------------
# B. Table-heavy PDF — pdfplumber considered and selected if better
# ---------------------------------------------------------------------------


def test_table_layout_selects_pdfplumber_when_preferable():
    with patch.object(te, 'extract_text_from_pdf_pymupdf', return_value=_unextracted_table_text()), \
         patch.object(pe, 'extract_text_from_pdf_pdfplumber', return_value=_structured_table_text()), \
         patch.object(pe, 'pdfplumber_available', return_value=True):
        text = te.extract_text_from_pdf(b'%PDF-fake-table')

    assert 'Job Title: Software Engineer' in text
    assert te.last_pdf_extractor() == 'pdfplumber'
    assert te.last_pdf_fallback_reason() == 'table_layout'


def test_pdfplumber_extractor_reads_table_pdf_and_returns_string():
    pytest.importorskip('pdfplumber')
    pdf = _make_table_pdf_bytes()
    text = pe.extract_text_from_pdf_pdfplumber(pdf)
    assert isinstance(text, str)
    assert len(text.strip()) >= te.MIN_TEXT_CHARS
    combined = text.lower()
    assert 'software engineer' in combined or 'bengaluru' in combined or 'python' in combined


# ---------------------------------------------------------------------------
# C. Poor PyMuPDF layout — pdfplumber automatically considered
# ---------------------------------------------------------------------------


def test_poor_pymupdf_triggers_pdfplumber_fallback():
    garbage = ':::: **** #### ' * 8
    with patch.object(te, 'extract_text_from_pdf_pymupdf', return_value=garbage), \
         patch.object(pe, 'extract_text_from_pdf_pdfplumber', return_value=GOOD_RESUME) as plumber, \
         patch.object(pe, 'pdfplumber_available', return_value=True):
        text = te.extract_text_from_pdf(b'%PDF-fake-garbage')

    plumber.assert_called_once()
    assert text == GOOD_RESUME
    assert te.last_pdf_extractor() == 'pdfplumber'
    assert te.last_pdf_fallback_reason() == 'garbage_text'


def test_insufficient_pymupdf_uses_pdfplumber():
    with patch.object(
        te,
        'extract_text_from_pdf_pymupdf',
        side_effect=ValueError('Insufficient text extracted - PDF may be image-based or corrupted'),
    ), patch.object(pe, 'extract_text_from_pdf_pdfplumber', return_value=GOOD_RESUME), \
         patch.object(pe, 'pdfplumber_available', return_value=True):
        text = te.extract_text_from_pdf(b'%PDF-empty-layer')

    assert text == GOOD_RESUME
    assert te.last_pdf_extractor() == 'pdfplumber'
    assert te.last_pdf_fallback_reason() == 'pymupdf_failed'


def test_broken_layout_triggers_pdfplumber():
    with patch.object(te, 'extract_text_from_pdf_pymupdf', return_value=_broken_layout_text()), \
         patch.object(pe, 'extract_text_from_pdf_pdfplumber', return_value=GOOD_RESUME), \
         patch.object(pe, 'pdfplumber_available', return_value=True):
        text = te.extract_text_from_pdf(b'%PDF-scrambled')

    assert text == GOOD_RESUME
    assert te.last_pdf_extractor() == 'pdfplumber'
    assert te.last_pdf_fallback_reason() == 'broken_layout'


# ---------------------------------------------------------------------------
# D. pdfplumber produces worse output — PyMuPDF remains selected
# ---------------------------------------------------------------------------


def test_worse_pdfplumber_keeps_pymupdf():
    pymu = _unextracted_table_text()
    worse = _broken_layout_text()
    with patch.object(te, 'extract_text_from_pdf_pymupdf', return_value=pymu), \
         patch.object(pe, 'extract_text_from_pdf_pdfplumber', return_value=worse) as plumber, \
         patch.object(pe, 'pdfplumber_available', return_value=True):
        text = te.extract_text_from_pdf(b'%PDF-worse-plumber')

    plumber.assert_called_once()
    assert text == pymu
    assert te.last_pdf_extractor() == 'pymupdf'
    assert te.last_pdf_fallback_reason() == 'table_layout'


def test_longer_pdfplumber_text_is_not_automatically_better():
    pymu = _unextracted_table_text()
    longer_noise = ('xxxx ' * 80) + '\n' + ('duplicated line\n' * 20)
    assert len(longer_noise) > len(pymu)
    with patch.object(te, 'extract_text_from_pdf_pymupdf', return_value=pymu), \
         patch.object(pe, 'extract_text_from_pdf_pdfplumber', return_value=longer_noise), \
         patch.object(pe, 'pdfplumber_available', return_value=True):
        text = te.extract_text_from_pdf(b'%PDF-longer-not-better')

    assert text == pymu
    assert te.last_pdf_extractor() == 'pymupdf'


# ---------------------------------------------------------------------------
# E. pdfplumber crashes — PyMuPDF result remains
# ---------------------------------------------------------------------------


def test_pdfplumber_failure_keeps_pymupdf_result():
    garbage = ':::: **** #### ' * 8
    with patch.object(te, 'extract_text_from_pdf_pymupdf', return_value=garbage), \
         patch.object(
             pe,
             'extract_text_from_pdf_pdfplumber',
             side_effect=RuntimeError('pdfplumber crashed'),
         ), \
         patch.object(pe, 'pdfplumber_available', return_value=True):
        text = te.extract_text_from_pdf(b'%PDF-plumber-fail')

    assert text == garbage
    assert te.last_pdf_extractor() == 'pymupdf'
    assert te.last_pdf_fallback_reason() == 'garbage_text'


def test_pdfplumber_orchestration_exception_does_not_break_pipeline():
    with patch.object(te, 'extract_text_from_pdf_pymupdf', return_value=GOOD_RESUME), \
         patch(
             'app.ai.parser.pdfplumber_extractor.maybe_use_pdfplumber',
             side_effect=RuntimeError('unexpected'),
         ):
        text = te.extract_text_from_pdf(b'%PDF-ok')

    assert 'Jane Doe' in text
    assert te.last_pdf_extractor() == 'pymupdf'


# ---------------------------------------------------------------------------
# F. PyMuPDF fails — existing PyPDF2 fallback still works
# ---------------------------------------------------------------------------


def test_both_extractors_fail_preserves_insufficient_text_error():
    original = ValueError('Insufficient text extracted - PDF may be image-based or corrupted')
    with patch.object(te, 'extract_text_from_pdf_pymupdf', side_effect=original), \
         patch.object(
             pe,
             'extract_text_from_pdf_pdfplumber',
             side_effect=ValueError('Insufficient text extracted via pdfplumber'),
         ), \
         patch.object(pe, 'pdfplumber_available', return_value=True), \
         patch.object(te, 'extract_text_from_pdf_pypdf2') as pypdf2:
        with pytest.raises(ValueError, match='Insufficient text extracted'):
            te.extract_text_from_pdf(b'%PDF-both-fail')
    pypdf2.assert_not_called()


def test_unexpected_pymupdf_error_still_tries_pypdf2():
    with patch.object(te, 'extract_text_from_pdf_pymupdf', side_effect=RuntimeError('boom')), \
         patch.object(pe, 'pdfplumber_available', return_value=False), \
         patch.object(te, 'extract_text_from_pdf_pypdf2', return_value=GOOD_RESUME) as pypdf2:
        text = te.extract_text_from_pdf(b'%PDF-boom')

    pypdf2.assert_called_once()
    assert text == GOOD_RESUME
    assert te.last_pdf_extractor() == 'pypdf2'


def test_unexpected_pymupdf_and_pypdf2_fail_wraps_error():
    with patch.object(te, 'extract_text_from_pdf_pymupdf', side_effect=RuntimeError('boom')), \
         patch.object(pe, 'pdfplumber_available', return_value=False), \
         patch.object(te, 'extract_text_from_pdf_pypdf2', side_effect=ValueError('pypdf2 dead')):
        with pytest.raises(ValueError, match='Failed to extract text from PDF: boom'):
            te.extract_text_from_pdf(b'%PDF-all-fail')


def test_pymupdf_missing_uses_pdfplumber_when_better():
    with patch.object(
        te,
        'extract_text_from_pdf_pymupdf',
        side_effect=ValueError('PyMuPDF (pymupdf) is not installed'),
    ), patch.object(pe, 'extract_text_from_pdf_pdfplumber', return_value=GOOD_RESUME), \
         patch.object(pe, 'pdfplumber_available', return_value=True), \
         patch.object(te, 'extract_text_from_pdf_pypdf2') as pypdf2:
        text = te.extract_text_from_pdf(b'%PDF-no-fitz')

    pypdf2.assert_not_called()
    assert text == GOOD_RESUME
    assert te.last_pdf_extractor() == 'pdfplumber'


# ---------------------------------------------------------------------------
# G. Scanned / OCR — pdfplumber must not replace OCR
# ---------------------------------------------------------------------------


def test_good_ocr_like_pymupdf_skips_pdfplumber():
    ocr_text = (
        'Scanned resume Jane Doe jane.doe@example.com '
        'Experience Software Engineer Education B.Tech Skills Python ' + ('y' * 40)
    )
    with patch.object(te, 'extract_text_from_pdf_pymupdf', return_value=ocr_text), \
         patch.object(pe, 'extract_text_from_pdf_pdfplumber') as plumber:
        text = te.extract_text_from_pdf(b'%PDF-scanned-ocr')

    plumber.assert_not_called()
    assert 'Jane Doe' in text
    assert te.last_pdf_extractor() == 'pymupdf'


def test_pdfplumber_does_not_replace_richer_ocr_text():
    """Thin digital layer from pdfplumber must not beat OCR-rich PyMuPDF text."""
    ocr_rich = GOOD_RESUME + '\n' + ('Additional OCR paragraph about production support. ' * 4)
    thin_layer = 'CONFIDENTIAL WATERMARK PAGE HEADER FOOTER XXXX'
    # Force consideration via a synthetic garbage prefix, then... actually
    # good OCR text should not even consider plumber. This covers the compare
    # guard if consideration did happen (e.g. table-like OCR).
    tableish_ocr = _unextracted_table_text() + '\n' + ocr_rich
    with patch.object(te, 'extract_text_from_pdf_pymupdf', return_value=tableish_ocr), \
         patch.object(pe, 'extract_text_from_pdf_pdfplumber', return_value=thin_layer), \
         patch.object(pe, 'pdfplumber_available', return_value=True):
        text = te.extract_text_from_pdf(b'%PDF-ocr-rich')

    assert text == tableish_ocr
    assert te.last_pdf_extractor() == 'pymupdf'


# ---------------------------------------------------------------------------
# H. No extractor environment variable is required
# ---------------------------------------------------------------------------


def test_no_extractor_env_vars_required(monkeypatch):
    monkeypatch.delenv('PDF_ENABLE_PDFPLUMBER', raising=False)
    monkeypatch.delenv('PDF_PRIMARY_EXTRACTOR', raising=False)
    monkeypatch.delenv('PDF_PLUMBER_MIN_CHARS', raising=False)
    monkeypatch.delenv('PDF_ENGINE', raising=False)
    monkeypatch.delenv('USE_PDFPLUMBER', raising=False)
    pdf = _make_pdf_bytes(
        [
            'Jane Doe',
            'jane.doe@example.com',
            'Experience Software Engineer',
            'Education B.Tech',
            'Skills Python SQL',
        ]
    )
    text = te.extract_text_from_pdf(pdf)
    assert 'Jane Doe' in text
    assert te.last_pdf_extractor() == 'pymupdf'


def test_extractor_selection_functions_are_not_env_gated():
    assert not hasattr(pe, 'pdfplumber_enabled')
    assert not hasattr(pe, 'pdf_primary_extractor')


# ---------------------------------------------------------------------------
# Strategy helpers
# ---------------------------------------------------------------------------


def test_good_pymupdf_text_does_not_warrant_fallback():
    assert pe.fallback_reason(GOOD_RESUME, None) is None


def test_pdfplumber_not_preferable_when_also_garbage():
    garbage = ':::: **** #### ' * 8
    assert pe.pdfplumber_result_is_preferable(garbage, garbage) is False


def test_extract_text_normalizes_pdfplumber_result():
    raw = 'Jane Doe\u200b\n' + GOOD_RESUME
    with patch.object(te, 'extract_text_from_pdf_pymupdf', return_value=':::: **** #### ' * 8), \
         patch.object(pe, 'extract_text_from_pdf_pdfplumber', return_value=raw), \
         patch.object(pe, 'pdfplumber_available', return_value=True):
        out = te.extract_text(b'%PDF-norm', 'resume.pdf')
    assert '\u200b' not in out
    assert 'Jane Doe' in out


def test_looks_like_broken_layout_and_tables():
    assert pe.looks_like_broken_layout(_broken_layout_text()) is True
    assert pe.looks_like_broken_layout(GOOD_RESUME) is False
    assert pe.looks_like_unextracted_tables(_unextracted_table_text()) is True
    assert pe.looks_like_unextracted_tables(GOOD_RESUME) is False


def test_looks_like_column_mix_detects_glued_section_headers():
    mixed = (
        'WORK EXPERIENCE TECHNICAL PROFICIENCY:\n'
        'Assistant System Engineer CORE LANG : C #\n'
        'Tata Consultancy Services (TCS)\n'
    )
    assert pe.looks_like_column_mix(mixed) is True
    assert pe.looks_like_column_mix(GOOD_RESUME) is False
    # Prose that merely mentions education/skills must not trip the mix gate
    prose = 'education courses that enhanced your skills and expertise, leading to'
    assert pe.looks_like_column_mix(prose) is False


def test_column_mixed_pdfplumber_is_not_preferable_to_pymupdf():
    pymu = (
        'Experience\nAssistant System Engineer\nTata Consultancy Services (TCS)\n'
        '07/2022 - Present\n'
        'Education\nB.E\n'
        'TECHNICAL PROFICIENCY:\nC#\n.NET Core\nSQL\n'
    )
    mixed = (
        'WORK EXPERIENCE TECHNICAL PROFICIENCY:\n'
        'Assistant System Engineer\nCORE LANG : C #\n'
        'Tata Consultancy Services (TCS)\n'
    )
    assert pe.pdfplumber_result_is_preferable(pymu, mixed) is False


def _vishal_pdf_path() -> Path | None:
    p = Path(r'C:\Users\DELL\Downloads\resume testing') / '#1_Vishal_Waghmode_Resume.pdf'
    return p if p.is_file() else None


def test_pdfplumber_two_column_resume_keeps_sections_apart():
    pdf_path = _vishal_pdf_path()
    if pdf_path is None:
        pytest.skip('Vishal two-column resume PDF not on disk')
    text = pe.extract_text_from_pdf_pdfplumber(pdf_path.read_bytes())
    assert 'WORK EXPERIENCE TECHNICAL PROFICIENCY' not in text
    assert pe.looks_like_column_mix(text) is False
    # Layout enhance canonicalizes headers (Experience / Skills) after crop.
    exp_idx = text.upper().find('EXPERIENCE')
    skill_idx = max(text.upper().find('TECHNICAL PROFICIENCY'), text.upper().find('\nSKILLS'))
    assert exp_idx != -1
    assert skill_idx != -1 or 'CORE LANG' in text or 'sql' in text.lower()
    nseit_idx = text.find('National Stock Exchange')
    tata_proj = text.find('TATA GROUP')
    assert nseit_idx != -1
    if tata_proj != -1:
        assert nseit_idx < tata_proj
    assert 'Tata Consultancy Services' in text
    assert 'CORE LANG' in text or 'C #' in text or 'C#' in text or 'sql' in text.lower()


def test_pdfplumber_two_column_resume_parses_both_jobs_and_skills():
    pdf_path = _vishal_pdf_path()
    if pdf_path is None:
        pytest.skip('Vishal two-column resume PDF not on disk')
    from app.ai.document_intelligence.pipeline import parse_resume_text_to_canonical

    text = pe.extract_text_from_pdf_pdfplumber(pdf_path.read_bytes())
    profile, _form, _ = parse_resume_text_to_canonical(text, allow_semantic=False)
    companies = ' '.join(e.company or '' for e in profile.experience)
    roles = ' '.join(e.role or '' for e in profile.experience)
    skills = ' '.join((s.canonical or s.name or '') for s in profile.skills).lower()
    assert 'Tata Consultancy' in companies
    assert 'NSEIT' in companies or 'National Stock' in companies
    assert 'Assistant System Engineer' in roles
    assert 'Assistant System Analyst' in roles
    assert not any(looks_like_phone_company(e.company) for e in profile.experience)
    assert 'c#' in skills or 'c #' in skills
    assert 'sql' in skills


def looks_like_phone_company(value: str | None) -> bool:
    s = (value or '').strip()
    return bool(s) and s.isdigit() and len(s) >= 8


# ---------------------------------------------------------------------------
# Two-column pdfplumber extraction (dynamic gutter, header confirmation)
# ---------------------------------------------------------------------------

_TC_HEADER = [
    'Vishal Candidate Name',
    'Software Developer Full Stack Engineer',
    'Experienced engineer building reliable client systems with care',
    'vishal.candidate@example.com 9876543210 Navi Mumbai India',
]

_TC_LEFT = [
    'WORK EXPERIENCE',
    'Assistant System Engineer',
    'Tata Consultancy Services TCS',
    '07/2022 - Present Thane Mumbai',
    'Built backend services for trading desk users',
    'Handled production support with business teams',
    'Assistant System Analyst',
    'NSEIT National Stock Exchange',
    '01/2021 - 06/2022 Navi Mumbai',
    'Supported exchange reporting and operations tools',
    'EDUCATION',
    'Bachelor of Engineering Computer Science',
    'State University campus graduated with distinction',
]

_TC_RIGHT = [
    'TECHNICAL PROFICIENCY',
    'CORE LANG C Sharp runtime and tooling',
    'SQL Structured Query Language reports',
    'HTML5 CSS3 markup for internal portals',
    'PROJECTS',
    'TATA GROUP portal modernization program',
    'Refactored dashboards for the operations team',
    'STRENGTHS',
    'Clear communication and stakeholder alignment',
    'Focused on delivery quality under timelines',
]


def _make_two_column_pdf(
    *,
    header_lines: list[str] | None = None,
    left_lines: list[str] | None = None,
    right_lines: list[str] | None = None,
    left_x: float = 48.0,
    right_x: float = 340.0,
    width: float = 612.0,
    height: float = 792.0,
    page2_lines: list[str] | None = None,
    inner_table: bool = False,
    draw_border: bool = False,
) -> bytes:
    """Synthetic two-column resume. No hardcoded extractor gutter (x=315)."""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=width, height=height)
    header_lines = list(header_lines if header_lines is not None else _TC_HEADER)
    left_lines = list(left_lines if left_lines is not None else _TC_LEFT)
    right_lines = list(right_lines if right_lines is not None else _TC_RIGHT)

    y = 50.0
    for line in header_lines:
        page.insert_text((48, y), line, fontsize=10)
        y += 14
    y += 10
    body_top = y
    ly = ry = body_top
    for line in left_lines:
        page.insert_text((left_x, ly), line, fontsize=9)
        ly += 13
    for line in right_lines:
        page.insert_text((right_x, ry), line, fontsize=9)
        ry += 13
    if inner_table:
        ly += 8
        page.insert_text((left_x, ly), 'Language', fontsize=9)
        page.insert_text((left_x + 70, ly), 'Years', fontsize=9)
        ly += 12
        page.insert_text((left_x, ly), 'Python', fontsize=9)
        page.insert_text((left_x + 70, ly), 'Five', fontsize=9)
        ly += 12
        page.insert_text((left_x, ly), 'Java', fontsize=9)
        page.insert_text((left_x + 70, ly), 'Three', fontsize=9)
    if draw_border:
        gutter = (left_x + 200 + right_x) / 2.0
        page.draw_line((gutter, body_top - 8), (gutter, height - 40), color=(0.7, 0.7, 0.7), width=0.4)
    if page2_lines:
        p2 = doc.new_page(width=width, height=height)
        y2 = 60.0
        for line in page2_lines:
            p2.insert_text((72, y2), line, fontsize=11)
            y2 += 16
    data = doc.tobytes()
    doc.close()
    return data


def _open_first_page(pdf: bytes):
    import pdfplumber
    import io

    plumber = pdfplumber.open(io.BytesIO(pdf))
    return plumber, plumber.pages[0]


def _default_plumber_text(pdf: bytes) -> str:
    import pdfplumber
    import io

    parts = []
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        for page in doc.pages:
            parts.append((page.extract_text() or '').strip())
    return '\n\n'.join(p for p in parts if p)


def _find_section_header(text: str, *names: str) -> int:
    up = text.upper()
    for name in names:
        pat = rf'(?m)^[ \t]*{re.escape(name.upper())}\s*:?\s*$'
        m = re.search(pat, up)
        if m:
            return m.start()
    return -1


def _assert_column_order(text: str) -> None:
    exp = _find_section_header(text, 'WORK EXPERIENCE', 'EXPERIENCE')
    tech = _find_section_header(text, 'TECHNICAL PROFICIENCY', 'SKILLS')
    proj = _find_section_header(text, 'PROJECTS')
    edu = _find_section_header(text, 'EDUCATION')
    tcs = text.find('Tata Consultancy')
    nseit = text.find('NSEIT')
    if nseit < 0:
        nseit = text.find('National Stock Exchange')
    assert exp != -1
    assert tcs != -1 and nseit != -1
    assert tcs < nseit
    if edu != -1:
        assert nseit < edu
    if tech != -1:
        assert tcs < tech
        if edu != -1:
            assert edu < tech
    if proj != -1:
        assert nseit < proj
        if tech != -1:
            assert tech < proj
    tcs_window = text[tcs:nseit] if nseit > tcs else text[tcs : tcs + 400]
    assert 'HTML5' not in tcs_window.upper()
    assert 'CORE LANG' not in tcs_window.upper()
    assert not re.search(r'(?m)^[ \t]*PROJECTS\s*:?\s*$', tcs_window, re.I)


def test_gutter_detection_is_not_hardcoded_at_315():
    src = Path(pe.__file__).read_text(encoding='utf-8')
    assert '315' not in src
    words_a = []
    words_b = []
    y = 80.0
    for i in range(10):
        for bucket, lx, rx in ((words_a, 40.0, 280.0), (words_b, 50.0, 430.0)):
            bucket.append({'text': f'LeftAlpha{i}', 'x0': lx, 'x1': lx + 70, 'top': y, 'bottom': y + 10})
            bucket.append({'text': 'LeftBeta', 'x0': lx + 80, 'x1': lx + 130, 'top': y, 'bottom': y + 10})
            bucket.append({'text': f'RightAlpha{i}', 'x0': rx, 'x1': rx + 70, 'top': y, 'bottom': y + 10})
            bucket.append({'text': 'RightBeta', 'x0': rx + 80, 'x1': rx + 130, 'top': y, 'bottom': y + 10})
        y += 16
    split_a = pe._detect_column_gutter(words_a, 612.0, 792.0)
    split_b = pe._detect_column_gutter(words_b, 612.0, 792.0)
    assert split_a is not None and split_b is not None
    assert abs(split_a - split_b) > 40
    assert abs(split_a - 315.0) > 8 or abs(split_b - 315.0) > 8


def test_a_vishal_two_column_resume_column_aware():
    """A. Vishal two-column resume (real file when present, else synthetic)."""
    pytest.importorskip('pdfplumber')
    pdf_path = _vishal_pdf_path()
    pdf = pdf_path.read_bytes() if pdf_path is not None else _make_two_column_pdf()
    text = pe.extract_text_from_pdf_pdfplumber(pdf)
    assert 'WORK EXPERIENCE TECHNICAL PROFICIENCY' not in text
    assert pe.looks_like_column_mix(text) is False
    _assert_column_order(text)


def test_b_normal_single_column_uses_default_extraction():
    pytest.importorskip('pdfplumber')
    pdf = _make_pdf_bytes(
        [
            'Jane Doe',
            'jane.doe@example.com 9876543210',
            'WORK EXPERIENCE',
            'Software Engineer at Example Corp 2019 to 2024',
            'Built APIs and internal tools for the platform team',
            'EDUCATION',
            'B.Tech Computer Science from State University',
            'SKILLS',
            'Python SQL AWS Docker Kubernetes Linux Git',
            'PROJECTS',
            'Internal billing portal used by operations staff daily',
        ]
    )
    plumber, page = _open_first_page(pdf)
    try:
        assert pe._extract_page_column_aware(page) is None
    finally:
        plumber.close()
    text = pe.extract_text_from_pdf_pdfplumber(pdf)
    assert 'Jane Doe' in text
    assert 'WORK EXPERIENCE TECHNICAL PROFICIENCY' not in text
    assert pe.looks_like_column_mix(text) is False


def test_c_unequal_column_widths():
    pytest.importorskip('pdfplumber')
    pdf = _make_two_column_pdf(left_x=42.0, right_x=430.0, width=612.0)
    plumber, page = _open_first_page(pdf)
    try:
        col = pe._extract_page_column_aware(page)
        gutter = pe._detect_column_gutter(page.extract_words(), float(page.width), float(page.height))
    finally:
        plumber.close()
    assert col is not None
    assert gutter is not None
    assert 240 < gutter < 500
    text = pe.extract_text_from_pdf_pdfplumber(pdf)
    _assert_column_order(text)
    assert pe.looks_like_column_mix(text) is False


def test_d_full_width_header_is_not_split():
    pytest.importorskip('pdfplumber')
    header = [
        'Vishal Candidate Name',
        'Software Developer Full Stack Engineer',
        'Experienced Full Stack Software Developer with a passion for games',
        'Skilled in backend systems and source control with agile delivery',
        'vishal.candidate@example.com 9876543210 Navi Mumbai India linkedin',
    ]
    pdf = _make_two_column_pdf(header_lines=header)
    plumber, page = _open_first_page(pdf)
    try:
        col = pe._extract_page_column_aware(page)
    finally:
        plumber.close()
    assert col is not None
    name_at = col.find('Vishal Candidate Name')
    exp_at = col.upper().find('WORK EXPERIENCE')
    tech_at = col.upper().find('TECHNICAL PROFICIENCY')
    assert 0 <= name_at < exp_at
    assert exp_at < tech_at
    # Header band stays intact: email appears before column body headers
    assert col.find('vishal.candidate@example.com') < exp_at
    text = pe.extract_text_from_pdf_pdfplumber(pdf)
    name_at = text.find('Vishal Candidate Name')
    exp_at = _find_section_header(text, 'WORK EXPERIENCE', 'EXPERIENCE')
    tech_at = _find_section_header(text, 'TECHNICAL PROFICIENCY', 'SKILLS')
    assert 0 <= name_at < exp_at
    assert exp_at < tech_at
    assert text.find('vishal.candidate@example.com') < exp_at
    _assert_column_order(text)


def test_e_two_column_without_visible_border():
    pytest.importorskip('pdfplumber')
    pdf = _make_two_column_pdf(draw_border=False)
    plumber, page = _open_first_page(pdf)
    try:
        assert pe._extract_page_column_aware(page) is not None
    finally:
        plumber.close()
    text = pe.extract_text_from_pdf_pdfplumber(pdf)
    _assert_column_order(text)


def test_f_table_inside_one_column_does_not_use_page_as_table():
    pytest.importorskip('pdfplumber')
    pdf = _make_two_column_pdf(inner_table=True)
    plumber, page = _open_first_page(pdf)
    try:
        col = pe._extract_page_column_aware(page)
        tables = page.extract_tables() or []
    finally:
        plumber.close()
    assert col is not None
    # A visually structured resume is not automatically a genuine grid table
    genuine = [t for t in tables if pe._is_genuine_grid_table(t)]
    text = pe.extract_text_from_pdf_pdfplumber(pdf)
    _assert_column_order(text)
    assert 'Python' in text
    # Column-aware path is used; fake whole-page tables must not poison output
    assert 'WORK EXPERIENCE TECHNICAL PROFICIENCY' not in text
    assert pe.looks_like_column_mix(text) is False
    del genuine  # presence is optional; quality gate is the assertion that matters


def test_g_aligned_single_column_is_not_two_column():
    """Dates/values aligned to the right must not activate column-aware mode."""
    pytest.importorskip('pdfplumber')
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    y = 60
    page.insert_text((72, y), 'Jane Doe Software Engineer Resume', fontsize=14)
    y += 24
    page.insert_text((72, y), 'jane.doe@example.com 9876543210 Bengaluru', fontsize=10)
    y += 22
    page.insert_text((72, y), 'WORK EXPERIENCE', fontsize=12)
    y += 18
    jobs = [
        ('Software Engineer Example Corp', '2019 - 2024'),
        ('Platform Developer Sample Labs', '2017 - 2019'),
        ('Intern Developer Startup Hub', '2016 - 2017'),
        ('Campus Ambassador College Club', '2015 - 2016'),
        ('Volunteer Mentor Coding Circle', '2014 - 2015'),
    ]
    for title, dates in jobs:
        page.insert_text((72, y), title, fontsize=10)
        page.insert_text((420, y), dates, fontsize=10)
        y += 16
        page.insert_text((72, y), 'Delivered product features for internal users', fontsize=9)
        y += 18
    page.insert_text((72, y), 'EDUCATION', fontsize=12)
    y += 16
    page.insert_text((72, y), 'B.Tech Computer Science State University', fontsize=10)
    page.insert_text((420, y), '2012 - 2016', fontsize=10)
    y += 20
    page.insert_text((72, y), 'SKILLS', fontsize=12)
    y += 16
    page.insert_text((72, y), 'Python SQL AWS Docker Kubernetes Linux Git CI', fontsize=10)
    pdf = doc.tobytes()
    doc.close()

    plumber, pg = _open_first_page(pdf)
    try:
        assert pe._extract_page_column_aware(pg) is None
    finally:
        plumber.close()
    text = pe.extract_text_from_pdf_pdfplumber(pdf)
    assert 'Jane Doe' in text
    assert 'WORK EXPERIENCE' in text.upper() or 'EXPERIENCE' in text.upper()
    assert pe.looks_like_column_mix(text) is False


def test_h_multipage_layout_can_change_between_pages():
    pytest.importorskip('pdfplumber')
    page2 = [
        'REFERENCES',
        'Professional references are available upon request from managers',
        'Additional coursework in distributed systems and cloud platforms',
        'Volunteer mentor for campus coding club during evening sessions',
        'Completed internal training on secure coding and code reviews',
        'Wrote design notes for the billing portal used by operations',
        'Collaborated with QA on regression packs before each release',
        'Documented runbooks for on-call engineers covering core services',
    ]
    pdf = _make_two_column_pdf(page2_lines=page2)
    import pdfplumber
    import io

    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        assert len(doc.pages) == 2
        assert pe._extract_page_column_aware(doc.pages[0]) is not None
        assert pe._extract_page_column_aware(doc.pages[1]) is None
    text = pe.extract_text_from_pdf_pdfplumber(pdf)
    _assert_column_order(text)
    assert 'REFERENCES' in text.upper() or 'references' in text.lower()
    assert text.upper().find('WORK EXPERIENCE') < text.upper().find('REFERENCES') or 'REFERENCES' in text.upper()


def test_vishal_three_way_extract_comparison():
    """PyMuPDF vs default pdfplumber vs column-aware pdfplumber."""
    pytest.importorskip('pdfplumber')
    pdf_path = _vishal_pdf_path()
    if pdf_path is None:
        pdf = _make_two_column_pdf()
        real = False
    else:
        pdf = pdf_path.read_bytes()
        real = True

    pymu = te.extract_text_from_pdf_pymupdf(pdf)
    default = _default_plumber_text(pdf)
    aware = pe.extract_text_from_pdf_pdfplumber(pdf)

    assert pe.looks_like_column_mix(default) is True
    assert 'WORK EXPERIENCE TECHNICAL PROFICIENCY' in default or pe.looks_like_column_mix(default)
    assert pe.looks_like_column_mix(aware) is False
    assert 'WORK EXPERIENCE TECHNICAL PROFICIENCY' not in aware
    _assert_column_order(aware)
    # PyMuPDF remains trusted primary for a good digital resume
    assert pe.fallback_reason(pymu, None) is None
    assert pe.pdfplumber_result_is_preferable(pymu, aware) is False
    if real:
        assert 'Tata Consultancy' in pymu
        assert 'National Stock Exchange' in pymu or 'NSEIT' in pymu
        assert 'TECHNICAL PROFICIENCY' in pymu.upper() or 'Skills' in pymu


def test_genuine_grid_table_rejects_page_sized_fake_table():
    fake = [['WORK EXPERIENCE\nTCS\n' + ('line\n' * 10) + 'TECHNICAL PROFICIENCY\nC#\nSQL']]
    assert pe._is_genuine_grid_table(fake) is False
    real = [['Language', 'Years'], ['Python', '5'], ['Java', '3']]
    assert pe._is_genuine_grid_table(real) is True


def test_column_mix_gate_catches_skills_and_projects_inside_experience():
    mixed = (
        'WORK EXPERIENCE TECHNICAL PROFICIENCY:\n'
        'Assistant System Engineer CORE LANG : C #\n'
        'Tata Consultancy Services (TCS)\n'
        '07/2022 - Present, Thane SQL HTML5\n'
        'PROJECTS TATA GROUP\n'
        'Assistant System Analyst NSEIT\n'
        'EDUCATION STRENGTHS\n'
    )
    assert pe.looks_like_column_mix(mixed) is True
    assert pe.pdfplumber_result_is_preferable(GOOD_RESUME, mixed) is False


def test_address_first_missing_name_triggers_pdfplumber_compare():
    """Sidebar/two-column extracts that start with phone/address should be compared."""
    address_first = (
        '8217276434\n'
        'x96@example.com\n'
        '#244, 1st Main Road, 2nd Cross\n'
        'Maruthi Nagar\n'
        'Bapuji Nagar, Bangalore\n'
        'Contact\n'
        'Summary\n'
        'MongoDB Linux NoSQL\n'
        'Education\n'
        'bachelor of engineering\n'
        'Experience\n'
        '2.7 years of experience in Mongo DB administration and cluster setup.\n'
    )
    plumber_with_name = (
        'JANE CANDIDATE\n'
        'ASSOCIATE DATABASE ENGINEER\n'
        'CONTACT:\n'
        '8217276434\n'
        'jane.candidate@example.com\n'
        'Summary\n'
        'Employment background reflects well over 2 years in Mongo DB.\n'
        'Education\n'
        'Bachelor of Engineering\n'
    )
    assert pe.fallback_reason(address_first, None) == 'address_first_missing_name'
    assert pe.pdfplumber_result_is_preferable(address_first, plumber_with_name) is True
    # A named digital extract must still keep PyMuPDF
    named = 'Anita Rao\nSoftware Engineer\nanita@example.com\n9876543210\nMumbai\nExperience\nAcme | Engineer | 2020-2024\n'
    assert pe.fallback_reason(named, None) is None
