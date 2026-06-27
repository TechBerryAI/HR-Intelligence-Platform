"""Plain text extraction."""

from __future__ import annotations

import time
from pathlib import Path

from dataset.extraction.detectors.language.detector import LanguageDetector
from dataset.extraction.extractors.base import BaseExtractor
from dataset.extraction.models import ExtractionResult


class TxtExtractor(BaseExtractor):
    format_id = "txt"
    method_name = "plain_text"

    ENCODINGS = ("utf-8", "utf-8-sig", "latin-1", "cp1252")

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

        raw = path.read_bytes()
        if b"\x00" in raw:
            result.quality.encoding_issues = True
            result.warnings.append("Null bytes detected in text file")

        text = None
        encoding_used = None
        for encoding in self.ENCODINGS:
            try:
                text = raw.decode(encoding)
                encoding_used = encoding
                break
            except UnicodeDecodeError:
                continue

        if text is None:
            result.quality.encoding_issues = True
            result.errors.append("Unable to decode text file with supported encodings")
            result.duration_seconds = time.perf_counter() - started
            return result

        result.raw_text = text
        result.metadata = {
            "encoding": encoding_used,
            "line_count": text.count("\n") + (1 if text else 0),
            "byte_length": len(raw),
        }
        lang = LanguageDetector().detect(text)
        if lang.language:
            result.metadata["language_hint"] = lang.language

        result.success = bool(text.strip())
        if not result.success:
            result.errors.append("Text file is empty")

        result.duration_seconds = time.perf_counter() - started
        return result
