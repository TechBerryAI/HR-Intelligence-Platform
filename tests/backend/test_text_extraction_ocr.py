"""Unit tests for PDF/image text extraction and OCR fallback (mocked, no Tesseract required)."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.parser import text_extraction as te


def test_extract_text_from_image_uses_ocr():
    with patch.object(te, "_ocr_image_bytes", return_value="A" * 40) as ocr:
        result = te.extract_text_from_image(b"fake-image-bytes", "resume.png")
    assert len(result) >= 30
    ocr.assert_called_once()


def test_extract_text_from_image_rejects_short_ocr():
    with patch.object(te, "_ocr_image_bytes", return_value="hi"):
        with pytest.raises(ValueError, match="only .* characters"):
            te.extract_text_from_image(b"x", "blank.png")


def test_ocr_image_bytes_missing_engines_message():
    te.reset_ocr_engine_status_cache()
    with patch.object(te, "OCR_ENABLED", True), \
         patch.object(te, "get_ocr_engine_status", return_value=(False, "no engines")):
        with pytest.raises(ValueError, match="OCR engines unavailable"):
            te._ocr_image_bytes(b"x")


def test_ocr_engines_disabled_status():
    te.reset_ocr_engine_status_cache()
    with patch.object(te, "OCR_ENABLED", False):
        te.reset_ocr_engine_status_cache()
        ok, detail = te.get_ocr_engine_status()
        assert ok is False
        assert "OCR_ENABLED" in detail


def test_pdf_skips_per_page_ocr_when_engines_missing():
    """Scanned pages must not burn time rendering/OCR when no engine is installed."""
    te.reset_ocr_engine_status_cache()
    page = MagicMock()
    page.get_text.return_value = ""
    page.get_images.return_value = [("img",)]

    doc = MagicMock()
    doc.__len__.return_value = 3
    doc.__getitem__.return_value = page
    doc.close = MagicMock()

    fake_fitz = MagicMock()
    fake_fitz.open.return_value = doc
    fake_fitz.Matrix = MagicMock(return_value="matrix")

    with patch.dict(sys.modules, {"fitz": fake_fitz}), \
         patch.object(te, "OCR_ENABLED", True), \
         patch.object(te, "ocr_engines_available", return_value=False), \
         patch.object(te, "ocr_unavailable_reason", return_value="no engines"), \
         patch.object(te, "_render_page_png") as render, \
         patch.object(te, "_ocr_image_bytes") as ocr, \
         patch.object(te, "_extract_pdf_page_tables", return_value=""):
        with pytest.raises(ValueError, match="Insufficient text"):
            te.extract_text_from_pdf_pymupdf(b"%PDF-fake")

    render.assert_not_called()
    ocr.assert_not_called()


def test_force_pdf_ocr_fails_fast_without_engines():
    te.reset_ocr_engine_status_cache()
    with patch.object(te, "ocr_engines_available", return_value=False), \
         patch.object(te, "ocr_unavailable_reason", return_value="no engines"):
        with pytest.raises(ValueError, match="Cannot force PDF OCR"):
            te._force_pdf_ocr(b"%PDF-fake")


def test_bulk_needs_ocr_retry_false_without_engines():
    from app.workers import bulk_parser as bp

    with patch(
        "app.ai.parser.text_extraction.ocr_engines_available",
        return_value=False,
    ):
        assert bp._bulk_needs_ocr_retry(
            "pdf", "", "OCR failed", looks_like_garbage=lambda s: True
        ) is False


def test_extract_text_routes_image_extension():
    with patch.object(te, "extract_text_from_image", return_value="X" * 40) as img:
        out = te.extract_text(b"img", "scan.JPEG")
    assert out.startswith("X")
    img.assert_called_once()


def test_extract_text_from_pdf_pymupdf_ocr_when_page_image_based():
    page = MagicMock()
    page.get_text.return_value = ""
    page.get_images.return_value = [("img",)]

    doc = MagicMock()
    doc.__len__.return_value = 1
    doc.__getitem__.return_value = page
    doc.close = MagicMock()

    fake_fitz = MagicMock()
    fake_fitz.open.return_value = doc
    fake_fitz.Matrix = MagicMock(return_value="matrix")

    with patch.dict(sys.modules, {"fitz": fake_fitz}), \
         patch.object(te, "_render_page_png", return_value=b"png"), \
         patch.object(te, "_png_has_ink", return_value=True), \
         patch.object(te, "_ocr_image_bytes", return_value="Scanned resume text " + ("y" * 20)), \
         patch.object(te, "ocr_engines_available", return_value=True), \
         patch.object(te, "OCR_ENABLED", True), \
         patch.object(te, "_extract_pdf_page_tables", return_value=""):
        text = te.extract_text_from_pdf_pymupdf(b"%PDF-fake")

    assert "Scanned resume" in text
    assert len(text) >= 30


def _white_png_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (120, 160), (255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


def _ink_png_bytes() -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (200, 200), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((20, 20, 180, 180), fill=(10, 10, 10))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_png_has_ink_detects_blank_and_content():
    assert te._png_has_ink(_white_png_bytes()) is False
    assert te._png_has_ink(_ink_png_bytes()) is True


def test_blank_pdf_page_does_not_run_ocr():
    page = MagicMock()
    page.get_text.return_value = ""
    page.get_images.return_value = []
    page.find_tables.side_effect = Exception("no tables")

    page2 = MagicMock()
    page2.get_text.return_value = "Digital resume body " + ("x" * 80)
    page2.get_images.return_value = []
    page2.find_tables.side_effect = Exception("no tables")

    doc = MagicMock()
    doc.__len__.return_value = 2
    doc.__getitem__.side_effect = lambda i: page if i == 0 else page2
    doc.close = MagicMock()

    fake_fitz = MagicMock()
    fake_fitz.open.return_value = doc
    fake_fitz.Matrix = MagicMock(return_value="matrix")

    with patch.dict(sys.modules, {"fitz": fake_fitz}), \
         patch.object(te, "_render_page_png", return_value=_white_png_bytes()), \
         patch.object(te, "_ocr_image_bytes") as ocr, \
         patch.object(te, "OCR_ENABLED", True):
        text = te.extract_text_from_pdf_pymupdf(b"%PDF-fake")

    ocr.assert_not_called()
    assert "Digital resume body" in text


def _low_contrast_ink_png_bytes() -> bytes:
    """Gray-on-gray content: old contrast<18 skip, new threshold still sees ink."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (200, 200), (205, 205, 205))
    draw = ImageDraw.Draw(img)
    draw.rectangle((20, 20, 180, 180), fill=(193, 193, 193))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_png_has_ink_keeps_low_contrast_content():
    assert te._png_has_ink(_low_contrast_ink_png_bytes()) is True
    assert te._png_has_ink(_white_png_bytes()) is False


