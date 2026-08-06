"""Naukri-shaped payload mapper (placeholder schema)."""
from __future__ import annotations

from typing import Any

from app.domains.integrations.dto import JobSnapshot


def to_naukri_payload(job: JobSnapshot) -> dict[str, Any]:
    return {
        'jobTitle': job.title,
        'company': job.company,
        'jobLocation': job.location,
        'jobDescription': job.description,
        'salary': job.salary,
        'experience': job.experience,
        'keywords': job.keywords,
        'referenceCode': job.job_id,
    }
