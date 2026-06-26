"""Sequential artifact ID assignment."""

from __future__ import annotations

import re
import threading
from pathlib import Path

from proposal_generator.shared.constants import ARTIFACT_PREFIX, SEQUENCE_FILENAME
from proposal_generator.shared.utils import load_yaml, write_yaml


class ArtifactIdAllocator:
    """Assign monotonic ART-00000001 style identifiers."""

    _PATTERN = re.compile(rf"^{ARTIFACT_PREFIX}-(\d{{8}})$")

    def __init__(self, output_root: Path) -> None:
        self._output_root = output_root
        self._sequence_path = output_root / SEQUENCE_FILENAME
        self._lock = threading.Lock()
        self._next_value = 1
        self._load_sequence()

    @property
    def sequence_path(self) -> Path:
        return self._sequence_path

    def assign(self) -> str:
        with self._lock:
            artifact_id = self._format(self._next_value)
            self._next_value += 1
            self._persist()
            return artifact_id

    def _load_sequence(self) -> None:
        if self._sequence_path.exists():
            data = load_yaml(self._sequence_path)
            self._next_value = int(data.get("next_value", 1))
            return

        max_existing = self._scan_existing_max()
        self._next_value = max_existing + 1
        self._persist()

    def _scan_existing_max(self) -> int:
        maximum = 0
        documents_root = self._output_root / "documents"
        if not documents_root.exists():
            return maximum

        for metadata_path in documents_root.glob("*/proposal_metadata.yaml"):
            try:
                data = load_yaml(metadata_path)
            except (OSError, ValueError):
                continue
            artifact_id = str(data.get("artifact", {}).get("artifact_id", ""))
            match = self._PATTERN.match(artifact_id)
            if match:
                maximum = max(maximum, int(match.group(1)))
        return maximum

    def _persist(self) -> None:
        write_yaml(
            self._sequence_path,
            {
                "sequence": {
                    "prefix": ARTIFACT_PREFIX,
                    "next_value": self._next_value,
                    "last_assigned": self._format(self._next_value - 1) if self._next_value > 1 else None,
                }
            },
        )

    @classmethod
    def _format(cls, value: int) -> str:
        return f"{ARTIFACT_PREFIX}-{value:08d}"