def _legacy_png_dark_ratio_below_threshold(image_bytes: bytes, threshold: float = 0.002) -> bool:
    """True when the pre-fix 240-thumbnail hist[:200] rule would skip OCR."""
    from PIL import Image

    image = Image.open(io.BytesIO(image_bytes))
    gray = image.convert("L")
    gray.thumbnail((240, 240))
    hist = gray.histogram()
    pixels = gray.size[0] * gray.size[1]
    if pixels <= 0:
        return True
    return sum(hist[:200]) <= pixels * threshold


def _sparse_light_text_png_bytes() -> bytes:
    """Light-gray thin text: luma ~215 never hits hist[:200] after a 240 thumbnail."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (800, 1100), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    lines = [
        "Experience",
        "Software Engineer at Sparse Corp",
        "Education University of Testing",
        "Skills Python SQL OCR",
        "Projects OCR mixed PDF recovery",
    ]
    y = 80
    for line in lines:
        draw.text((60, y), line, fill=(215, 215, 215), font=font)
        draw.line((60, y + 10, 420, y + 10), fill=(215, 215, 215), width=1)
        y += 36
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _speckle_png_bytes() -> bytes:
    """A handful of isolated dark pixels on white — dust, not page content."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (800, 1100), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    for xy in ((40, 40), (400, 90), (720, 800), (80, 1000), (600, 500)):
        draw.point(xy, fill=(10, 10, 10))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_png_has_ink_keeps_sparse_light_content():
    sparse = _sparse_light_text_png_bytes()
    assert _legacy_png_dark_ratio_below_threshold(sparse) is True
    assert te._png_has_ink(sparse) is True
    assert te._png_has_ink(_white_png_bytes()) is False


def test_png_has_ink_rejects_speckles():
    assert te._png_has_ink(_speckle_png_bytes()) is False
    assert te._png_has_ink(_white_png_bytes()) is False


