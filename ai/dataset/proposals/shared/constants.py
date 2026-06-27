"""Shared constants."""

from __future__ import annotations

ENGINE_VERSION = "1.0.0"
STAGE_ID = "STAGE-PROPOSAL-GENERATOR"
ARTIFACT_TYPE = "PROPOSAL"
ARTIFACT_PREFIX = "ART"
SEQUENCE_FILENAME = ".artifact_sequence.yaml"

DOC_TYPE_TASK_MAP: dict[str, str] = {
    "resume": "resume_parsing",
    "job_description": "jd_parsing",
    "jd": "jd_parsing",
}

REQUIRED_SILVER_FILES = ("raw_text.txt", "metadata.yaml", "extraction_report.yaml")
PROPOSAL_FILES = ("proposal.json", "proposal_metadata.yaml", "proposal_report.yaml")
