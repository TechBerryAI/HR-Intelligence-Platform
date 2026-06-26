"""Load Dataset Inspector artifacts for extraction gating."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class InspectorContext:
    """Inspector artifacts consumed by the extraction engine."""

    inspection_path: Path
    manifest: dict[str, Any] = field(default_factory=dict)
    quality_report: dict[str, Any] = field(default_factory=dict)
    hash_index: dict[str, Any] = field(default_factory=dict)
    ocr_required_paths: set[str] = field(default_factory=set)
    hash_by_path: dict[str, dict[str, Any]] = field(default_factory=dict)
    extraction_ready: bool | None = None

    @classmethod
    def load(cls, inspection_path: Path) -> InspectorContext:
        ctx = cls(inspection_path=inspection_path.resolve())
        manifest_path = inspection_path / "dataset_manifest.yaml"
        quality_path = inspection_path / "quality_report.yaml"
        hash_path = inspection_path / "hash_index.json"
        profile_path = inspection_path / "dataset_profile.yaml"

        if manifest_path.exists():
            with manifest_path.open(encoding="utf-8") as handle:
                ctx.manifest = yaml.safe_load(handle) or {}

        if quality_path.exists():
            with quality_path.open(encoding="utf-8") as handle:
                ctx.quality_report = yaml.safe_load(handle) or {}
            gates = ctx.quality_report.get("gates", {})
            ctx.extraction_ready = gates.get("extraction_ready")

        if hash_path.exists():
            with hash_path.open(encoding="utf-8") as handle:
                ctx.hash_index = json.load(handle)
            for entry in ctx.hash_index.get("entries", []):
                path = entry.get("path")
                if path:
                    ctx.hash_by_path[path] = entry

        if profile_path.exists():
            with profile_path.open(encoding="utf-8") as handle:
                profile = yaml.safe_load(handle) or {}
            for signal in profile.get("ocr_signals", []):
                if signal.get("signal") == "ocr_required":
                    ctx.ocr_required_paths.add(signal["path"])

        return ctx

    def hash_for_path(self, relative_path: str) -> str | None:
        entry = self.hash_by_path.get(relative_path)
        return entry.get("sha256") if entry else None

    def is_duplicate(self, relative_path: str) -> bool:
        entry = self.hash_by_path.get(relative_path)
        return bool(entry and entry.get("duplicate_of"))

    def duplicate_of(self, relative_path: str) -> str | None:
        entry = self.hash_by_path.get(relative_path)
        return entry.get("duplicate_of") if entry else None
