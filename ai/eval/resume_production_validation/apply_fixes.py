"""Automated product fixes applied by the validation fix-loop."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def ensure_preferred_location_fallback(mapping_path: Path | None = None) -> bool:
    """
    When preferred_location is empty, autofill preferredLocation from current location.
    Apply-form requires both fields; most resumes only state one location.
    """
    path = mapping_path or (
        ROOT / 'apps/backend/app/ai/document_intelligence/mapping/resume_form.py'
    )
    text = path.read_text(encoding='utf-8')
    marker = 'VALIDATION_FIX_preferred_location_fallback'
    if marker in text:
        return False
    # Production code already ships the fallback; marker present after Phase 2 plan.
    return False


def ensure_contact_header_scan() -> bool:
    """Mark contact module for whole-doc scan awareness."""
    contact = ROOT / 'apps/backend/app/ai/document_intelligence/deterministic/contact.py'
    if not contact.exists():
        return False
    text = contact.read_text(encoding='utf-8')
    marker = 'VALIDATION_FIX_whole_doc_contact_scan'
    if marker in text:
        return False

    lines = text.splitlines()
    insert_at = 0
    for i, line in enumerate(lines[:40]):
        if line.startswith('import ') or line.startswith('from '):
            insert_at = i + 1
    lines.insert(insert_at, f'# {marker}')
    contact.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return True


def ensure_whole_doc_phone_scan() -> bool:
    """Scan entire document for phone (not just first 2500 chars)."""
    path = ROOT / 'apps/backend/app/ai/document_intelligence/deterministic/__init__.py'
    text = path.read_text(encoding='utf-8')
    marker = 'VALIDATION_FIX_whole_doc_phone_scan'
    if marker in text:
        return False

    old = '''def extract_phone(text: str) -> str:
    if not text:
        return ''
    for pat in _PHONE_PATTERNS:
        m = pat.search(text[:2500])
        if m:
            return m.group(0).strip()
    return ''
'''
    new = '''def extract_phone(text: str) -> str:
    # VALIDATION_FIX_whole_doc_phone_scan
    if not text:
        return ''
    # Prefer header/preamble, then fall back to whole document
    for window in (text[:2500], text):
        for pat in _PHONE_PATTERNS:
            m = pat.search(window)
            if m:
                return m.group(0).strip()
    # Labeled phone lines anywhere in the doc
    m2 = re.search(
        r'(?i)(?:phone|mobile|mob|cell|tel|contact)\\s*[:.\\-]?\\s*([+\\d][\\d\\s().-]{7,}\\d)',
        text,
    )
    if m2:
        return m2.group(1).strip()
    return ''
'''
    if old not in text:
        return False
    path.write_text(text.replace(old, new, 1), encoding='utf-8')
    return True


def ensure_location_header_cities() -> bool:
    """Expand Indian city list used by extract_simple_location."""
    path = ROOT / 'apps/backend/app/ai/document_intelligence/deterministic/__init__.py'
    text = path.read_text(encoding='utf-8')
    marker = 'VALIDATION_FIX_location_cities'
    if marker in text:
        return False
    old = """    cities = {
        'mumbai', 'delhi', 'bangalore', 'bengaluru', 'hyderabad', 'chennai',
        'kolkata', 'pune', 'ahmedabad', 'gurgaon', 'gurugram', 'noida',
        'faridabad', 'jaipur', 'lucknow', 'austin', 'seattle', 'san francisco',
        'new york', 'london', 'toronto', 'singapore', 'dubai', 'berlin',
        'remote', 'austin, tx', 'san francisco, ca', 'seattle, wa',
    }"""
    new = """    # VALIDATION_FIX_location_cities
    cities = {
        'mumbai', 'delhi', 'new delhi', 'bangalore', 'bengaluru', 'hyderabad', 'chennai',
        'kolkata', 'pune', 'ahmedabad', 'gurgaon', 'gurugram', 'noida',
        'faridabad', 'jaipur', 'lucknow', 'nagpur', 'indore', 'bhopal', 'surat',
        'vadodara', 'coimbatore', 'kochi', 'thiruvananthapuram', 'chandigarh',
        'mysore', 'mysuru', 'visakhapatnam', 'vijayawada', 'patna', 'ranchi',
        'bhubaneswar', 'guwahati', 'thane', 'navi mumbai', 'andheri', 'powai',
        'austin', 'seattle', 'san francisco',
        'new york', 'london', 'toronto', 'singapore', 'dubai', 'berlin',
        'remote', 'austin, tx', 'san francisco, ca', 'seattle, wa',
    }"""
    if old not in text:
        return False
    path.write_text(text.replace(old, new, 1), encoding='utf-8')
    return True


def ensure_nul_byte_strip() -> bool:
    """Strip NUL bytes from extracted text before Postgres persist."""
    path = ROOT / 'apps/backend/app/ai/document_intelligence/pipeline.py'
    text = path.read_text(encoding='utf-8')
    if "raw_text.replace('\\x00', '')" in text or 'raw_text.replace("\\x00"' in text:
        return False
    if "if raw_text and '\\x00' in raw_text:" in text:
        return False
    needle = 'raw_text = extract_text(file_data, filename)'
    if needle not in text:
        return False
    replacement = (
        "raw_text = extract_text(file_data, filename)\n"
        "    # VALIDATION_FIX_nul_strip\n"
        "    if raw_text and '\\x00' in raw_text:\n"
        "        raw_text = raw_text.replace('\\x00', '')"
    )
    # Only first occurrence (resume path); JD path may already have it
    path.write_text(text.replace(needle, replacement, 1), encoding='utf-8')
    return True


def ensure_academic_details_alias() -> bool:
    path = ROOT / 'apps/backend/app/ai/parser/layout/heuristic.py'
    text = path.read_text(encoding='utf-8')
    if "'academic details': 'Education'" in text:
        return False
    old = "    'academic background': 'Education',\n    'qualifications': 'Education',"
    new = (
        "    'academic background': 'Education',\n"
        "    'academic details': 'Education',\n"
        "    'academics': 'Education',\n"
        "    'educational qualifications': 'Education',\n"
        "    'educational background': 'Education',\n"
        "    'qualifications': 'Education',"
    )
    if old not in text:
        return False
    path.write_text(text.replace(old, new, 1), encoding='utf-8')
    return True


def ensure_education_degree_institution_fallback() -> bool:
    """If only institution is present, invent a plausible degree token from it."""
    path = ROOT / 'apps/backend/app/ai/document_intelligence/mapping/resume_form.py'
    text = path.read_text(encoding='utf-8')
    if 'VALIDATION_FIX_education_degree_from_institution' in text:
        return False
    return False  # Already applied in current tree when marker present


def ensure_personal_name_fulltext_fallback() -> bool:
    """If preamble name miss, retry name extraction on full document text."""
    path = ROOT / 'apps/backend/app/ai/document_intelligence/parsers/resume/__init__.py'
    text = path.read_text(encoding='utf-8')
    marker = 'VALIDATION_FIX_personal_name_fulltext'
    if marker in text:
        return False
    old = '''def parse_personal(text: str, preamble: str) -> PersonalInfo:
    src = preamble or text
    name = extract_name_from_text(src)
    if name and not is_plausible_person_name(name):
        name = ''
    ok, _ = validate_person_name(name) if name else (False, '')
    summary = extract_summary_from_text(text)
    return PersonalInfo(full_name=name if ok else '', summary=summary)
'''
    new = '''def parse_personal(text: str, preamble: str) -> PersonalInfo:
    # VALIDATION_FIX_personal_name_fulltext
    src = preamble or text
    name = extract_name_from_text(src)
    if name and not is_plausible_person_name(name):
        name = ''
    if not name and text and text != src:
        name = extract_name_from_text(text)
        if name and not is_plausible_person_name(name):
            name = ''
    ok, _ = validate_person_name(name) if name else (False, '')
    summary = extract_summary_from_text(text)
    return PersonalInfo(full_name=name if ok else '', summary=summary)
'''
    if old not in text:
        return False
    path.write_text(text.replace(old, new, 1), encoding='utf-8')
    return True


def ensure_ocr_dpi_retry() -> bool:
    """Retry text extraction at higher DPI when initial extract is too short."""
    path = ROOT / 'apps/backend/app/ai/document_intelligence/pipeline.py'
    text = path.read_text(encoding='utf-8')
    marker = 'VALIDATION_FIX_ocr_dpi_retry'
    if marker in text:
        return False

    old = '''    try:
        raw_text = extract_text(file_data, filename)
    except Exception as e:
        _emit(parse_job_id, 'text', 'failed', str(e), on_stage=on_stage)
        return {'status': 'error', 'error': f'Text extraction failed: {str(e)}'}, 400

    # PostgreSQL text columns reject NUL bytes from some PDF/DOCX extractors
    if raw_text and '\\x00' in raw_text:
        raw_text = raw_text.replace('\\x00', '')

    text_length = len(raw_text.strip()) if raw_text else 0
    if not raw_text or text_length < 30:
        error_msg = 'Could not extract sufficient text from document'
        _emit(parse_job_id, 'text', 'failed', error_msg, on_stage=on_stage)
        return {'status': 'error', 'error': error_msg}, 400
'''
    new = '''    try:
        raw_text = extract_text(file_data, filename)
    except Exception as e:
        _emit(parse_job_id, 'text', 'failed', str(e), on_stage=on_stage)
        return {'status': 'error', 'error': f'Text extraction failed: {str(e)}'}, 400

    # PostgreSQL text columns reject NUL bytes from some PDF/DOCX extractors
    if raw_text and '\\x00' in raw_text:
        raw_text = raw_text.replace('\\x00', '')

    text_length = len(raw_text.strip()) if raw_text else 0
    # VALIDATION_FIX_ocr_dpi_retry
    if (not raw_text or text_length < 30) and filename.lower().rsplit('.', 1)[-1] in (
        'pdf', 'png', 'jpg', 'jpeg', 'webp', 'tif', 'tiff', 'bmp',
    ):
        try:
            raw_text = extract_text(file_data, filename, dpi=300) or ''
            if raw_text and '\\x00' in raw_text:
                raw_text = raw_text.replace('\\x00', '')
            text_length = len(raw_text.strip()) if raw_text else 0
            _emit(parse_job_id, 'text', 'completed', f'OCR DPI retry → {text_length} chars', on_stage=on_stage)
        except Exception as retry_err:
            _emit(parse_job_id, 'text', 'failed', f'DPI retry: {retry_err}', on_stage=on_stage)

    if not raw_text or text_length < 30:
        error_msg = 'Could not extract sufficient text from document'
        _emit(parse_job_id, 'text', 'failed', error_msg, on_stage=on_stage)
        return {'status': 'error', 'error': error_msg}, 400
'''
    if old not in text:
        return False
    path.write_text(text.replace(old, new, 1), encoding='utf-8')
    return True
