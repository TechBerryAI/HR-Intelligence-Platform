"""Classify certifications vs skills vs training vs experience mentions.

Does not invent a certification title from an issuer or a technology token.
"""
from __future__ import annotations

import re

from app.ai.document_intelligence.association.evidence import Evidence
from app.ai.document_intelligence.association.taxonomy import SECTION_MISCLASSIFICATION
from app.ai.document_intelligence.models.candidate import CertificateEntry, SkillEntry
from app.ai.document_intelligence.parsers.resume import _DUTY_VERB_START

# Credential evidence — not a technology brand list.
_CERT_EVIDENCE = re.compile(
    r'(?i)\b(?:certified|certificate|certification|licen[cs]ed?|licen[cs]e)\b'
)
_TRAINING_EVIDENCE = re.compile(
    r'(?i)\b(?:training|workshop|bootcamp|seminar|completed\s+\w.{0,40}\s+course)\b'
)
# Compact professional credential abbreviations (entity type, not resume-specific).
_CREDENTIAL_ABBREV = re.compile(
    r'(?i)^(pmp|cissp|ccna|ccnp|ccie|cisa|cism|cissp|itil(?:\s+v?\d)?|'
    r'comptia(?:\s+\w+)?|cka|ckad|rhce|rhcsa|ceh|oscp)$'
)


def classify_certificate_name(name: str) -> str:
    """Return certification | training | skill | experience_mention | uncertain."""
    t = (name or '').strip()
    if not t:
        return 'uncertain'
    if _CERT_EVIDENCE.search(t):
        return 'certification'
    if _CREDENTIAL_ABBREV.match(t):
        return 'certification'
    if _TRAINING_EVIDENCE.search(t):
        return 'training'
    if _DUTY_VERB_START.match(t) or (len(t.split()) > 12):
        return 'experience_mention'
    if len(t.split()) <= 2:
        return 'skill'
    return 'uncertain'


def associate_certificates_and_skills(
    certificates: list[CertificateEntry],
    skills: list[SkillEntry],
    *,
    report: list[dict] | None = None,
) -> tuple[list[CertificateEntry], list[SkillEntry]]:
    kept_certs: list[CertificateEntry] = []
    for cert in certificates:
        kind = classify_certificate_name(cert.name)
        evidence = Evidence()
        if kind == 'certification':
            evidence.add('entity_pattern')
            evidence.add('explicit_label')
            kept_certs.append(cert)
            if report is not None:
                report.append({'field': 'certification', 'name': cert.name, 'kind': kind, 'action': 'keep'})
            continue
        if kind in {'skill', 'training', 'experience_mention'}:
            if report is not None:
                report.append(
                    {
                        'field': 'certification',
                        'name': cert.name,
                        'kind': kind,
                        'action': 'drop',
                        'taxonomy': SECTION_MISCLASSIFICATION,
                    }
                )
            continue
        # Uncertain: keep to avoid regressing titled credentials without a cue.
        kept_certs.append(cert)
        if report is not None:
            report.append({'field': 'certification', 'name': cert.name, 'kind': kind, 'action': 'keep'})

    kept_skills: list[SkillEntry] = []
    seen = {(s.canonical or s.name or '').strip().lower() for s in skills}
    for skill in skills:
        label = (skill.canonical or skill.name or '').strip()
        kind = classify_certificate_name(label)
        if kind == 'certification':
            if not any(
                (c.name or '').strip().lower() == label.lower() for c in kept_certs
            ):
                kept_certs.append(CertificateEntry(name=label[:200]))
            if report is not None:
                report.append(
                    {
                        'field': 'skill',
                        'name': label,
                        'kind': kind,
                        'action': 'move_to_cert',
                        'taxonomy': SECTION_MISCLASSIFICATION,
                    }
                )
            continue
        kept_skills.append(skill)

    # Do not invent skills from dropped cert tokens (correctly missing > wrong).
    _ = seen
    return kept_certs, kept_skills
