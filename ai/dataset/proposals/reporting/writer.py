"""Write dataset-level proposal reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dataset.proposals.shared.utils import write_yaml


def write_dataset_reports(output_root: Path, reports: dict[str, dict[str, Any]]) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    mapping = {
        "proposal_summary.yaml": reports["summary"],
        "proposal_statistics.yaml": reports["statistics"],
        "proposal_errors.yaml": reports["errors"],
        "proposal_log.yaml": reports["log"],
    }
    for filename, payload in mapping.items():
        write_yaml(output_root / filename, payload)
