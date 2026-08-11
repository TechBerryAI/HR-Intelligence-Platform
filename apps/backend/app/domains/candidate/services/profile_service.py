"""Shared applicant identity + profile persistence (public job apply — no candidate accounts)."""
from __future__ import annotations

import re

from app.database.connection.db import BACKEND, NOW_SQL, db_get, db_run

CGPA_COL = '"cgpa/percentage"' if BACKEND == "postgresql" else "[cgpa/percentage]"

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def validate_public_apply_payload(data: dict, has_resume: bool) -> str | None:
    """Return an error message if invalid, else None."""
    full_name = (data.get("fullName") or "").strip()
    email = normalize_email(data.get("email"))
    phone = (data.get("phone") or "").strip()
    current_location = (data.get("currentLocation") or "").strip()
    preferred_location = (data.get("preferredLocation") or "").strip()
    experience_level = (data.get("experienceLevel") or "").strip()

    if not full_name:
        return "Full name is required"
    if not email or not _EMAIL_RE.match(email):
        return "A valid email is required"
    if not phone:
        return "Phone is required"
    if not current_location:
        return "Current location is required"
    if not preferred_location:
        return "Preferred location is required"
    if experience_level not in ("fresher", "experienced"):
        return "Experience level is required"
    if experience_level == "experienced":
        serving_notice = (data.get("servingNotice") or "").strip().lower()
        if serving_notice not in ("yes", "no"):
            return "Serving notice is required for experienced candidates"
        # Period + last working day only when currently serving notice
        if serving_notice == "yes":
            if not (data.get("noticePeriod") or "").strip():
                return "Notice period is required when serving notice"
            if not (data.get("lastWorkingDay") or "").strip():
                return "Last working date is required when serving notice"
    parsed_id = (data.get("parsedId") or data.get("parsed_id") or "").strip()
    if not has_resume and not parsed_id:
        return "Resume file is required"

    education = data.get("education") or []
    valid_edu = [
        e
        for e in education
        if isinstance(e, dict)
        and (e.get("degree") or "").strip()
        and (e.get("institution") or "").strip()
    ]
    if not valid_edu:
        return "At least one education entry with degree and institution is required"
    return None


def upsert_passwordless_candidate(
    name: str,
    email: str,
    *,
    organization_id: str | None = None,
) -> str:
    """
    Find or create applicant (candidates) by email within an organization — no password / no login.
    Returns cid.
    """
    email_norm = normalize_email(email)
    org_id = str(organization_id or "").strip() or None
    if not org_id:
        raise ValueError("organization_id is required to create a candidate")

    existing = db_get(
        """
        SELECT cid, name FROM candidates
        WHERE organization_id = ?
          AND LOWER(TRIM(email)) = ?
        """,
        (org_id, email_norm),
    )
    if existing:
        cid = existing["cid"]
        if name and name.strip() and name.strip() != (existing.get("name") or ""):
            db_run(
                "UPDATE candidates SET name = ? WHERE cid = ?",
                (name.strip(), cid),
            )
        return cid

    db_run(
        "INSERT INTO candidates (name, email, organization_id) VALUES (?, ?, ?)",
        (name.strip(), email_norm, org_id),
    )
    row = db_get(
        """
        SELECT cid FROM candidates
        WHERE organization_id = ?
          AND LOWER(TRIM(email)) = ?
        """,
        (org_id, email_norm),
    )
    if not row:
        raise RuntimeError("Failed to create candidates row")
    return row["cid"]


