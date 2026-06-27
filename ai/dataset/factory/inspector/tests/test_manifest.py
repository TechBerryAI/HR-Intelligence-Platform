"""Tests for dataset manifest generation."""

from datetime import datetime, timezone

from dataset.factory.inspector.models import InspectionResult
from dataset.factory.inspector.reporting.generators import build_manifest


def test_build_manifest_contains_required_fields() -> None:
    started = datetime(2026, 6, 26, tzinfo=timezone.utc)
    result = InspectionResult(
        run_id="11111111-1111-1111-1111-111111111111",
        started_at=started,
        completed_at=started,
        source_path="/data/resumes",
        output_path="/data/inspection",
        duration_seconds=1.5,
        status="inspected",
    )

    manifest = build_manifest(
        result,
        {"workers": 4},
        dataset_id="DS-RESUMES-RAW",
        dataset_version="1.0.0",
        dataset_name="Raw Resume Corpus",
        doc_type="resume",
        factory_version="1.0.0",
        status="inspected",
    )

    assert manifest["manifest"]["id"] == "DATASET-MANIFEST"
    assert manifest["dataset"]["id"] == "DS-RESUMES-RAW"
    assert manifest["source"]["mutability"] == "read_only"
    assert manifest["inspection"]["stage_id"] == "STAGE-INSPECTOR"
    assert manifest["status"] == "inspected"
    assert "dataset_profile.yaml" in manifest["artifacts"]["dataset_profile"]
