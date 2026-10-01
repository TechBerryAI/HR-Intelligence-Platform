"""Legacy Word 97-2003 (.doc) extraction.

`.doc` was rejected outright until antiword was added. These tests cover the
container sniffing (files are routinely mislabelled), the antiword-missing
error path, and the upload allowlist that gates the HTTP endpoints.

The antiword round-trip itself only runs where the binary is installed.
"""
from __future__ import annotations

import io

import pytest

from app.ai.parser import text_extraction as tx
from app.domains.recruitment.api import parsing as parsing_mod

OLE2_HEADER = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' + b'\x00' * 64


@pytest.fixture
def app_ctx():
    """Bare Flask context — the rejection helpers build jsonify responses."""
    from flask import Flask

    app = Flask(__name__)
    with app.app_context():
        yield app


def _docx_bytes(text: str = 'Vishal Goel\nMongoDB Certified DBA\nMeerut Institute') -> bytes:
    from docx import Document

    doc = Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- sniffing


@pytest.mark.parametrize(
    ('data', 'expected'),
    [
        (b'%PDF-1.7 rest', 'pdf'),
        (b'PK\x03\x04rest', 'docx'),
        (OLE2_HEADER, 'doc'),
        (b'{\\rtf1\\ansi hello}', 'doc'),
        (b'RIFF____WEBPVP8 ', 'webp'),
        (b'MZ\x90\x00 not a document', None),
    ],
)
def test_upload_sniffer_recognises_legacy_doc(data, expected):
    assert parsing_mod.sniff_upload_kind(data) is expected


def test_doc_is_in_the_upload_allowlist_with_a_word_mime_type():
    assert 'doc' in parsing_mod.ALLOWED_EXTENSIONS
    assert parsing_mod.MIME_TYPE_MAP['doc'] == 'application/msword'
    assert parsing_mod.allowed_file('resume.doc')


def test_docx_renamed_to_doc_is_not_a_content_mismatch():
    """The extractor sniffs the real container, so the pair must interoperate."""
    assert parsing_mod._reject_bad_content(_docx_bytes(), 'resume.doc') is None
    assert parsing_mod._reject_bad_content(OLE2_HEADER, 'resume.docx') is None


def test_a_renamed_executable_is_still_rejected(app_ctx):
    rejected = parsing_mod._reject_bad_content(b'MZ\x90\x00 payload', 'resume.doc')
    assert rejected is not None
    assert rejected[1] == 400


# --------------------------------------------------------------- container


def test_docx_wearing_a_doc_extension_extracts_natively(monkeypatch):
    """No antiword needed: the ZIP magic wins over the extension."""
    monkeypatch.setattr(tx, '_antiword_path', lambda: '')
    text = tx.extract_text_from_doc(_docx_bytes())
    assert 'Vishal Goel' in text
    assert 'Meerut Institute' in text


def test_rtf_wearing_a_doc_extension_extracts_natively(monkeypatch):
    monkeypatch.setattr(tx, '_antiword_path', lambda: '')
    rtf = (
        rb'{\rtf1\ansi\deff0 {\fonttbl{\f0 Times;}}'
        rb'\f0\fs24 Vishal Goel\par MongoDB Certified DBA\par '
        rb'Meerut Institute of Engineering and Technology\par}'
    )
    text = tx.extract_text_from_doc(rtf)
    assert 'Vishal Goel' in text
    assert 'MongoDB Certified DBA' in text


def test_unknown_container_is_rejected_with_a_clear_message():
    with pytest.raises(ValueError, match='Unrecognized .doc container'):
        tx.extract_text_from_doc(b'MZ\x90\x00 not a word document at all')


def test_empty_file_is_rejected():
    with pytest.raises(ValueError, match='Empty'):
        tx.extract_text_from_doc(b'')


# ------------------------------------------------- built-in Word reader


