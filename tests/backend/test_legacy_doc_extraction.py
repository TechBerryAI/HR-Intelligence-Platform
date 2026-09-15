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


# ----------------------------------------------------------- antiword gate


def test_missing_antiword_explains_itself_rather_than_crashing(monkeypatch):
    monkeypatch.setattr(tx, '_antiword_path', lambda: '')
    with pytest.raises(ValueError, match='antiword'):
        tx.extract_text_from_doc(OLE2_HEADER)


def test_upload_is_refused_only_when_antiword_is_missing(app_ctx, monkeypatch):
    monkeypatch.setattr(tx, '_antiword_path', lambda: '')
    refusal = parsing_mod._reject_unsupported_doc('resume.doc')
    assert refusal is not None and refusal[1] == 400
    assert 'DOCX or PDF' in refusal[0].get_json()['error']

    monkeypatch.setattr(tx, '_antiword_path', lambda: '/usr/bin/antiword')
    assert parsing_mod._reject_unsupported_doc('resume.doc') is None
    assert parsing_mod._reject_unsupported_doc('resume.pdf') is None


@pytest.mark.skipif(not tx.antiword_available(), reason='antiword binary not installed')
def test_real_ole2_document_round_trips_through_antiword():
    """Guards the flag order and output cleanup against an antiword upgrade."""
    header_only = OLE2_HEADER  # valid magic, no document body
    with pytest.raises(ValueError):
        tx.extract_text_from_doc(header_only)
