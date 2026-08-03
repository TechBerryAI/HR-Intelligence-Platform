"""
Form DTOs — the ONLY shapes React may consume for autofill.

Values are plain form-ready primitives. Traceability lives in `trace`.
Wire keys with leading underscores (legacy form extras) are produced via
serialization aliases — Pydantic fields themselves never start with `_`.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EducationFormRow(BaseModel):
    degree: str = ''
    institution: str = ''
    cgpa: str = ''
    startMonth: str = ''
    endMonth: str = ''


class ExperienceFormRow(BaseModel):
    company: str = ''
    role: str = ''
    startMonth: str = ''
    endMonth: str = ''
    isCurrent: bool = False
    description: str = ''


class CertificationFormRow(BaseModel):
    name: str = ''
    issuer: str = ''
    validTill: str = ''
    validationUrl: str = ''
    status: str = ''


class FieldTrace(BaseModel):
    """End-to-end trace for one form field."""

    form_field: str
    canonical_path: str
    mapper: str
    source: str = ''
    validator: str = ''
    confidence: float = 0.0
    reason: str = ''


class ApplicationFormDTO(BaseModel):
    """Apply-job form autofill payload."""

    model_config = ConfigDict(populate_by_name=True)

    fullName: str = ''
    email: str = ''
    phone: str = ''
    linkedinUrl: str = ''
    portfolioUrl: str = ''
    githubUrl: str = ''
    currentLocation: str = ''
    preferredLocation: str = ''
    experienceLevel: str = ''
    skills: str = ''
    summary: str = ''
    education: list[EducationFormRow] = Field(default_factory=list)
    experiences: list[ExperienceFormRow] = Field(default_factory=list)
    certifications: list[CertificationFormRow] = Field(default_factory=list)
    skillsList: list[str] = Field(default_factory=list, serialization_alias='_skills')
    summaryText: str = Field(default='', serialization_alias='_summary')
    trace: list[FieldTrace] = Field(default_factory=list)

    def to_autofill_dict(self) -> dict[str, Any]:
        """Plain dict for JSON — includes `_skills` / `_summary` aliases for FE."""
        data = self.model_dump(by_alias=True, exclude={'trace'})
        data['trace'] = [t.model_dump() for t in self.trace]
        return data


class JobCreateFormDTO(BaseModel):
    """Recruiter job-create form autofill payload."""

    model_config = ConfigDict(populate_by_name=True)

    title: str = ''
    location: str = ''
    experienceFrom: str = ''
    experienceTo: str = ''
    description: str = ''
    salary: str = ''
    company: str = ''
    mandatorySkills: list[str] = Field(default_factory=list)
    preferredSkills: list[str] = Field(default_factory=list)
    employmentType: str = ''
    skillsList: list[str] = Field(default_factory=list, serialization_alias='_skills')
    mandatorySkillsList: list[str] = Field(
        default_factory=list, serialization_alias='_mandatorySkills'
    )
    preferredSkillsList: list[str] = Field(
        default_factory=list, serialization_alias='_preferredSkills'
    )
    responsibilitiesList: list[str] = Field(
        default_factory=list, serialization_alias='_responsibilities'
    )
    qualificationsList: list[str] = Field(
        default_factory=list, serialization_alias='_qualifications'
    )
    keywordsList: list[str] = Field(default_factory=list, serialization_alias='_keywords')
    trace: list[FieldTrace] = Field(default_factory=list)

    def to_autofill_dict(self) -> dict[str, Any]:
        data = self.model_dump(by_alias=True, exclude={'trace'})
        data['trace'] = [t.model_dump() for t in self.trace]
        return data
