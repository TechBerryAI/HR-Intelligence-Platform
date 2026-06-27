"""Legacy DOC (OLE) text extraction."""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from dataset.extraction.extractors.base import BaseExtractor
from dataset.extraction.models import ExtractionResult


class DocExtractor(BaseExtractor):
    format_id = "doc"
    method_name = "antiword"

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

        antiword = shutil.which("antiword")
        if not antiword:
            result.errors.append(
                "Legacy .doc extraction requires antiword CLI (not installed). "
                "Convert to DOCX or install antiword."
            )
            result.duration_seconds = time.perf_counter() - started
            return result

        try:
            completed = subprocess.run(
                [antiword, "-m", "UTF-8.txt", str(path)],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except subprocess.TimeoutExpired:
            result.errors.append("antiword timed out")
            result.duration_seconds = time.perf_counter() - started
            return result
        except OSError as exc:
            result.errors.append(str(exc))
            result.duration_seconds = time.perf_counter() - started
            return result

        if completed.returncode != 0:
            result.errors.append(completed.stderr.strip() or f"antiword exited with code {completed.returncode}")
            result.duration_seconds = time.perf_counter() - started
            return result

        result.raw_text = completed.stdout
        result.metadata = {"extractor": "antiword", "encoding": "UTF-8"}
        result.success = bool(result.raw_text.strip())
        if not result.success:
            result.errors.append("antiword returned empty text")

        result.duration_seconds = time.perf_counter() - started
        return result