def test_image_page_full_dpi_ink_recheck_runs_ocr():
    page = MagicMock()
    page.get_text.return_value = ""
    page.get_images.return_value = [("img",)]
    page.find_tables.side_effect = Exception("no tables")

    doc = MagicMock()
    doc.__len__.return_value = 1
    doc.__getitem__.return_value = page
    doc.close = MagicMock()

    fake_fitz = MagicMock()
    fake_fitz.open.return_value = doc
    fake_fitz.Matrix = MagicMock(return_value="matrix")

    renders = [_white_png_bytes(), _ink_png_bytes()]

    def fake_render(_page, dpi=0):
        return renders.pop(0) if renders else _ink_png_bytes()

    with patch.dict(sys.modules, {"fitz": fake_fitz}), \
         patch.object(te, "_render_page_png", side_effect=fake_render), \
         patch.object(te, "_ocr_image_bytes", return_value="Faint scanned resume " + ("y" * 20)) as ocr, \
         patch.object(te, "ocr_engines_available", return_value=True), \
         patch.object(te, "OCR_ENABLED", True), \
         patch.object(te, "_extract_pdf_page_tables", return_value=""):
        text = te.extract_text_from_pdf_pymupdf(b"%PDF-fake")

    ocr.assert_called()
    assert "Faint scanned" in text


def test_page_needs_ocr_on_garbage_digital_with_images():
    page = MagicMock()
    page.get_images.return_value = [("img",)]
    junk = ":::: **** #### " * 16  # >=200 chars so sparse-image rule does not fire
    assert 200 <= len(junk.strip()) <= 400
    assert te.looks_like_garbage_extract(junk) is True
    assert te._page_needs_ocr(page, junk) is True


def test_should_retry_high_dpi_skips_good_text_and_already_300():
    good = "Jane Doe jane@example.com Experience Python SQL education skills " + ("x" * 20)
    weak = "a few words on a scanned page here"
    with patch.object(te, "ocr_engines_available", return_value=True):
        assert te.should_retry_high_dpi_extract("scan.pdf", good, max_dpi_used=180) is False
        assert te.should_retry_high_dpi_extract("scan.pdf", "", extract_failed=True, max_dpi_used=180) is True
        assert te.should_retry_high_dpi_extract("scan.pdf", "", extract_failed=True, max_dpi_used=300) is False
        assert te.should_retry_high_dpi_extract("note.docx", "", extract_failed=True, max_dpi_used=180) is False
        assert te.should_retry_high_dpi_extract("photo.png", "", extract_failed=True, max_dpi_used=180) is False
        assert te.should_retry_high_dpi_extract("scan.pdf", weak, max_dpi_used=180) is True
    with patch.object(te, "ocr_engines_available", return_value=False):
        assert te.should_retry_high_dpi_extract("scan.pdf", "", extract_failed=True, max_dpi_used=180) is False


def test_ocr_dpi_fast_reads_hardware_start(monkeypatch):
    monkeypatch.delenv("OCR_DPI_FAST", raising=False)
    monkeypatch.setenv("HCIP_OCR_DPI_START", "150")
    assert te._ocr_dpi_fast() == 150
    monkeypatch.setenv("OCR_DPI_FAST", "200")
    assert te._ocr_dpi_fast() == 200


def test_ocr_layout_empty_with_ink_runs_opencv_once():
    from app.ai.parser.layout import detector as det

    ink = _ink_png_bytes()

    with patch.object(det, "preprocess_image_bytes", return_value=ink), \
         patch.object(det, "is_layout_enabled", return_value=True), \
         patch.object(det, "is_jd_layout_enabled", return_value=True), \
         patch.object(det, "_rapidocr_detections", return_value=[]), \
         patch.object(det, "_opencv_then_ocr", return_value="Recovered faint text") as opencv:
        text, source = det.ocr_image_with_layout(ink, ocr_fn=lambda _b: "should-not-run")

    opencv.assert_called_once()
    assert "Recovered" in text
    assert source == "opencv_blocks"


