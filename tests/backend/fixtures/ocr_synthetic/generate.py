"""Synthetic scanned/digital PDFs for OCR regression (no real candidate PII)."""
from __future__ import annotations

import io

SYNTHETIC_RESUME = (
    "Alex Example\n"
    "alex.example@example.com\n"
    "Experience\n"
    "Software Engineer at Example Corp 2020-2024\n"
    "Education\n"
    "B.S. Computer Science Example University\n"
    "Skills\n"
    "Python SQL Docker\n"
)


def render_text_png(
    text: str,
    *,
    size: tuple[int, int] = (850, 1100),
    fill: tuple[int, int, int] = (0, 0, 0),
    background: tuple[int, int, int] = (255, 255, 255),
    rotate: int = 0,
    contrast: float = 1.0,
) -> bytes:
    from PIL import Image, ImageDraw, ImageEnhance

    img = Image.new('RGB', size, background)
    draw = ImageDraw.Draw(img)
    y = 40
    for line in text.splitlines():
        draw.text((40, y), line, fill=fill)
        y += 28
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)
    if rotate:
        img = img.rotate(rotate, expand=True, fillcolor=background)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def scanned_pdf_bytes(
    text: str = SYNTHETIC_RESUME,
    *,
    rotate: int = 0,
    fill: tuple[int, int, int] = (0, 0, 0),
    background: tuple[int, int, int] = (255, 255, 255),
    contrast: float = 1.0,
    two_column: bool = False,
) -> bytes:
    import fitz

    if two_column:
        left, _, right = text.partition('\nEducation\n')
        col = left + '\nEducation\n' + right if right else text
        png = render_text_png(col, fill=fill, background=background, rotate=rotate, contrast=contrast)
    else:
        png = render_text_png(text, fill=fill, background=background, rotate=rotate, contrast=contrast)
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(page.rect, stream=png)
    data = doc.tobytes()
    doc.close()
    return data


def digital_pdf_bytes(text: str = SYNTHETIC_RESUME) -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def mixed_pdf_bytes() -> bytes:
    import fitz

    doc = fitz.open()
    digital = doc.new_page(width=612, height=792)
    digital.insert_text((72, 72), 'Digital page one\nExperience at Example Corp\n' + ('python skills ' * 12))
    png = render_text_png('Scanned page two\nEducation\nExample University\nSkills Python')
    scanned = doc.new_page(width=612, height=792)
    scanned.insert_image(scanned.rect, stream=png)
    data = doc.tobytes()
    doc.close()
    return data


def image_heavy_pdf_bytes() -> bytes:
    import fitz

    png = render_text_png(SYNTHETIC_RESUME)
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(page.rect, stream=png)
    page.insert_image(fitz.Rect(400, 600, 580, 760), stream=png)
    page.insert_image(fitz.Rect(40, 600, 220, 760), stream=png)
    data = doc.tobytes()
    doc.close()
    return data