def save_candidate_profile(
    candidate_id: str,
    data: dict,
    resume_binary: bytes | None = None,
    *,
    completed: bool = True,
    resume_raw_file_id: str | None = None,
) -> None:
    """Upsert candidate_profiles and replace education/certifications/experiences.

    Prefer ``resume_raw_file_id`` (object/media store) over BYTEA ``resume``.
    When only ``resume_binary`` is provided, bytes are stored via raw_files/media
    and ``resume`` BYTEA is left NULL for new writes.
    """
    from app.domains.recruitment.services.parsing_storage import store_raw_file

    existing = db_get(
        "SELECT candidate_id FROM candidate_profiles WHERE candidate_id = ?",
        (candidate_id,),
    )
    completed_val = (
        True if completed else False
    ) if BACKEND == "postgresql" else (1 if completed else 0)

    email = normalize_email(data.get("email")) or (data.get("email") or "").strip()
    full_name = (data.get("fullName") or "").strip()
    phone = (data.get("phone") or "").strip()
    experience_level = (data.get("experienceLevel") or "").strip() or None
    serving_notice = (data.get("servingNotice") or "").strip() or None
    notice_period = (data.get("noticePeriod") or "").strip() or None
    last_working_day = (data.get("lastWorkingDay") or "").strip() or None
    linkedin_url = (data.get("linkedinUrl") or "").strip() or None
    portfolio_url = (data.get("portfolioUrl") or "").strip() or None
    current_location = (data.get("currentLocation") or "").strip() or None
    preferred_location = (data.get("preferredLocation") or "").strip() or None

    linked_raw_id = resume_raw_file_id
    if resume_binary is not None and len(resume_binary) > 0 and not linked_raw_id:
        stored = store_raw_file(
            candidate_id,
            'candidate',
            resume_binary,
            'resume.pdf',
            'application/pdf',
            None,
        )
        linked_raw_id = stored.get('id')
        if not linked_raw_id:
            raise RuntimeError('resume catalog store did not return raw_file id')

    if existing:
        if linked_raw_id:
            db_run(
                f"""
                UPDATE candidate_profiles SET
                  full_name = ?, email = ?, phone = ?,
                  experience_level = ?, serving_notice = ?, notice_period = ?, last_working_day = ?,
                  linkedin_url = ?, portfolio_url = ?,
                  current_location = ?, preferred_location = ?,
                  resume_raw_file_id = ?,
                  resume = NULL,
                  completed = ?,
                  updated_at = {NOW_SQL}
                WHERE candidate_id = ?
                """,
                (
                    full_name,
                    email,
                    phone,
                    experience_level,
                    serving_notice,
                    notice_period,
                    last_working_day,
                    linkedin_url,
                    portfolio_url,
                    current_location,
                    preferred_location,
                    linked_raw_id,
                    completed_val,
                    candidate_id,
                ),
            )
        else:
            db_run(
                f"""
                UPDATE candidate_profiles SET
                  full_name = ?, email = ?, phone = ?,
                  experience_level = ?, serving_notice = ?, notice_period = ?, last_working_day = ?,
                  linkedin_url = ?, portfolio_url = ?,
                  current_location = ?, preferred_location = ?,
                  completed = ?,
                  updated_at = {NOW_SQL}
                WHERE candidate_id = ?
                """,
                (
                    full_name,
                    email,
                    phone,
                    experience_level,
                    serving_notice,
                    notice_period,
                    last_working_day,
                    linkedin_url,
                    portfolio_url,
                    current_location,
                    preferred_location,
                    completed_val,
                    candidate_id,
                ),
            )
    else:
        db_run(
            """
            INSERT INTO candidate_profiles (
              candidate_id, full_name, email, phone,
              experience_level, serving_notice, notice_period, last_working_day,
              linkedin_url, portfolio_url,
              current_location, preferred_location,
              resume, resume_raw_file_id,
              completed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate_id,
                full_name,
                email,
                phone,
                experience_level,
                serving_notice,
                notice_period,
                last_working_day,
                linkedin_url,
                portfolio_url,
                current_location,
                preferred_location,
                None,  # resume BYTEA retired for new writes — use resume_raw_file_id
                linked_raw_id,
                completed_val,
            ),
        )

    education_entries = data.get("education") or []
    db_run("DELETE FROM candidate_education WHERE candidate_id = ?", (candidate_id,))
    for entry in education_entries:
        if not isinstance(entry, dict):
            continue
        degree = entry.get("degree")
        institution = entry.get("institution")
        cgpa = entry.get("cgpa") or entry.get("cgpaPercentage")
        start_date = entry.get("startMonth") or entry.get("start_date")
        end_date = entry.get("endMonth") or entry.get("end_date")
        if not degree and not institution and not cgpa and not start_date and not end_date:
            continue
        db_run(
            "INSERT INTO candidate_education (candidate_id, degree, institution, "
            + CGPA_COL
            + ", start_date, end_date) VALUES (?, ?, ?, ?, ?, ?)",
            (candidate_id, degree, institution, cgpa, start_date, end_date),
        )

    certification_entries = data.get("certifications") or []
    db_run("DELETE FROM candidate_certifications WHERE candidate_id = ?", (candidate_id,))
    for entry in certification_entries:
        if not isinstance(entry, dict):
            continue
        certification = entry.get("certification") or entry.get("name")
        issuer = entry.get("issuer") or entry.get("authority")
        end_month = (
            entry.get("endMonth")
            or entry.get("end_month")
            or entry.get("validTill")
        )
        if not certification and not issuer and not end_month:
            continue
        db_run(
            """
            INSERT INTO candidate_certifications (candidate_id, certification, issuer, end_month)
            VALUES (?, ?, ?, ?)
            """,
            (candidate_id, certification, issuer, end_month),
        )

    experience_entries = data.get("experiences") or []
    db_run("DELETE FROM candidate_experiences WHERE candidate_id = ?", (candidate_id,))
    for entry in experience_entries:
        if not isinstance(entry, dict):
            continue
        company = entry.get("company")
        role = entry.get("role")
        start_date = entry.get("startMonth") or entry.get("start_date")
        end_date = entry.get("endMonth") or entry.get("end_date")
        is_current = entry.get("isCurrent", False)
        if is_current:
            present = "yes"
            end_date = None
        else:
            present = "no"
        if not company and not role and not start_date:
            continue
        db_run(
            """
            INSERT INTO candidate_experiences (candidate_id, company, role, start_date, end_date, present)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (candidate_id, company, role, start_date, end_date, present),
        )


