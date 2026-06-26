"""Write proposal artifacts to disk."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from proposal_generator.shared.utils import write_yaml


def write_proposal_artifacts(
    output_dir: Path,
    *,
    proposal: Any,
    metadata: dict[str, Any],
    report: dict[str, Any],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "proposal.json").write_text(
        json.dumps(proposal, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    write_yaml(output_dir / "proposal_metadata.yaml", metadata)
    write_yaml(output_dir / "proposal_report.yaml", report)
    return output_dir