def test_ocr_layout_empty_does_not_call_plain_again():
    with patch.object(te, "OCR_ENABLED", True), \
         patch.object(te, "RESUME_LAYOUT_ENABLED", True), \
         patch.object(te, "ocr_engines_available", return_value=True), \
         patch(
             "app.ai.parser.layout.detector.ocr_image_with_layout",
             return_value=("", "empty"),
         ), \
         patch.object(te, "_ocr_image_bytes_plain") as plain, \
         patch.object(te, "_ocr_with_recovery") as recovery:
        with pytest.raises(ValueError, match="empty"):
            te._ocr_image_bytes(b"png")
        plain.assert_not_called()
        recovery.assert_not_called()


def test_ocr_layout_needs_recovery_runs_tesseract_ladder():
    recovered = "Recovered tesseract resume text " + ("x" * 20)
    with patch.object(te, "OCR_ENABLED", True), \
         patch.object(te, "RESUME_LAYOUT_ENABLED", True), \
         patch.object(te, "ocr_engines_available", return_value=True), \
         patch(
             "app.ai.parser.layout.detector.ocr_image_with_layout",
             return_value=("", "needs_recovery"),
         ), \
         patch.object(
             te,
             "_ocr_with_recovery",
             return_value=te.OcrAttempt(text=recovered, engine="tesseract"),
         ) as recovery:
        out = te._ocr_image_bytes(_ink_png_bytes())
    recovery.assert_called_once()
    assert "Recovered tesseract" in out


def test_extract_text_docx_still_works():
    with pytest.raises(ValueError, match="Unsupported"):
        te.extract_text(b"x", "resume.txt")


def _pdf_doc_from_pages(pages):
    doc = MagicMock()
    doc.__len__.return_value = len(pages)
    doc.__getitem__.side_effect = lambda i: pages[i]
    doc.close = MagicMock()
    fake_fitz = MagicMock()
    fake_fitz.open.return_value = doc
    fake_fitz.Matrix = MagicMock(return_value="matrix")
    return fake_fitz


def test_digital_pdf_does_not_invoke_ocr():
    page = MagicMock()
    page.get_text.return_value = (
        "Alex Example alex@example.com\nExperience Python SQL education skills\n" + ("body " * 40)
    )
    page.get_images.return_value = []
    fake_fitz = _pdf_doc_from_pages([page])
    with patch.dict(sys.modules, {"fitz": fake_fitz}), \
         patch.object(te, "_ocr_image_bytes") as ocr, \
         patch.object(te, "_extract_pdf_page_tables", return_value=""):
        result = te.extract_pdf_pymupdf_document(b"%PDF-fake")
    ocr.assert_not_called()
    assert result.used_ocr is False
    assert "Alex Example" in result.text
    assert result.page_results[0].source == "digital"


def test_mixed_pdf_preserves_page_order():
    digital = MagicMock()
    digital.get_text.return_value = "Digital page one Experience at Example Corp " + ("python " * 20)
    digital.get_images.return_value = []
    scanned = MagicMock()
    scanned.get_text.return_value = ""
    scanned.get_images.return_value = [("img",)]
    fake_fitz = _pdf_doc_from_pages([digital, scanned])
    with patch.dict(sys.modules, {"fitz": fake_fitz}), \
         patch.object(te, "_render_page_png", return_value=b"png"), \
         patch.object(te, "_png_has_ink", return_value=True), \
         patch.object(te, "_ocr_image_bytes", return_value="OCR page two Education University " + ("y" * 20)), \
         patch.object(te, "ocr_engines_available", return_value=True), \
         patch.object(te, "OCR_ENABLED", True), \
         patch.object(te, "_extract_pdf_page_tables", return_value=""):
        result = te.extract_pdf_pymupdf_document(b"%PDF-fake")
    assert result.used_ocr is True
    assert result.ocr_pages == [2]
    assert result.page_results[0].used_ocr is False
    assert result.page_results[1].used_ocr is True
    assert result.text.index("Digital page one") < result.text.index("OCR page two")


