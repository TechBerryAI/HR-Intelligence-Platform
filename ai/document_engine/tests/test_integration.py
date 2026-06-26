"""Integration tests for extraction engine."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from document_engine.engine.config import EngineConfig
from document_engine.engine.orchestrator import ExtractionEngine


def test_integration_extracts_docx_and_txt(sample_docx, sample_txt, tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "silver"
    source.mkdir()
    output.mkdir()

    shutil.copy(sample_docx, source / "resume.docx")
    shutil.copy(sample_txt, source / "notes.txt")

    config = EngineConfig(
        source_path=source,
        output_path=output,
        inspection_path=None,
        skip_duplicates=False,
        skip_non_resume_artifacts=False,
    )
    logger = logging.getLogger("test")
    logger.handlers = []
    logger.addHandler(logging.NullHandler())

    result = ExtractionEngine(config, logger).run()

    assert result.files_processed == 2
    assert result.successful >= 1
    assert (output / "extraction_summary.yaml").exists()
    assert (output / "extraction_log.yaml").exists()
    assert any((output / "documents").iterdir())