def link_parsed_resume(parsed_id: str | None, candidate_id: str, public_uploader_id: str | None = None) -> dict | None:
    """
    Ensure a parsed_resumes row is linked to candidate_id.
    Returns the parsed resume record or None.

    Public apply often hits content-hash cache: client gets an existing parsed_id
    plus a fresh PUB* uploader id. Do not require raw_files.uploader_id to match
    that new PUB id — UUID parsed_id from the parse response is sufficient to
    bind an unowned row (or reuse a row already owned by this candidate).
    """
    if parsed_id:
        row = db_get(
            "SELECT id, toon, confidence, raw_file_id, candidate_id FROM parsed_resumes WHERE id = ?",
            (parsed_id,),
        )
        if row:
            existing_cid = row.get('candidate_id')
            if not existing_cid:
                # Prefer proving uploader ownership when available; otherwise allow
                # content-hash cache reuse (unowned row + explicit parsed_id).
                if public_uploader_id and row.get('raw_file_id'):
                    owned = db_get(
                        "SELECT 1 AS ok FROM raw_files WHERE id = ? AND uploader_id = ?",
                        (row['raw_file_id'], public_uploader_id),
                    )
                    if not owned:
                        # Cache hit under a prior PUB* uploader — still bind for this apply
                        pass
                db_run(
                    "UPDATE parsed_resumes SET candidate_id = ? WHERE id = ? AND candidate_id IS NULL",
                    (candidate_id, parsed_id),
                )
            elif str(existing_cid) != str(candidate_id):
                # Same resume bytes previously linked to another applicant — reuse TOON
                # for ATS without stealing the foreign candidate_id link.
                return row
            return row

    row = db_get(
        """
        SELECT toon, confidence, id, raw_file_id
        FROM parsed_resumes
        WHERE candidate_id = ?
        ORDER BY created_at DESC
        """,
        (candidate_id,),
    )
    if row:
        return row

    if public_uploader_id:
        row = db_get(
            """
            SELECT pr.toon, pr.confidence, pr.id, pr.raw_file_id
            FROM parsed_resumes pr
            INNER JOIN raw_files rf ON pr.raw_file_id = rf.id
            WHERE rf.uploader_id = ?
            ORDER BY pr.created_at DESC
            """,
            (public_uploader_id,),
        )
        if row:
            db_run(
                "UPDATE parsed_resumes SET candidate_id = ? WHERE id = ? AND (candidate_id IS NULL OR candidate_id = ?)",
                (candidate_id, row["id"], candidate_id),
            )
            return row
    return None
