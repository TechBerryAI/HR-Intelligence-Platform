"""LinkedIn-shaped payload mapper (placeholder schema)."""
from __future__ import annotations

from typing import Any

from app.domains.integrations.dto import JobSnapshot


def to_linkedin_payload(job: JobSnapshot) -> dict[str, Any]:
    return {
        'title': job.title,
        'companyName': job.company,
        'location': job.location,
        'description': job.description,
        'employmentStatus': 'FULL_TIME',
        'externalJobPostingId': job.job_id,
        'listedAt': None,
        'workplaceTypes': ['On-site'],
        'salaryInsights': job.salary,
        'experienceLevel': job.experience,
        'skills': (job.keywords or '').split(',') if job.keywords else [],
    }
