"""Validate Silver Dataset inputs before runtime execution."""

from __future__ import annotations

from pathlib import Path

from proposal_generator.engine.config import GeneratorConfig
from proposal_generator.models.proposal import ProposalResult, SilverDocumentJob
from proposal_generator.shared.utils import load_yaml


class InputValidator:
    """Gate proposal generation on Silver Dataset readiness."""

    def validate(self, job: SilverDocumentJob, config: GeneratorConfig) -> ProposalResult | None:
        if config.resume and self._already_generated(job):
            return ProposalResult(
                document_id=job.document_id,
                relative_path=job.relative_path,
                skipped=True,
                skip_reason="Already generated (--resume)",
            )

        if config.skip_failed_extractions and not job.extraction_success:
            return ProposalResult(
                document_id=job.document_id,
                relative_path=job.relative_path,
                skipped=True,
                skip_reason="Extraction failed in Silver Dataset",
                warnings=["Skipped document with failed extraction"],
            )

        raw_text_path = Path(job.source_dir) / "raw_text.txt"
        if not raw_text_path.exists():
            return ProposalResult(
                document_id=job.document_id,
                relative_path=job.relative_path,
                success=False,
                errors=["Missing raw_text.txt"],
            )

        text = raw_text_path.read_text(encoding="utf-8")
        if config.skip_empty_text and not text.strip():
            return ProposalResult(
                document_id=job.document_id,
                relative_path=job.relative_path,
                skipped=True,
                skip_reason="Empty extracted text",
                warnings=["Skipped document with empty raw_text.txt"],
            )

        metadata_path = Path(job.source_dir) / "metadata.yaml"
        if metadata_path.exists():
            try:
                load_yaml(metadata_path)
            except ValueError as exc:
                return ProposalResult(
                    document_id=job.document_id,
                    relative_path=job.relative_path,
                    success=False,
                    errors=[f"Invalid metadata.yaml: {exc}"],
                )

        return None

    def _already_generated(self, job: SilverDocumentJob) -> bool:
        proposal_json = Path(job.output_dir) / "proposal.json"
        proposal_metadata = Path(job.output_dir) / "proposal_metadata.yaml"
        return proposal_json.exists() and proposal_metadata.exists()
