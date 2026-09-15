"""Paths, field specification, and run configuration for the resume benchmark."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / 'apps' / 'backend'

# Gold corpus (real candidate PII — git-ignored, stays on disk).
CORPUS_DIR = Path(
    os.getenv('RESUME_BENCHMARK_CORPUS', str(ROOT / 'ai' / 'dataset' / 'lake' / 'benchmark' / 'resume_gold' / 'v1'))
)
CASES_DIR = CORPUS_DIR / 'cases'
CORPUS_MANIFEST = CORPUS_DIR / 'manifest.json'

# Run artifacts.
RUNS_DIR = Path(os.getenv('RESUME_BENCHMARK_RUNS', str(ROOT / 'ai' / 'eval' / 'reports' / 'resume_benchmark')))
BASELINE_LINK = RUNS_DIR / 'baseline.json'

THRESHOLDS_FILE = Path(__file__).resolve().parent / 'thresholds.yaml'

# Match quality band shared by every fuzzy comparator.
MATCH_STRONG = 0.85
MATCH_PARTIAL = 0.60


@dataclass(frozen=True)
class FieldSpec:
    """One scored field: where it lives in gold, in the prediction, and how to compare."""

    key: str
    """Key in ``ApplicationFormDTO.to_autofill_dict()``."""

    gold_column: str
    """Column header in the benchmark spreadsheet."""

    label: str
    metric: str
    """One of: name, email, phone, location, url, enum, skills, text, section."""

    weight: float = 1.0
    critical: bool = False
    """Critical fields block the regression gate on any drop."""

    blank_gold_fallback: str = ''
    """Field this one intentionally falls back to when the resume states nothing.

    When gold is blank and the prediction merely echoes that field's gold value,
    the product is behaving as designed - score it as a blank match, not as a
    hallucination. ``preferredLocation`` mirroring ``currentLocation`` is the
    one such rule today (``VALIDATION_FIX_preferred_location_fallback``).
    """


FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec('fullName', 'Full Name', 'Full name', 'name', weight=1.5, critical=True),
    FieldSpec('email', 'Email', 'Email', 'email', weight=1.5, critical=True),
    FieldSpec('phone', 'Phone', 'Phone', 'phone', weight=1.5, critical=True),
    FieldSpec('currentLocation', 'Current location', 'Current location', 'location'),
    FieldSpec(
        'preferredLocation', 'Preferred location', 'Preferred location', 'location',
        weight=0.5, blank_gold_fallback='currentLocation',
    ),
    FieldSpec('linkedinUrl', 'LinkedIn URL', 'LinkedIn URL', 'url'),
    FieldSpec('portfolioUrl', 'Portfolio', 'Portfolio URL', 'url', weight=0.5),
    FieldSpec('githubUrl', 'GitHub URL', 'GitHub URL', 'url'),
    FieldSpec('experienceLevel', 'Experience level', 'Experience level', 'enum'),
    FieldSpec('skills', 'Skills (comma-separated)', 'Skills', 'skills', weight=1.5, critical=True),
    FieldSpec('summary', 'Professional summary', 'Professional summary', 'text'),
    FieldSpec('education', 'Education', 'Education', 'section', weight=1.5, critical=True),
    FieldSpec('experiences', 'Experience', 'Experience', 'section', weight=1.5, critical=True),
    FieldSpec('certifications', 'Certifications', 'Certifications', 'section'),
)

FIELD_BY_KEY = {f.key: f for f in FIELDS}
GOLD_COLUMNS = tuple(f.gold_column for f in FIELDS)
FILENAME_COLUMN = 'File Name'

# Section key -> subfields on the predicted form rows that hold comparable text.
SECTION_VALUE_FIELDS = {
    'education': ('degree', 'institution'),
    'experiences': ('company', 'role'),
    'certifications': ('name', 'issuer'),
}

SECTION_DATE_FIELDS = ('startMonth', 'endMonth', 'validTill')


def load_thresholds() -> dict:
    """Read ``thresholds.yaml`` without requiring PyYAML.

    The file is a flat two-level mapping of numbers, written by
    ``run_benchmark.py --write-thresholds``.
    """
    if not THRESHOLDS_FILE.exists():
        return {}
    text = THRESHOLDS_FILE.read_text(encoding='utf-8')
    try:
        import yaml

        return yaml.safe_load(text) or {}
    except ImportError:
        pass

    data: dict[str, dict[str, float]] = {}
    section: dict[str, float] | None = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if not line.startswith((' ', '\t')):
            key = line.split(':', 1)[0].strip()
            section = data.setdefault(key, {})
            continue
        if section is None or ':' not in line:
            continue
        key, raw = line.split(':', 1)
        raw = raw.strip()
        try:
            section[key.strip()] = float(raw) if '.' in raw else int(raw)
        except ValueError:
            section[key.strip()] = raw
    return data
