"""Indeed-shaped payload mapper (placeholder schema)."""
from __future__ import annotations

from typing import Any

from app.domains.integrations.dto import JobSnapshot


def to_indeed_payload(job: JobSnapshot) -> dict[str, Any]:
    return {
        'title': job.title,
        'company': job.company,
        'city': job.location,
        'description': job.description,
        'salary': job.salary,
        'jobType': 'fulltime',
        'referenceNumber': job.job_id,
        'experience': job.experience,
    }
