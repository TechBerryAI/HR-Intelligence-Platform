"""RTF text extraction."""

from __future__ import annotations

import re
import time
from pathlib import Path

from dataset.extraction.extractors.base import BaseExtractor
from dataset.extraction.models import ExtractionResult


class RtfExtractor(BaseExtractor):
    format_id = "rtf"
    method_name = "rtf_strip"

    def extract(self, path: Path, *, relative_path: str, source_hash: str) -> ExtractionResult:
        started = time.perf_counter()
        result = ExtractionResult(
            source_path=str(path),
            relative_path=relative_path,
            format=self.format_id,
            source_hash=source_hash,
            success=False,
            method=self.method_name,
        )

        try:
            raw = path.read_text(encoding="latin-1", errors="replace")
        except OSError as exc:
            result.errors.append(str(exc))
            result.duration_seconds = time.perf_counter() - started
            return result

        text = self._strip_rtf(raw)
        result.raw_text = text
        result.metadata = {"source_format": "rtf", "char_count_raw": len(raw)}
        result.success = bool(text.strip())
        if not result.success:
            result.errors.append("No extractable text found in RTF")

        result.duration_seconds = time.perf_counter() - started
        return result

    @staticmethod
    def _strip_rtf(raw: str) -> str:
        text = raw
        text = re.sub(r"\\'[0-9a-fA-F]{2}", " ", text)
        text = re.sub(r"\\[a-zA-Z]+\-?\d* ?", " ", text)
        text = re.sub(r"[{}]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
