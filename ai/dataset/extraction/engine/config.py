"""Configuration for Document Processing Engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

ENGINE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ENGINE_ROOT / "config.default.yaml"
DEFAULT_INSPECTION_PATH = ENGINE_ROOT.parent / "lake" / "inspection"


class EngineConfig(BaseModel):
    """Runtime configuration for document extraction."""

    source_path: Path
    output_path: Path
    inspection_path: Path | None = None
    dataset_id: str = "DS-RESUMES-RAW"
    dataset_version: str = "1.0.0"
    doc_type: Literal["resume", "job_description", "mixed"] = "resume"
    recursive: bool = True
    workers: int = Field(default=4, ge=1, le=64)
    verbose: bool = False
    resume: bool = False
    skip_duplicates: bool = True
    skip_corrupt: bool = False
    skip_password_protected: bool = True
    skip_non_resume_artifacts: bool = True
    enforce_extraction_gate: bool = False
    pdf_max_pages: int = Field(default=0, ge=0)
    hash_algorithm: Literal["sha256"] = "sha256"

    @field_validator("source_path", "output_path", "inspection_path", mode="before")
    @classmethod
    def _coerce_path(cls, value: Any) -> Path | None:
        if value is None:
            return None
        return Path(value).expanduser().resolve()

    def snapshot(self) -> dict[str, Any]:
        return {
            "source_path": str(self.source_path),
            "output_path": str(self.output_path),
            "inspection_path": str(self.inspection_path) if self.inspection_path else None,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "doc_type": self.doc_type,
            "recursive": self.recursive,
            "workers": self.workers,
            "resume": self.resume,
            "skip_duplicates": self.skip_duplicates,
            "skip_corrupt": self.skip_corrupt,
            "skip_password_protected": self.skip_password_protected,
            "skip_non_resume_artifacts": self.skip_non_resume_artifacts,
            "enforce_extraction_gate": self.enforce_extraction_gate,
            "pdf_max_pages": self.pdf_max_pages,
        }


def load_config_file(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a mapping: {path}")
    return data


def build_config(
    *,
    input_path: Path | None = None,
    output_path: Path | None = None,
    config_path: Path | None = None,
    inspection_path: Path | None = None,
    recursive: bool | None = None,
    workers: int | None = None,
    resume: bool = False,
    verbose: bool = False,
    overrides: dict[str, Any] | None = None,
) -> EngineConfig:
    values: dict[str, Any] = {}
    if DEFAULT_CONFIG_PATH.exists():
        values.update(load_config_file(DEFAULT_CONFIG_PATH))
    if config_path is not None:
        values.update(load_config_file(config_path))
    if overrides:
        values.update({k: v for k, v in overrides.items() if v is not None})

    if input_path is not None:
        values["source_path"] = input_path
    if output_path is not None:
        values["output_path"] = output_path
    if inspection_path is not None:
        values["inspection_path"] = inspection_path
    elif values.get("inspection_path") is None:
        values["inspection_path"] = DEFAULT_INSPECTION_PATH
    if recursive is not None:
        values["recursive"] = recursive
    if workers is not None:
        values["workers"] = workers

    values["resume"] = resume
    values["verbose"] = verbose

    if "source_path" not in values:
        raise ValueError("--input / source_path is required")
    if "output_path" not in values:
        raise ValueError("--output / output_path is required")

    return EngineConfig(**values)
