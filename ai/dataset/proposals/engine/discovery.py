"""Discover Silver Dataset documents for proposal generation."""

from __future__ import annotations

from pathlib import Path

from dataset.proposals.engine.config import GeneratorConfig
from dataset.proposals.models.proposal import SilverDocumentJob
from dataset.proposals.shared.constants import DOC_TYPE_TASK_MAP, REQUIRED_SILVER_FILES
from dataset.proposals.shared.utils import load_yaml


def discover_silver_documents(config: GeneratorConfig) -> list[SilverDocumentJob]:
    """Discover document directories under the Silver Dataset."""
    source = config.source_path
    if not source.exists():
        raise FileNotFoundError(f"SOURCE_NOT_FOUND: {source}")

    documents_root = source / "documents"
    if not documents_root.exists():
        raise FileNotFoundError(f"DOCUMENTS_NOT_FOUND: {documents_root}")

    jobs: list[SilverDocumentJob] = []
    iterator = documents_root.rglob("*") if config.recursive else documents_root.glob("*")

    seen_dirs: set[Path] = set()
    for path in sorted(iterator, key=lambda p: p.as_posix()):
        if not path.is_file() or path.name != "raw_text.txt":
            continue
        doc_dir = path.parent
        if doc_dir in seen_dirs:
            continue
        seen_dirs.add(doc_dir)

        if not _has_required_files(doc_dir):
            continue

        metadata = load_yaml(doc_dir / "metadata.yaml")
        extraction_report = load_yaml(doc_dir / "extraction_report.yaml")
        document = metadata.get("document", {})
        artifact = metadata.get("artifact", {})
        quality = extraction_report.get("quality", {})

        doc_type = str(document.get("doc_type") or config.doc_type)
        task_name = DOC_TYPE_TASK_MAP.get(doc_type, config.default_task)
        document_id = doc_dir.name
        relative = doc_dir.relative_to(source).as_posix()

        output_dir = config.output_path / "documents" / document_id
        jobs.append(
            SilverDocumentJob(
                document_id=document_id,
                source_dir=str(doc_dir),
                output_dir=str(output_dir),
                relative_path=relative,
                doc_type=doc_type,
                task_name=task_name,
                dataset_id=str(artifact.get("dataset_id") or config.dataset_id),
                dataset_version=str(artifact.get("dataset_version") or config.dataset_version),
                source_file=str(document.get("source_file") or document_id),
                source_hash=str(document.get("source_hash") or artifact.get("sha256") or ""),
                extraction_success=bool(quality.get("extraction_success", True)),
            )
        )
    return jobs


def _has_required_files(doc_dir: Path) -> bool:
    return all((doc_dir / name).exists() for name in REQUIRED_SILVER_FILES)
