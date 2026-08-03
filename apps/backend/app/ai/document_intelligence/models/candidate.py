"""
ONE canonical Resume model: CandidateProfile.

No aliases. No duplicate DTOs for the same concept.
Persistence may serialize to TOON; React never sees TOON for autofill.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class PersonalInfo(BaseModel):
    full_name: str = ''
    summary: str = ''


class ContactInfo(BaseModel):
    email: str = ''
    phone: str = ''
    location: str = ''
    preferred_location: str = ''
    linkedin: str = ''
    github: str = ''
    portfolio: str = ''
    other_links: list[str] = Field(default_factory=list)


class EducationEntry(BaseModel):
    degree: str = ''
    field: str = ''
    institution: str = ''
    gpa: str = ''
    start: str = ''
    end: str = ''


class ExperienceEntry(BaseModel):
    company: str = ''
    role: str = ''
    start: str = ''
    end: str = ''
    is_current: bool = False
    description: str = ''
    location: str = ''


class ProjectEntry(BaseModel):
    name: str = ''
    description: str = ''
    technologies: list[str] = Field(default_factory=list)
    url: str = ''


class SkillEntry(BaseModel):
    name: str = ''
    canonical: str = ''
    category: str = ''


class CertificateEntry(BaseModel):
    name: str = ''
    issuer: str = ''
    valid_till: str = ''
    validation_url: str = ''
    status: str = ''


class LanguageEntry(BaseModel):
    name: str = ''
    proficiency: str = ''


class LinkEntry(BaseModel):
    label: str = ''
    url: str = ''


class PreferenceEntry(BaseModel):
    key: str = ''
    value: str = ''


class CandidateProfile(BaseModel):
    """Canonical resume / candidate profile — single source of truth."""

    schema_version: str = '1.0.0'
    personal: PersonalInfo = Field(default_factory=PersonalInfo)
    contact: ContactInfo = Field(default_factory=ContactInfo)
    education: list[EducationEntry] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    skills: list[SkillEntry] = Field(default_factory=list)
    certificates: list[CertificateEntry] = Field(default_factory=list)
    languages: list[LanguageEntry] = Field(default_factory=list)
    links: list[LinkEntry] = Field(default_factory=list)
    preferences: list[PreferenceEntry] = Field(default_factory=list)
    total_experience_years: Optional[float] = None
    # Provenance metadata from engine (optional)
    field_meta: dict[str, Any] = Field(default_factory=dict)
