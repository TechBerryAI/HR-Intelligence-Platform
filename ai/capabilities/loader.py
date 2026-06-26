"""Capability package loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from capabilities.models import CapabilityMetadata, CapabilityPackage, CapabilityRuntimeConfig


class CapabilityLoadError(Exception):
    """Failed to load a capability package."""


REQUIRED_FILES = (
    "capability.yaml",
    "prompt.md",
    "schema.json",
    "validation.yaml",
    "runtime.yaml",
)


def load_capability(capability_dir: Path) -> CapabilityPackage:
    """Load a single capability from its directory."""
    capability_dir = capability_dir.resolve()
    if not capability_dir.is_dir():
        raise CapabilityLoadError(f"Capability directory not found: {capability_dir}")

    missing = [name for name in REQUIRED_FILES if not (capability_dir / name).exists()]
    if missing:
        raise CapabilityLoadError(
            f"Capability '{capability_dir.name}' missing required files: {', '.join(missing)}"
        )

    metadata = _load_metadata(capability_dir / "capability.yaml")
    prompt_text = (capability_dir / "prompt.md").read_text(encoding="utf-8")
    schema_doc = json.loads((capability_dir / "schema.json").read_text(encoding="utf-8"))
    validation_rules = _load_yaml(capability_dir / "validation.yaml")
    runtime_config = CapabilityRuntimeConfig(**_load_yaml(capability_dir / "runtime.yaml"))

    if metadata.id != capability_dir.name:
        raise CapabilityLoadError(
            f"Capability id '{metadata.id}' does not match directory '{capability_dir.name}'"
        )

    return CapabilityPackage(
        metadata=metadata,
        root_dir=capability_dir,
        prompt_text=prompt_text,
        schema_doc=schema_doc,
        validation_rules=validation_rules,
        runtime_config=runtime_config,
    )


def discover_capabilities(capabilities_dir: Path) -> dict[str, CapabilityPackage]:
    """Discover and load all capability packages under capabilities_dir."""
    capabilities_dir = capabilities_dir.resolve()
    if not capabilities_dir.exists():
        raise CapabilityLoadError(f"Capabilities directory not found: {capabilities_dir}")

    loaded: dict[str, CapabilityPackage] = {}
    for entry in sorted(capabilities_dir.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith((".", "_")):
            continue
        if not (entry / "capability.yaml").exists():
            continue
        package = load_capability(entry)
        if package.status != "active":
            continue
        if package.id in loaded:
            raise CapabilityLoadError(f"Duplicate capability id: {package.id}")
        loaded[package.id] = package
    return loaded


def _load_metadata(path: Path) -> CapabilityMetadata:
    raw = _load_yaml(path)
    capability_section = raw.get("capability", raw)
    if not isinstance(capability_section, dict):
        raise CapabilityLoadError(f"Invalid capability.yaml structure: {path}")
    return CapabilityMetadata(**capability_section)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise CapabilityLoadError(f"Expected mapping in {path}")
    return data
