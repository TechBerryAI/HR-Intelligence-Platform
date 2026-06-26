"""Simple language hint detection (deterministic, no ML)."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass
class LanguageHint:
    language: str | None
    confidence: float | None = None
    method: str = "ascii_heuristic"


class LanguageDetector:
    """Best-effort language hint without external ML models."""

    NON_ASCII_RATIO_THRESHOLD = 0.15

    def detect(self, text: str) -> LanguageHint:
        sample = text[:5000]
        if not sample.strip():
            return LanguageHint(language=None, confidence=None)

        non_ascii = sum(1 for c in sample if ord(c) > 127)
        ratio = non_ascii / len(sample)
        if ratio > self.NON_ASCII_RATIO_THRESHOLD:
            return LanguageHint(language="non_en", confidence=round(ratio, 2))

        words = re.findall(r"\b[a-zA-Z']+\b", sample.lower())
        if len(words) >= 10:
            return LanguageHint(language="en", confidence=0.6)
        return LanguageHint(language=None, confidence=None)
