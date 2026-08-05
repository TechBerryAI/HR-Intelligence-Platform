"""
ONE canonical Job Description model: JobProfile.

No aliases. No duplicate DTOs for the same concept.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class JobBasicInfo(BaseModel):
    title: str = ''
    company: str = ''
    employment_type: str = ''
    description: str = ''


class JobRequirements(BaseModel):
    min_experience_years: Optional[float] = None
    max_experience_years: Optional[float] = None
    qualifications: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class JobResponsibilities(BaseModel):
    items: list[str] = Field(default_factory=list)


class JobSkills(BaseModel):
    mandatory: list[str] = Field(default_factory=list)
    preferred: list[str] = Field(default_factory=list)
    general: list[str] = Field(default_factory=list)


class JobBenefits(BaseModel):
    items: list[str] = Field(default_factory=list)


class JobLocation(BaseModel):
    primary: str = ''


class JobCompensation(BaseModel):
    salary_range: str = ''


class JobPreference(BaseModel):
    key: str = ''
    value: str = ''


class JobProfile(BaseModel):
    """Canonical job description profile — single source of truth."""

    schema_version: str = '1.0.0'
    basic: JobBasicInfo = Field(default_factory=JobBasicInfo)
    requirements: JobRequirements = Field(default_factory=JobRequirements)
    responsibilities: JobResponsibilities = Field(default_factory=JobResponsibilities)
    skills: JobSkills = Field(default_factory=JobSkills)
    benefits: JobBenefits = Field(default_factory=JobBenefits)
    location: JobLocation = Field(default_factory=JobLocation)
    compensation: JobCompensation = Field(default_factory=JobCompensation)
    preferences: list[JobPreference] = Field(default_factory=list)
    field_meta: dict[str, Any] = Field(default_factory=dict)