def test_mixed_pdf_sparse_light_page_is_ocrd_not_dropped():
    """GOOD digital page + sparse/light scan must OCR page 2 and keep both in order."""
    digital = MagicMock()
    digital.get_text.return_value = (
        "Digital page one Experience at Example Corp " + ("python " * 20)
    )
    digital.get_images.return_value = []
    scanned = MagicMock()
    scanned.get_text.return_value = ""
    scanned.get_images.return_value = [("img",)]
    fake_fitz = _pdf_doc_from_pages([digital, scanned])
    ocr_text = "OCR page two Education University " + ("y" * 20)
    with patch.dict(sys.modules, {"fitz": fake_fitz}), \
         patch.object(te, "_render_page_png", return_value=_sparse_light_text_png_bytes()), \
         patch.object(te, "_ocr_image_bytes", return_value=ocr_text) as ocr, \
         patch.object(te, "ocr_engines_available", return_value=True), \
         patch.object(te, "OCR_ENABLED", True), \
         patch.object(te, "_extract_pdf_page_tables", return_value=""):
        result = te.extract_pdf_pymupdf_document(b"%PDF-fake")
    ocr.assert_called()
    assert result.used_ocr is True
    assert result.ocr_pages == [2]
    assert result.page_results[0].used_ocr is False
    assert result.page_results[1].used_ocr is True
    assert result.page_results[1].fallback != "ink_skip"
    assert "Digital page one" in result.text
    assert "OCR page two" in result.text
    assert result.text.index("Digital page one") < result.text.index("OCR page two")


def test_weak_ocr_escalates_dpi_and_prefers_better():
    page = MagicMock()
    page.get_text.return_value = ""
    page.get_images.return_value = [("img",)]
    fake_fitz = _pdf_doc_from_pages([page])
    ocr_calls = []

    def fake_ocr(_png):
        ocr_calls.append(1)
        if len(ocr_calls) == 1:
            return "xx"
        return "High DPI scanned resume Experience education skills " + ("z" * 30)

    with patch.dict(sys.modules, {"fitz": fake_fitz}), \
         patch.object(te, "_render_page_png", return_value=b"png"), \
         patch.object(te, "_png_has_ink", return_value=True), \
         patch.object(te, "_ocr_image_bytes", side_effect=fake_ocr), \
         patch.object(te, "ocr_engines_available", return_value=True), \
         patch.object(te, "OCR_ENABLED", True), \
         patch.object(te, "_extract_pdf_page_tables", return_value=""):
        result = te.extract_pdf_pymupdf_document(b"%PDF-fake")
    assert len(ocr_calls) >= 2
    assert "High DPI" in result.text
    assert result.final_dpi >= te.OCR_DPI or result.used_ocr


def test_rapidocr_failure_falls_back_to_tesseract():
    with patch.object(te, "_ocr_with_rapidocr", side_effect=RuntimeError("boom")), \
         patch.object(te, "_tesseract_available", return_value=True), \
         patch.object(te, "_ocr_with_tesseract", return_value="Tesseract recovered resume text " + ("x" * 10)):
        out = te._ocr_image_bytes_plain(b"png")
    assert "Tesseract recovered" in out


def test_no_engine_pdf_reports_ocr_unavailable_without_fake_success():
    page = MagicMock()
    page.get_text.return_value = ""
    page.get_images.return_value = [("img",)]
    fake_fitz = _pdf_doc_from_pages([page])
    with patch.dict(sys.modules, {"fitz": fake_fitz}), \
         patch.object(te, "OCR_ENABLED", True), \
         patch.object(te, "ocr_engines_available", return_value=False), \
         patch.object(te, "ocr_unavailable_reason", return_value="no engines"), \
         patch.object(te, "_render_page_png") as render, \
         patch.object(te, "_ocr_image_bytes") as ocr, \
         patch.object(te, "_extract_pdf_page_tables", return_value=""):
        result = te.extract_pdf_pymupdf_document(b"%PDF-fake")
        with pytest.raises(ValueError, match="Insufficient text"):
            te.extract_text_from_pdf_pymupdf(b"%PDF-fake")
    render.assert_not_called()
    ocr.assert_not_called()
    assert result.used_ocr is False
    assert result.status == "ocr_unavailable"
    assert not (result.text or "").strip()


def test_ocr_keeps_short_digital_when_ocr_fails():
    page = MagicMock()
    page.get_text.return_value = "Alex Example leftover header"
    page.get_images.return_value = [("img",)]
    fake_fitz = _pdf_doc_from_pages([page])
    with patch.dict(sys.modules, {"fitz": fake_fitz}), \
         patch.object(te, "_render_page_png", return_value=b"png"), \
         patch.object(te, "_png_has_ink", return_value=True), \
         patch.object(te, "_ocr_image_bytes", side_effect=ValueError("OCR failed")), \
         patch.object(te, "ocr_engines_available", return_value=True), \
         patch.object(te, "OCR_ENABLED", True), \
         patch.object(te, "_extract_pdf_page_tables", return_value=""):
        result = te.extract_pdf_pymupdf_document(b"%PDF-fake")
    assert "Alex Example" in result.text