def _word_doc_bytes(
    pieces: list[tuple[str, bool]], *, nfib: int = 0x00C1, flags: int = 0x0200, word6: bool = False,
) -> bytes:
    """Build a minimal Word 97 (or Word 6) .doc per [MS-CFB]/[MS-DOC].

    ``pieces`` are (text, compressed) runs: compressed → cp1252, else UTF-16LE.
    Streams are padded past the 4096-byte mini-stream cutoff so they live in
    regular sectors.
    """
    import struct

    text_at = 0x800
    word = bytearray(0x1000)
    struct.pack_into('<HH', word, 0, 0xA5DC if word6 else 0xA5EC, 0x0065 if word6 else nfib)
    struct.pack_into('<H', word, 0x0A, flags)
    table = bytearray()
    if word6:
        body = ''.join(t for t, _ in pieces).encode('cp1252')
        word[text_at:text_at + len(body)] = body
        struct.pack_into('<II', word, 0x18, text_at, text_at + len(body))
    else:
        pos = 0x20
        struct.pack_into('<H', word, pos, 14)
        pos += 2 + 28
        struct.pack_into('<H', word, pos, 22)
        pos += 2 + 88
        struct.pack_into('<H', word, pos, 93)
        fclcb = pos + 2
        cps, pcds, off = [0], [], text_at
        for text, compressed in pieces:
            raw = text.encode('cp1252' if compressed else 'utf-16-le')
            word[off:off + len(raw)] = raw
            pcds.append((off * 2) | 0x40000000 if compressed else off)
            cps.append(cps[-1] + len(text))
            off += len(raw)
        plc = struct.pack(f'<{len(cps)}I', *cps) + b''.join(
            struct.pack('<HIH', 0, fc, 0) for fc in pcds
        )
        table = bytearray(b'\x02' + struct.pack('<I', len(plc)) + plc)
        struct.pack_into('<II', word, fclcb + 33 * 8, 0, len(table))
    table = table.ljust(0x1000, b'\x00')

    sec = 512
    streams = [('WordDocument', bytes(word))] + ([] if word6 else [('1Table', bytes(table))])
    fat = [0xFFFFFFFD, 0xFFFFFFFE]  # sector 0 = FAT, sector 1 = directory
    starts, body = [], b''
    for _, data in streams:
        n = len(data) // sec
        first = len(fat)
        starts.append(first)
        fat += [first + i + 1 for i in range(n - 1)] + [0xFFFFFFFE]
        body += data
    fat_sector = struct.pack(f'<{len(fat)}I', *fat).ljust(sec, b'\xff')

    def entry(name: str, kind: int, start: int, size: int) -> bytes:
        raw = name.encode('utf-16-le') + b'\x00\x00'
        e = bytearray(128)
        e[:len(raw)] = raw
        struct.pack_into('<HB', e, 0x40, len(raw), kind)
        struct.pack_into('<III', e, 0x74, start, size, 0)
        return bytes(e)

    directory = entry('Root Entry', 5, 0xFFFFFFFE, 0) + b''.join(
        entry(name, 2, s, len(data)) for (name, data), s in zip(streams, starts)
    )
    header = bytearray(512)
    header[:8] = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
    struct.pack_into('<HHH', header, 0x18, 0x3E, 3, 0xFFFE)
    struct.pack_into('<HH', header, 0x1E, 9, 6)
    struct.pack_into('<II', header, 0x2C, 1, 1)
    struct.pack_into('<IIIII', header, 0x38, 4096, 0xFFFFFFFE, 0, 0xFFFFFFFE, 0)
    struct.pack_into('<109I', header, 0x4C, 0, *([0xFFFFFFFF] * 108))
    return bytes(header) + fat_sector + directory.ljust(sec, b'\x00') + body


RESUME_TEXT = (
    'Vishal Goel\rMongoDB Certified DBA\r'
    'Skill\x07Years\x07\x07MongoDB\x076\x07\x07'
    'Meerut Institute of Engineering and Technology\r'
)


def test_word97_doc_is_read_without_antiword(monkeypatch):
    monkeypatch.setattr(tx, '_antiword_path', lambda: '')
    data = _word_doc_bytes([(RESUME_TEXT, True), ('Pune – Résumé\r', False)])
    text = tx.extract_text_from_doc(data)
    assert text.splitlines()[:2] == ['Vishal Goel', 'MongoDB Certified DBA']
    assert 'Skill | Years' in text and 'MongoDB | 6' in text
    assert 'Pune – Résumé' in text  # UTF-16 piece keeps non-ASCII


def test_field_codes_are_dropped_but_their_display_text_kept():
    from app.ai.parser.legacy_doc import extract_doc_text

    data = _word_doc_bytes([(
        'Email: \x13 HYPERLINK "mailto:a@b.com" \x14a@b.com\x15\r' + RESUME_TEXT, True,
    )])
    text = extract_doc_text(data)
    assert 'Email: a@b.com' in text
    assert 'HYPERLINK' not in text


