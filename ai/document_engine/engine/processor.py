"""Process individual documents."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from dataset_factory.inspector.format_detection import FormatRegistry
from dataset_factory.inspector.hashing import hash_file

from document_engine.engine.config import EngineConfig
from document_engine.extractors.registry import ExtractorRegistry
from document_engine.models import DocumentJob, ExtractionResult
from document_engine.validators.extraction_validator import finalize_extraction


class DocumentProcessor:
    """Extract a single document and write silver artifacts."""

    def __init__(self, config: EngineConfig, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self.format_registry = FormatRegistry()
        self.extractors = ExtractorRegistry(pdf_max_pages=config.pdf_max_pages)

    def should_skip(self, job: DocumentJob, output_dir: Path) -> ExtractionResult | None:
        if self.config.skip_duplicates and job.is_duplicate:
            return ExtractionResult(
                source_path=job.absolute_path,
                relative_path=job.relative_path,
                format=job.format,
                source_hash=job.source_hash or "",
                success=False,
                skipped=True,
                skip_reason=f"Duplicate of {job.duplicate_of}",
            )
        return None

    def process(self, job: DocumentJob) -> ExtractionResult:
        path = Path(job.absolute_path)
        started = time.perf_counter()

        source_hash = job.source_hash
        if not source_hash:
            source_hash, hash_error = hash_file(path)
            if hash_error:
                return ExtractionResult(
                    source_path=job.absolute_path,
                    relative_path=job.relative_path,
                    format=job.format,
                    source_hash="",
                    success=False,
                    errors=[hash_error],
                    duration_seconds=time.perf_counter() - started,
                )
            job.source_hash = source_hash

        if self.config.resume and self._already_extracted(job, self._doc_output_dir(job)):
            return ExtractionResult(
                source_path=job.absolute_path,
                relative_path=job.relative_path,
                format=job.format,
                source_hash=source_hash,
                success=True,
                skipped=True,
                skip_reason="Already extracted (--resume)",
                duration_seconds=time.perf_counter() - started,
            )

        skip = self.should_skip(job, self._doc_output_dir(job))
        if skip is not None:
            skip.duration_seconds = time.perf_counter() - started
            return skip

        detected = self.format_registry.detect(path)
        format_id = detected.format_id if detected.supported else job.format
        if format_id == "unknown":
            return ExtractionResult(
                source_path=job.absolute_path,
                relative_path=job.relative_path,
                format="unknown",
                source_hash=source_hash,
                success=False,
                errors=["Unsupported or unknown format"],
                duration_seconds=time.perf_counter() - started,
            )

        result = self.extractors.extract(
            path,
            format_id=format_id,
            relative_path=job.relative_path,
            source_hash=source_hash,
        )

        if job.inspector_ocr_required and not result.quality.requires_ocr:
            result.quality.requires_ocr = True
            result.warnings.append("Inspector flagged OCR required")

        result = finalize_extraction(result)
        result.duration_seconds = time.perf_counter() - started
        return result

    def _doc_output_dir(self, job: DocumentJob) -> Path:
        from document_engine.shared.utils import document_id_from_hash

        doc_id = document_id_from_hash(job.source_hash or "sha256:unknown")
        return self.config.output_path / "documents" / doc_id

    @staticmethod
    def _already_extracted(job: DocumentJob, output_dir: Path) -> bool:
        metadata_path = output_dir / "metadata.yaml"
        if not metadata_path.exists():
            return False
        try:
            import yaml

            with metadata_path.open(encoding="utf-8") as handle:
                metadata = yaml.safe_load(handle) or {}
            extraction = metadata.get("extraction", {})
            return (
                extraction.get("success") is True
                and metadata.get("source_hash") == job.source_hash
            )
        except Exception:  # noqa: BLE001
            return False
