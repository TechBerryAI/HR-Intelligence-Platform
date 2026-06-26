"""Write inspection artifacts to disk."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from ..utils import yaml_dump


ARTIFACT_FILES = [
    "dataset_manifest.yaml",
    "dataset_profile.yaml",
    "quality_report.yaml",
    "statistics.yaml",
    "hash_index.json",
    "inspection_log.yaml",
]


def ensure_output_dir(output_path: Path) -> None:
    """Create output directory if missing."""
    output_path.mkdir(parents=True, exist_ok=True)


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write dictionary as YAML file."""
    path.write_text(yaml_dump(data), encoding="utf-8")


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Write dictionary as JSON file."""
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_artifacts(output_path: Path, artifacts: dict[str, dict[str, Any]]) -> list[str]:
    """Write all inspection artifacts and return relative artifact names."""
    ensure_output_dir(output_path)
    written: list[str] = []

    for filename in ARTIFACT_FILES:
        if filename not in artifacts:
            continue
        target = output_path / filename
        if filename.endswith(".json"):
            write_json(target, artifacts[filename])
        else:
            write_yaml(target, artifacts[filename])
        written.append(filename)

    return written