def test_pdfplumber_does_not_replace_ocr_backed_text():
    from app.ai.parser.pdfplumber_extractor import maybe_use_pdfplumber

    ocr_text = "OCR recovered Experience education skills alex@example.com " + ("x" * 20)
    with patch(
        "app.ai.parser.pdfplumber_extractor.extract_text_from_pdf_pdfplumber"
    ) as plumber:
        text, reason = maybe_use_pdfplumber(
            b"%PDF",
            pymupdf_text=ocr_text,
            used_ocr=True,
        )
    plumber.assert_not_called()
    assert text is None
    assert reason == "ocr_backed_pymupdf"


def test_parallel_extract_results_are_isolated():
    from concurrent.futures import ThreadPoolExecutor

    def run_one(label: str):
        page = MagicMock()
        page.get_text.return_value = ""
        page.get_images.return_value = [("img",)]
        fake_fitz = _pdf_doc_from_pages([page])
        with patch.dict(sys.modules, {"fitz": fake_fitz}), \
             patch.object(te, "_render_page_png", return_value=b"png"), \
             patch.object(te, "_png_has_ink", return_value=True), \
             patch.object(
                 te,
                 "_ocr_image_bytes",
                 return_value=f"{label} scanned resume Experience education " + ("q" * 20),
             ), \
             patch.object(te, "ocr_engines_available", return_value=True), \
             patch.object(te, "OCR_ENABLED", True), \
             patch.object(te, "_extract_pdf_page_tables", return_value=""):
            return te.extract_pdf_pymupdf_document(b"%PDF-fake")

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(run_one, "ALPHA")
        b = pool.submit(run_one, "BETA")
        ra, rb = a.result(), b.result()
    assert "ALPHA" in ra.text
    assert "BETA" in rb.text
    assert "ALPHA" not in rb.text
    assert "BETA" not in ra.text
    assert te.last_extract_max_dpi() == 0
    assert ra.final_dpi != 0 or ra.used_ocr
    assert rb.used_ocr and ra.used_ocr


def test_ocr_health_status_values():
    te.reset_ocr_engine_status_cache()
    with patch.object(te, "OCR_ENABLED", False):
        te.reset_ocr_engine_status_cache()
        assert te.ocr_health_status() == "unavailable"
    te.reset_ocr_engine_status_cache()
    with patch.object(te, "OCR_ENABLED", True), \
         patch.object(te, "get_ocr_engine_status", return_value=(True, "rapidocr")):
        assert te.ocr_health_status() == "ok"
    with patch.object(te, "OCR_ENABLED", True), \
         patch.object(te, "get_ocr_engine_status", return_value=(True, "tesseract")):
        assert te.ocr_health_status() == "degraded"


def test_extract_document_image_uses_ocr():
    with patch.object(te, "extract_text_from_image", return_value="Image resume text " + ("x" * 20)):
        result = te.extract_document(b"img", "scan.PNG")
    assert result.used_ocr is True
    assert result.source == "image"
    assert "Image resume" in result.text


def test_overlay_full_page_image_is_ocrd():
    """Thin digital overlay with resume tokens must not skip OCR on a scanned page."""
    overlay = "Experience\nCurriculum Vitae"
    page = MagicMock()
    page.get_text.return_value = overlay
    page.get_images.return_value = [("img",)]
    page.get_image_info.return_value = [{"bbox": (0, 0, 612, 792)}]
    page.rect.width = 612
    page.rect.height = 792
    page.find_tables.side_effect = Exception("no tables")
    assert te._page_needs_ocr(page, overlay) is True

    fake_fitz = _pdf_doc_from_pages([page])
    ocr_text = "Alex Example scanned overlay recovery Experience education " + ("y" * 20)
    with patch.dict(sys.modules, {"fitz": fake_fitz}), \
         patch.object(te, "_render_page_png", return_value=_ink_png_bytes()), \
         patch.object(te, "_ocr_image_bytes", return_value=ocr_text) as ocr, \
         patch.object(te, "ocr_engines_available", return_value=True), \
         patch.object(te, "OCR_ENABLED", True), \
         patch.object(te, "_extract_pdf_page_tables", return_value=""):
        result = te.extract_pdf_pymupdf_document(b"%PDF-fake")
    ocr.assert_called()
    assert result.used_ocr is True
    assert "scanned overlay" in result.text


