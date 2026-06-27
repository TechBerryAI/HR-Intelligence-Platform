"""Format detection using shared format registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .config import FORMAT_REGISTRY_PATH


@dataclass(frozen=True)
class FormatSpec:
    """Detected format specification."""

    format_id: str
    supported: bool
    magic_matched: bool = False


class FormatRegistry:
    """Load and apply format detection rules."""

    SUPPORTED_FORMATS = {"pdf", "docx", "doc", "txt", "rtf", "zip"}

    def __init__(self, registry_path: Path | None = None) -> None:
        path = registry_path or FORMAT_REGISTRY_PATH
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        self._formats: dict[str, dict[str, Any]] = data.get("formats", {})
        if not self._formats and "format_registry" in data:
            registry = data["format_registry"]
            if isinstance(registry, dict):
                self._formats = registry.get("formats", {})
        self._extension_map: dict[str, str] = {}
        for format_id, spec in self._formats.items():
            for ext in spec.get("extensions", []):
                self._extension_map[ext.lower().lstrip(".")] = format_id

    def detect(self, path: Path, header_bytes: bytes | None = None) -> FormatSpec:
        """Detect file format via magic bytes with extension fallback."""
        extension = path.suffix.lower().lstrip(".")
        header = header_bytes if header_bytes is not None else self._read_header(path)

        magic_matches: list[str] = []
        for format_id, spec in self._formats.items():
            for magic in spec.get("magic_bytes", []):
                if "hex" in magic:
                    magic_bytes = bytes.fromhex(magic["hex"])
                    offset = magic.get("offset", 0)
                    if header[offset : offset + len(magic_bytes)] == magic_bytes:
                        magic_matches.append(format_id)
                elif "ascii_prefix" in magic:
                    prefix = magic["ascii_prefix"].encode("utf-8")
                    if header.startswith(prefix):
                        magic_matches.append(format_id)

        if len(magic_matches) == 1:
            format_id = magic_matches[0]
            if extension and extension in self._extension_map:
                ext_format = self._extension_map[extension]
                if ext_format != format_id and format_id == "zip" and ext_format == "docx":
                    format_id = "docx"
            return FormatSpec(format_id=format_id, supported=True, magic_matched=True)

        if extension == "pdf" and header[:4] == b"PK\x03\x04":
            return FormatSpec(format_id="docx", supported=True, magic_matched=True)

        if extension in self._extension_map:
            format_id = self._extension_map[extension]
            return FormatSpec(format_id=format_id, supported=True, magic_matched=False)

        if magic_matches:
            format_id = magic_matches[0]
            return FormatSpec(format_id=format_id, supported=True, magic_matched=True)

        return FormatSpec(format_id="unknown", supported=False)

    @staticmethod
    def _read_header(path: Path, size: int = 16) -> bytes:
        try:
            with path.open("rb") as handle:
                return handle.read(size)
        except OSError:
            return b""
