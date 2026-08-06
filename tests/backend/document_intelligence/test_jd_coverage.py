"""Smoke tests for JD coverage gate package (must stay importable / not gitignored)."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3] / "apps" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.document_intelligence.canonical.from_toon import job_profile_from_toon
from app.ai.document_intelligence.coverage import (
    CoverageReport,
    detect_jd_evidence,
    recover_jd_profile_gaps,
)


def test_coverage_package_exports():
    assert callable(recover_jd_profile_gaps)
    assert callable(detect_jd_evidence)
    assert CoverageReport is not None


def test_recover_fills_location_when_evidence_present():
    text = (
        "Senior Platform Engineer\n"
        "Location: Mumbai\n"
        "Experience: 5+ years\n"
        "Skills: Python, Kubernetes, AWS\n"
        "We build reliable cloud platforms.\n"
    )
    empty = job_profile_from_toon({})
    profile, report = recover_jd_profile_gaps(empty, text)
    assert isinstance(report, CoverageReport)
    loc = (getattr(getattr(profile, "location", None), "primary", "") or "").lower()
    assert "mumbai" in loc
    assert "location" in (report.recovered_fields or [])


def test_recover_unlabeled_location_mumbai_without_newline_bleed():
    text = (
        "Middleware Weblogic Admin JD:\n"
        "Experience- 1 to 5 yrs\n"
        "Location Mumbai(Looking for candidates from Mumbai Location only)\n"
        "Work from office and rotational shifts\n"
        "Primary Technology-Weblogic, OHS\n"
    )
    # Simulate prior garbage fill that must be replaced
    dirty = job_profile_from_toon(
        {"location": {"primary": "Mumbai Work from offi"}}
    )
    profile, report = recover_jd_profile_gaps(dirty, text)
    loc = (getattr(getattr(profile, "location", None), "primary", "") or "").strip()
    assert loc.lower() == "mumbai", f"got {loc!r}"
    assert "work from" not in loc.lower()
    assert "location" not in (report.missing_with_evidence or [])