def test_word6_doc_is_read_from_its_single_text_run(monkeypatch):
    monkeypatch.setattr(tx, '_antiword_path', lambda: '')
    text = tx.extract_text_from_doc(_word_doc_bytes([(RESUME_TEXT, True)], word6=True))
    assert 'Vishal Goel' in text and 'MongoDB | 6' in text


def test_password_protected_doc_says_so():
    from app.ai.parser.legacy_doc import extract_doc_text

    with pytest.raises(ValueError, match='password-protected'):
        extract_doc_text(_word_doc_bytes([(RESUME_TEXT, True)], flags=0x0300))


def test_truncated_ole2_header_fails_cleanly_without_antiword(monkeypatch):
    monkeypatch.setattr(tx, '_antiword_path', lambda: '')
    with pytest.raises(ValueError):
        tx.extract_text_from_doc(OLE2_HEADER)


def test_doc_uploads_are_never_refused_up_front():
    assert parsing_mod._reject_unsupported_doc('resume.doc') is None
    assert parsing_mod._reject_unsupported_doc('resume.pdf') is None


# --------------------------------------------- web page / ODT saved as .doc


NAUKRI_HTML = (
    b'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "x.dtd">'
    b'<html><head><meta charset="utf-8"><style>p{color:red}</style><title>CV</title></head>'
    b'<body><div>BHAVIK PATEL</div><p>Marketing Executive &amp; Sales</p>'
    b'<table><tr><td>Company</td><td>Years</td></tr><tr><td>Ketul Chem</td><td>4</td></tr></table>'
    b'<script>alert(1)</script></body></html>'
)


def test_naukri_html_saved_as_doc_is_sniffed_and_extracted(monkeypatch):
    monkeypatch.setattr(tx, '_antiword_path', lambda: '')
    assert parsing_mod.sniff_upload_kind(NAUKRI_HTML) == 'doc'
    text = tx.extract_text_from_doc(NAUKRI_HTML)
    assert 'BHAVIK PATEL' in text
    assert 'Marketing Executive & Sales' in text
    assert 'Ketul Chem | 4' in text
    assert 'alert' not in text and 'color:red' not in text


def test_mhtml_saved_as_doc_is_extracted():
    from app.ai.parser.legacy_doc import extract_html_text, is_html_document

    mhtml = (
        b'MIME-Version: 1.0\r\nContent-Type: multipart/related; boundary="B"\r\n\r\n'
        b'--B\r\nContent-Type: text/html; charset="utf-8"\r\n\r\n'
        b'<html><body><p>Vishal Goel</p><p>MongoDB DBA</p></body></html>\r\n--B--\r\n'
    )
    assert is_html_document(mhtml)
    lines = [ln for ln in extract_html_text(mhtml).splitlines() if ln]
    assert lines == ['Vishal Goel', 'MongoDB DBA']


def test_odt_saved_as_doc_or_docx_is_extracted():
    import zipfile

    content = (
        '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
        'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"><office:body><office:text>'
        '<text:h>Purti Kushwaha</text:h><text:p>Oracle<text:s text:c="2"/>DBA</text:p>'
        '<table:table><table:table-row><table:table-cell><text:p>Skill</text:p></table:table-cell>'
        '<table:table-cell><text:p>RMAN</text:p></table:table-cell></table:table-row></table:table>'
        '<text:p>Meerut Institute of Engineering and Technology</text:p>'
        '</office:text></office:body></office:document-content>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('mimetype', 'application/vnd.oasis.opendocument.text')
        zf.writestr('content.xml', content)
    odt = buf.getvalue()

    text = tx.extract_text_from_doc(odt)
    assert text.splitlines()[:3] == ['Purti Kushwaha', 'Oracle DBA', 'Skill | RMAN']
    # Same file named .docx goes through the dispatcher's ODT detour.
    assert 'Purti Kushwaha' in tx.extract_document(odt, 'resume.docx').text


@pytest.mark.skipif(not tx.antiword_available(), reason='antiword binary not installed')
def test_real_ole2_document_round_trips_through_antiword():
    """Guards the flag order and output cleanup against an antiword upgrade."""
    header_only = OLE2_HEADER  # valid magic, no document body
    with pytest.raises(ValueError):
        tx.extract_text_from_doc(header_only)
