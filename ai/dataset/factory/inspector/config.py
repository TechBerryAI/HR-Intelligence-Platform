"""Configuration for Dataset Inspector."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator


FACTORY_VERSION = "1.0.0"
STAGE_ID = "STAGE-INSPECTOR"
STAGE_VERSION = "1.0.0"

INSPECTOR_ROOT = Path(__file__).resolve().parent
FORMAT_REGISTRY_PATH = INSPECTOR_ROOT.parent / "shared" / "format_registry.yaml"
QUALITY_MODEL_PATH = INSPECTOR_ROOT / "quality_model.yaml"
DEFAULT_CONFIG_PATH = INSPECTOR_ROOT / "config.default.yaml"


class InspectorConfig(BaseModel):
    """Runtime configuration for a dataset inspection run."""

    source_path: Path
    output_path: Path
    dataset_id: str = "DS-RESUMES-RAW"
    dataset_version: str = "1.0.0"
    dataset_name: str = "Raw Resume Corpus"
    doc_type: Literal["resume", "job_description", "mixed"] = "resume"
    recursive: bool = True
    workers: int = Field(default=4, ge=1, le=64)
    verbose: bool = False
    dry_run: bool = False
    follow_symlinks: bool = False
    max_file_size_bytes: int = 52_428_800
    hash_algorithm: Literal["sha256"] = "sha256"
    enable_near_duplicate: bool = False
    sampling_rate: float = Field(default=0.05, ge=0.0, le=1.0)
    min_samples: int = 10
    max_samples: int = 500
    max_depth_logged: int = 10
    factory_version: str = FACTORY_VERSION

    @field_validator("source_path", "output_path", mode="before")
    @classmethod
    def _coerce_path(cls, value: Any) -> Path:
        return Path(value).expanduser().resolve()

    @field_validator("dataset_id")
    @classmethod
    def _validate_dataset_id(cls, value: str) -> str:
        import re

        if not re.match(r"^DS-[A-Z0-9-]+$", value):
            raise ValueError("dataset_id must match pattern ^DS-[A-Z0-9-]+$")
        return value

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serializable config snapshot for the inspection log."""
        return {
            "source_path": str(self.source_path),
            "output_path": str(self.output_path),
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "dataset_name": self.dataset_name,
            "doc_type": self.doc_type,
            "recursive": self.recursive,
            "workers": self.workers,
            "follow_symlinks": self.follow_symlinks,
            "max_file_size_bytes": self.max_file_size_bytes,
            "hash_algorithm": self.hash_algorithm,
            "enable_near_duplicate": self.enable_near_duplicate,
            "sampling_rate": self.sampling_rate,
            "min_samples": self.min_samples,
            "max_samples": self.max_samples,
            "max_depth_logged": self.max_depth_logged,
            "factory_version": self.factory_version,
        }


def load_config_file(path: Path) -> dict[str, Any]:
    """Load YAML configuration file."""
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
    verbose: bool = False,
    dry_run: bool = False,
    overrides: dict[str, Any] | None = None,
) -> InspectorConfig:
    """Merge defaults, config file, and CLI overrides into InspectorConfig."""
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

    values["verbose"] = verbose
    values["dry_run"] = dry_run

    if "source_path" not in values:
        raise ValueError("--input / source_path is required")
    if "output_path" not in values:
        raise ValueError("--output / output_path is required")

    return InspectorConfig(**values)