def test_render_page_png_caps_long_side():
    page = MagicMock()
    page.rect.width = 4000
    page.rect.height = 6000
    pix = MagicMock()
    pix.tobytes.return_value = b"png"
    page.get_pixmap.return_value = pix
    captured = {}

    def fake_matrix(z1, z2=None):
        captured["zoom"] = z1
        return "matrix"

    fake_fitz = MagicMock()
    fake_fitz.Matrix = fake_matrix
    fake_fitz.csRGB = object()
    with patch.dict(sys.modules, {"fitz": fake_fitz}):
        te._render_page_png(page, dpi=250)
    assert captured["zoom"] <= te._ocr_max_side() / 6000 + 1e-9
    assert captured["zoom"] < 250 / 72.0
    kwargs = page.get_pixmap.call_args.kwargs
    assert kwargs.get("alpha") is False
    assert "colorspace" in kwargs


def test_force_pdf_ocr_uses_recovery_not_layout_raise():
    page = MagicMock()
    page.rect.width = 612
    page.rect.height = 792
    page.get_images.return_value = [("img",)]
    page.get_image_info.return_value = [{"bbox": (0, 0, 612, 792)}]
    fake_fitz = _pdf_doc_from_pages([page])
    recovered = "Force recovery resume Experience education skills " + ("z" * 20)
    with patch.dict(sys.modules, {"fitz": fake_fitz}), \
         patch.object(te, "_render_page_png", return_value=_ink_png_bytes()), \
         patch.object(
             te,
             "_ocr_with_recovery",
             return_value=te.OcrAttempt(text=recovered, engine="rapidocr_raw"),
         ) as recovery, \
         patch.object(te, "_ocr_image_bytes") as layout_path, \
         patch.object(te, "ocr_engines_available", return_value=True):
        out = te._force_pdf_ocr(b"%PDF-fake", dpi=300)
    recovery.assert_called()
    layout_path.assert_not_called()
    assert "Force recovery" in out


def test_ocr_recovery_raw_after_empty_preprocessed():
    with patch.object(te, "_ocr_with_rapidocr", side_effect=[("", None), ("Raw recovered resume text " + ("q" * 20), 0.9)]), \
         patch.object(te, "_tesseract_available", return_value=False):
        attempt = te._ocr_with_recovery(b"png", skip_preprocessed=False)
    assert attempt.engine == "rapidocr_raw"
    assert "Raw recovered" in attempt.text


def test_ocr_recovery_rotates_when_upright_empty():
    def fake_rapidocr(image_bytes, *, preprocess=True):
        if image_bytes == b"rot90":
            return ("Rotated recovered resume Experience education " + ("x" * 20), 0.85)
        return ("", None)

    with patch.object(te, "_ocr_with_rapidocr", side_effect=fake_rapidocr), \
         patch.object(te, "_tesseract_available", return_value=False), \
         patch.object(te, "_rotate_image_bytes", side_effect=lambda _b, deg: f"rot{deg}".encode()):
        attempt = te._ocr_with_recovery(b"upright")
    assert attempt.engine == "rotated_90"
    assert "Rotated recovered" in attempt.text


def test_high_coverage_page_not_ink_skipped():
    page = MagicMock()
    page.get_text.return_value = ""
    page.get_images.return_value = [("img",)]
    page.get_image_info.return_value = [{"bbox": (0, 0, 612, 792)}]
    page.rect.width = 612
    page.rect.height = 792
    fake_fitz = _pdf_doc_from_pages([page])
    with patch.dict(sys.modules, {"fitz": fake_fitz}), \
         patch.object(te, "_render_page_png", return_value=_white_png_bytes()), \
         patch.object(te, "_png_has_ink", return_value=False), \
         patch.object(
             te,
             "_ocr_image_bytes",
             return_value="Coverage scan resume Experience education " + ("y" * 20),
         ) as ocr, \
         patch.object(te, "ocr_engines_available", return_value=True), \
         patch.object(te, "OCR_ENABLED", True), \
         patch.object(te, "_extract_pdf_page_tables", return_value=""):
        result = te.extract_pdf_pymupdf_document(b"%PDF-fake")
    ocr.assert_called()
    assert result.used_ocr is True
    assert "Coverage scan" in result.text
