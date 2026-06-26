"""Proposal Generator configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

GENERATOR_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = GENERATOR_ROOT / "config.default.yaml"


class GeneratorConfig(BaseModel):
    """Runtime configuration for proposal generation."""

    source_path: Path
    output_path: Path
    dataset_id: str = "DS-RESUMES-RAW"
    dataset_version: str = "1.0.0"
    doc_type: Literal["resume", "job_description", "mixed"] = "resume"
    default_task: str = "resume_parsing"
    recursive: bool = True
    workers: int = Field(default=4, ge=1, le=64)
    verbose: bool = False
    resume: bool = False
    skip_failed_extractions: bool = True
    skip_empty_text: bool = True
    runtime_config_path: Path | None = None

    @field_validator("source_path", "output_path", "runtime_config_path", mode="before")
    @classmethod
    def _coerce_path(cls, value: Any) -> Path | None:
        if value is None:
            return None
        return Path(value).expanduser().resolve()

    def snapshot(self) -> dict[str, Any]:
        return {
            "source_path": str(self.source_path),
            "output_path": str(self.output_path),
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "doc_type": self.doc_type,
            "default_task": self.default_task,
            "recursive": self.recursive,
            "workers": self.workers,
            "resume": self.resume,
            "skip_failed_extractions": self.skip_failed_extractions,
            "skip_empty_text": self.skip_empty_text,
            "runtime_config_path": str(self.runtime_config_path) if self.runtime_config_path else None,
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
    recursive: bool | None = None,
    workers: int | None = None,
    resume: bool = False,
    verbose: bool = False,
    overrides: dict[str, Any] | None = None,
) -> GeneratorConfig:
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

    return GeneratorConfig(**values)
