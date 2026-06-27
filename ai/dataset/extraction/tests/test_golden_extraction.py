"""Golden extraction tests."""

from dataset.factory.inspector.hashing import hash_file

from dataset.extraction.extractors.docx.extractor import DocxExtractor
from dataset.extraction.extractors.txt.extractor import TxtExtractor
from dataset.extraction.validators.extraction_validator import finalize_extraction


def test_golden_docx_extraction(sample_docx) -> None:
    digest, _ = hash_file(sample_docx)
    result = DocxExtractor().extract(sample_docx, relative_path="sample.docx", source_hash=digest)
    result = finalize_extraction(result)

    assert result.success is True
    assert "Senior Software Engineer" in result.raw_text
    assert "Python" in result.raw_text
    assert result.quality.words_extracted >= 5


def test_golden_txt_extraction(sample_txt) -> None:
    digest, _ = hash_file(sample_txt)
    result = TxtExtractor().extract(sample_txt, relative_path="sample.txt", source_hash=digest)
    result = finalize_extraction(result)

    assert result.success is True
    assert "Plain text resume content" in result.raw_text
    assert result.metadata["encoding"] == "utf-8"
