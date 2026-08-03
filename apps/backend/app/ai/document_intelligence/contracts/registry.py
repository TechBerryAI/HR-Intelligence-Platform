"""
Field Contract Registry.

Every Application Form / Job Form field defines:
  source → validator → confidence → mapper → destination
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class FieldContract:
    form_field: str
    canonical_path: str
    source: str  # deterministic | knowledge | semantic_ai | derived
    validator: str
    mapper: str
    destination: str  # ApplicationFormDTO | JobCreateFormDTO
    confidence_rule: str = 'fixed'
    default_confidence: float = 0.9


RESUME_MAPPER = 'document_intelligence.mapping.resume_form.v1'
JD_MAPPER = 'document_intelligence.mapping.jd_form.v1'


RESUME_FIELD_CONTRACTS: dict[str, FieldContract] = {
    'fullName': FieldContract(
        'fullName', 'personal.full_name', 'deterministic', 'validate_person_name',
        RESUME_MAPPER, 'ApplicationFormDTO', default_confidence=0.95,
    ),
    'email': FieldContract(
        'email', 'contact.email', 'deterministic', 'validate_email',
        RESUME_MAPPER, 'ApplicationFormDTO', default_confidence=0.99,
    ),
    'phone': FieldContract(
        'phone', 'contact.phone', 'deterministic', 'validate_phone',
        RESUME_MAPPER, 'ApplicationFormDTO', default_confidence=0.95,
    ),
    'linkedinUrl': FieldContract(
        'linkedinUrl', 'contact.linkedin', 'deterministic', 'validate_url',
        RESUME_MAPPER, 'ApplicationFormDTO', default_confidence=0.95,
    ),
    'portfolioUrl': FieldContract(
        'portfolioUrl', 'contact.portfolio', 'deterministic', 'validate_url',
        RESUME_MAPPER, 'ApplicationFormDTO', default_confidence=0.9,
    ),
    'githubUrl': FieldContract(
        'githubUrl', 'contact.github', 'deterministic', 'validate_url',
        RESUME_MAPPER, 'ApplicationFormDTO', default_confidence=0.95,
    ),
    'currentLocation': FieldContract(
        'currentLocation', 'contact.location', 'deterministic', 'validate_nonempty',
        RESUME_MAPPER, 'ApplicationFormDTO', default_confidence=0.85,
    ),
    'preferredLocation': FieldContract(
        'preferredLocation', 'contact.preferred_location', 'deterministic', 'validate_nonempty',
        RESUME_MAPPER, 'ApplicationFormDTO', default_confidence=0.85,
    ),
    'experienceLevel': FieldContract(
        'experienceLevel', 'total_experience_years|experience[]', 'derived', 'experience_level_rule',
        RESUME_MAPPER, 'ApplicationFormDTO', default_confidence=0.85,
    ),
    'skills': FieldContract(
        'skills', 'skills[].canonical', 'knowledge', 'validate_skill_item',
        RESUME_MAPPER, 'ApplicationFormDTO', default_confidence=0.9,
    ),
    'summary': FieldContract(
        'summary', 'personal.summary', 'semantic_ai', 'validate_nonempty',
        RESUME_MAPPER, 'ApplicationFormDTO', default_confidence=0.8,
    ),
    'education[].degree': FieldContract(
        'education[].degree', 'education[].degree+field', 'deterministic', 'validate_degree',
        RESUME_MAPPER, 'ApplicationFormDTO', default_confidence=0.85,
    ),
    'education[].institution': FieldContract(
        'education[].institution', 'education[].institution', 'deterministic',
        'validate_institution', RESUME_MAPPER, 'ApplicationFormDTO', default_confidence=0.85,
    ),
    'education[].cgpa': FieldContract(
        'education[].cgpa', 'education[].gpa', 'deterministic', 'validate_nonempty',
        RESUME_MAPPER, 'ApplicationFormDTO', default_confidence=0.8,
    ),
    'education[].startMonth': FieldContract(
        'education[].startMonth', 'education[].start', 'deterministic', 'validate_month_year',
        RESUME_MAPPER, 'ApplicationFormDTO', default_confidence=0.85,
    ),
    'education[].endMonth': FieldContract(
        'education[].endMonth', 'education[].end', 'deterministic', 'validate_month_year',
        RESUME_MAPPER, 'ApplicationFormDTO', default_confidence=0.85,
    ),
    'experiences[].company': FieldContract(
        'experiences[].company', 'experience[].company', 'deterministic', 'validate_company',
        RESUME_MAPPER, 'ApplicationFormDTO', default_confidence=0.85,
    ),
    'experiences[].role': FieldContract(
        'experiences[].role', 'experience[].role', 'deterministic', 'validate_role',
        RESUME_MAPPER, 'ApplicationFormDTO', default_confidence=0.85,
    ),
    'experiences[].startMonth': FieldContract(
        'experiences[].startMonth', 'experience[].start', 'deterministic', 'validate_month_year',
        RESUME_MAPPER, 'ApplicationFormDTO', default_confidence=0.85,
    ),
    'experiences[].endMonth': FieldContract(
        'experiences[].endMonth', 'experience[].end', 'deterministic', 'validate_month_year',
        RESUME_MAPPER, 'ApplicationFormDTO', default_confidence=0.85,
    ),
    'experiences[].isCurrent': FieldContract(
        'experiences[].isCurrent', 'experience[].is_current', 'deterministic', 'boolean',
        RESUME_MAPPER, 'ApplicationFormDTO', default_confidence=0.9,
    ),
    'experiences[].description': FieldContract(
        'experiences[].description', 'experience[].description', 'semantic_ai', 'validate_nonempty',
        RESUME_MAPPER, 'ApplicationFormDTO', default_confidence=0.75,
    ),
    'certifications[].name': FieldContract(
        'certifications[].name', 'certificates[].name', 'deterministic', 'validate_nonempty',
        RESUME_MAPPER, 'ApplicationFormDTO', default_confidence=0.8,
    ),
}


JD_FIELD_CONTRACTS: dict[str, FieldContract] = {
    'title': FieldContract(
        'title', 'basic.title', 'deterministic', 'validate_nonempty',
        JD_MAPPER, 'JobCreateFormDTO', default_confidence=0.95,
    ),
    'location': FieldContract(
        'location', 'location.primary', 'deterministic', 'validate_nonempty',
        JD_MAPPER, 'JobCreateFormDTO', default_confidence=0.9,
    ),
    'company': FieldContract(
        'company', 'basic.company', 'deterministic', 'validate_company',
        JD_MAPPER, 'JobCreateFormDTO', default_confidence=0.85,
    ),
    'salary': FieldContract(
        'salary', 'compensation.salary_range', 'deterministic', 'validate_nonempty',
        JD_MAPPER, 'JobCreateFormDTO', default_confidence=0.85,
    ),
    'experienceFrom': FieldContract(
        'experienceFrom', 'requirements.min_experience_years', 'deterministic', 'numeric',
        JD_MAPPER, 'JobCreateFormDTO', default_confidence=0.9,
    ),
    'experienceTo': FieldContract(
        'experienceTo', 'requirements.max_experience_years', 'deterministic', 'numeric',
        JD_MAPPER, 'JobCreateFormDTO', default_confidence=0.9,
    ),
    'mandatorySkills': FieldContract(
        'mandatorySkills', 'skills.mandatory', 'knowledge', 'validate_skill_item',
        JD_MAPPER, 'JobCreateFormDTO', default_confidence=0.9,
    ),
    'preferredSkills': FieldContract(
        'preferredSkills', 'skills.preferred', 'knowledge', 'validate_skill_item',
        JD_MAPPER, 'JobCreateFormDTO', default_confidence=0.85,
    ),
    'employmentType': FieldContract(
        'employmentType', 'basic.employment_type', 'deterministic', 'validate_nonempty',
        JD_MAPPER, 'JobCreateFormDTO', default_confidence=0.85,
    ),
    'description': FieldContract(
        'description', 'format_jd_description(...)', 'derived', 'format_jd_description',
        JD_MAPPER, 'JobCreateFormDTO', default_confidence=0.9,
    ),
}


def get_contract(form_field: str, *, kind: str = 'resume') -> Optional[FieldContract]:
    table = RESUME_FIELD_CONTRACTS if kind == 'resume' else JD_FIELD_CONTRACTS
    return table.get(form_field)
