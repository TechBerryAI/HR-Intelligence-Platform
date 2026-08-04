"""
Batch-evaluate JD PDFs in /JD using deterministic Document Intelligence only
(no Ollama / semantic enrichment — avoids hangs when LLM is unavailable).
"""
from __future__ import annotations

import json
import re
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "apps" / "backend"
JD_DIR = ROOT / "JD"
OUT_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(BACKEND))

# Force skip LLM before importing pipeline pieces that read env at import time
import os

os.environ["RESUME_SKIP_LLM_WHEN_DETERMINISTIC"] = "true"
os.environ["JD_SKIP_LLM_WHEN_DETERMINISTIC"] = "true"
os.environ["DOCUMENT_INTELLIGENCE_SEMANTIC_AI"] = "false"  # no Ollama hang in batch
os.environ["OCR_ENABLED"] = "false"  # digital text only for batch speed/stability

from app.ai.document_intelligence import parse_jd_text_to_canonical
from app.ai.parser.text_extraction import extract_text_from_pdf_pymupdf, normalize_extracted_text


def parse_jd_deterministic(text: str):
    """Match production in-memory path (deterministic + repair), LLM forced off."""
    return parse_jd_text_to_canonical(text, max_workers=2)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def tokens(s: str) -> set[str]:
    stop = {"the", "and", "for", "with", "from", "job", "description", "jd", "role", "overview"}
    return {t for t in re.findall(r"[a-z0-9+#.]{2,}", norm(s)) if t not in stop}


def title_overlap(parsed: str, source: str, filename: str) -> float:
    p = tokens(parsed)
    if not p:
        return 0.0
    pool = tokens(source[:1000]) | tokens(Path(filename).stem)
    if not pool:
        return 0.0
    return len(p & pool) / max(1, len(p))


def value_in_source(value: str, source: str, min_len: int = 3):
    v = norm(value)
    if not v or len(v) < min_len:
        return None
    return v in norm(source)


def skills_precision(skills: list[str], source: str):
    if not skills:
        return 0.0, 0, 0
    src = norm(source)
    hit = checked = 0
    for sk in skills:
        s = norm(sk)
        if len(s) < 2:
            continue
        checked += 1
        if s in src or any(tok in src for tok in s.split() if len(tok) >= 4):
            hit += 1
    if checked == 0:
        return 0.0, 0, 0
    return hit / checked, hit, checked


def experience_plausible(exp_from: str, exp_to: str, source: str) -> dict:
    src = norm(source)
    years = re.findall(r"(\d+)\s*(?:\+|to|-|–|—)?\s*(?:years?|yrs?)", src)
    nums = [int(x) for x in years if x.isdigit()]
    result = {
        "parsed_from": exp_from,
        "parsed_to": exp_to,
        "source_year_mentions": sorted(set(nums))[:10],
        "ok": None,
    }
    try:
        pf = int(float(exp_from)) if exp_from not in (None, "") else None
        pt = int(float(exp_to)) if exp_to not in (None, "") else None
    except Exception:
        result["ok"] = False
        return result
    if pf is None and pt is None:
        return result
    if nums:
        candidates = [x for x in [pf, pt] if x is not None]
        result["ok"] = any(any(abs(c - n) <= 1 for n in nums) for c in candidates)
    return result


def expected_title_from_filename(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"\s*\(\d+\)\s*$", "", stem)
    stem = re.sub(r"(?i)[\s_-]*jd[\s_-]*", " ", stem)
    stem = re.sub(r"(?i)job\s*description", " ", stem)
    return re.sub(r"\s+", " ", stem).strip(" -_")


def avg(xs):
    return round(sum(xs) / len(xs), 3) if xs else 0.0


def main():
    files = sorted(JD_DIR.glob("*.pdf"))
    print(f"Found {len(files)} PDFs in {JD_DIR}", flush=True)

    results = []
    summary = {
        "total_files": len(files),
        "parsed_ok": 0,
        "parsed_fail": 0,
        "empty_title": 0,
        "empty_skills": 0,
        "empty_description": 0,
        "mode": "canonical_deterministic_plus_repair_no_llm_no_ocr",
    }
    title_scores, skill_scores, loc_hits, exp_hits, fname_title_hits = [], [], [], [], []
    coverage_gap_total = 0
    coverage_recovered_total = 0

    for idx, f in enumerate(files, 1):
        item = {
            "file": f.name,
            "size": f.stat().st_size,
            "status": "ok",
            "error": None,
            "text_chars": 0,
            "elapsed_sec": 0,
            "form": {},
            "checks": {},
            "expected": {"title_from_filename": expected_title_from_filename(f.name)},
        }
        t0 = time.time()
        print(f"\n[{idx}/{len(files)}] {f.name}", flush=True)
        try:
            data = f.read_bytes()
            text = normalize_extracted_text(extract_text_from_pdf_pymupdf(data) or "")
            item["text_chars"] = len(text)
            print(f"  extracted {len(text)} chars", flush=True)
            if len(text.strip()) < 30:
                item["status"] = "thin_text"
                item["error"] = f"Only {len(text.strip())} chars extracted (OCR disabled)"
                summary["parsed_fail"] += 1
                item["elapsed_sec"] = round(time.time() - t0, 2)
                results.append(item)
                print(f"  FAIL thin_text", flush=True)
                continue

            _profile, form, toon = parse_jd_deterministic(text)
            autofill = form.to_autofill_dict()
            compact = {
                "title": autofill.get("title") or "",
                "company": autofill.get("company") or "",
                "location": autofill.get("location") or "",
                "salary": autofill.get("salary") or "",
                "experienceFrom": autofill.get("experienceFrom") or "",
                "experienceTo": autofill.get("experienceTo") or "",
                "employmentType": autofill.get("employmentType") or "",
                "mandatorySkills": autofill.get("mandatorySkills") or [],
                "preferredSkills": autofill.get("preferredSkills") or [],
                "skillsList": autofill.get("_skills") or [],
                "responsibilities": (autofill.get("_responsibilities") or [])[:12],
                "qualifications": (autofill.get("_qualifications") or [])[:8],
                "descriptionPreview": (autofill.get("description") or "")[:500],
                "descriptionLen": len(autofill.get("description") or ""),
                "coverage": autofill.get("coverage") or [],
            }
            item["form"] = compact

            all_skills = list(
                dict.fromkeys(
                    (compact["mandatorySkills"] or [])
                    + (compact["preferredSkills"] or [])
                    + (compact["skillsList"] or [])
                )
            )
            t_overlap = title_overlap(compact["title"], text, f.name)
            expected_title = item["expected"]["title_from_filename"]
            fname_overlap = title_overlap(compact["title"], expected_title, f.name) if compact["title"] else 0.0
            sk_prec, sk_hit, sk_n = skills_precision(all_skills[:25], text)
            loc_ok = value_in_source(compact["location"], text) if compact["location"] else None
            company_ok = value_in_source(compact["company"], text) if compact["company"] else None
            exp = experience_plausible(compact["experienceFrom"], compact["experienceTo"], text)
            cov = compact.get("coverage") or []
            missing_ev = [c for c in cov if isinstance(c, dict) and c.get("status") == "missing_with_evidence"]
            recovered = [c for c in cov if isinstance(c, dict) and c.get("status") == "recovered"]
            from app.ai.parser.enrichment.jd_text_inference import skills_look_skill_like

            item["checks"] = {
                "title_overlap_source": round(t_overlap, 3),
                "title_overlap_filename": round(fname_overlap, 3),
                "title_present": bool(compact["title"]),
                "skills_precision": round(sk_prec, 3),
                "skills_hit": sk_hit,
                "skills_checked": sk_n,
                "skills_count": len(all_skills),
                "skills_look_skill_like": skills_look_skill_like(all_skills),
                "location_in_source": loc_ok,
                "company_in_source": company_ok,
                "experience": exp,
                "has_description": compact["descriptionLen"] >= 40,
                "coverage_missing_with_evidence": [c.get("field") for c in missing_ev],
                "coverage_recovered": [c.get("field") for c in recovered],
                "source_preview": text[:600].replace("\n", " | "),
            }

            summary["parsed_ok"] += 1
            if not compact["title"]:
                summary["empty_title"] += 1
            if not all_skills:
                summary["empty_skills"] += 1
            if compact["descriptionLen"] < 40:
                summary["empty_description"] += 1
            title_scores.append(t_overlap)
            fname_title_hits.append(fname_overlap)
            if sk_n:
                skill_scores.append(sk_prec)
            if loc_ok is not None:
                loc_hits.append(1.0 if loc_ok else 0.0)
            if exp["ok"] is not None:
                exp_hits.append(1.0 if exp["ok"] else 0.0)
            coverage_gap_total += len(missing_ev)
            coverage_recovered_total += len(recovered)

            safe = re.sub(r"[^\w.\-]+", "_", f.stem)[:90]
            (OUT_DIR / f"{safe}.json").write_text(
                json.dumps(
                    {
                        "file": f.name,
                        "expected": item["expected"],
                        "form": compact,
                        "checks": item["checks"],
                        "toon_preview": str(toon)[:1500],
                        "source_preview": text[:2500],
                    },
                    indent=2,
                    default=str,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            def _safe(s: str) -> str:
                return (s or "").encode("ascii", "replace").decode("ascii")

            print(
                f"  OK title={_safe(compact['title'])!r} loc={_safe(compact['location'])!r} "
                f"skills={len(all_skills)} exp={compact['experienceFrom']}-{compact['experienceTo']} "
                f"title_ov={t_overlap:.2f} skillP={sk_prec:.2f}",
                flush=True,
            )
        except Exception as e:
            item["status"] = "error"
            item["error"] = f"{type(e).__name__}: {e}"
            item["traceback"] = traceback.format_exc()[-1500:]
            summary["parsed_fail"] += 1
            print(f"  ERROR {item['error']}".encode("ascii", "replace").decode("ascii"), flush=True)

        item["elapsed_sec"] = round(time.time() - t0, 2)
        results.append(item)

    summary.update(
        {
            "title_overlap_avg": avg(title_scores),
            "title_vs_filename_avg": avg(fname_title_hits),
            "skills_precision_avg": avg(skill_scores),
            "location_in_source_rate": avg(loc_hits),
            "experience_ok_rate": avg(exp_hits),
            "coverage_missing_with_evidence_total": coverage_gap_total,
            "coverage_recovered_total": coverage_recovered_total,
        }
    )

    issues = []
    for r in results:
        if r["status"] != "ok":
            issues.append({"file": r["file"], "issue": r["status"], "detail": r.get("error")})
            continue
        c, form = r["checks"], r["form"]
        if not form.get("title"):
            issues.append({"file": r["file"], "issue": "missing_title", "detail": c.get("source_preview", "")[:200]})
        elif c.get("title_overlap_source", 0) < 0.25 and c.get("title_overlap_filename", 0) < 0.25:
            issues.append(
                {
                    "file": r["file"],
                    "issue": "weak_title_match",
                    "detail": f"parsed={form.get('title')!r} expected~{r['expected']['title_from_filename']!r}",
                }
            )
        if c.get("skills_count", 0) == 0:
            issues.append({"file": r["file"], "issue": "missing_skills", "detail": None})
        elif c.get("skills_precision", 1) < 0.5:
            issues.append(
                {
                    "file": r["file"],
                    "issue": "low_skills_precision",
                    "detail": f"{c.get('skills_hit')}/{c.get('skills_checked')}",
                }
            )
        # Reject garbage / letter-bullet skill tokens
        skills_list = list(form.get("mandatorySkills") or []) + list(form.get("skillsList") or [])
        garbage = [
            s
            for s in skills_list
            if isinstance(s, str)
            and (
                s.strip().lower() in {"job", "jd", "role", "skills", "education"}
                or re.match(r"^[oO]\s+", s.strip())
            )
        ]
        if garbage:
            issues.append(
                {
                    "file": r["file"],
                    "issue": "garbage_skills",
                    "detail": garbage[:8],
                }
            )
        if not c.get("skills_look_skill_like", True) and c.get("skills_count", 0) > 0:
            issues.append(
                {
                    "file": r["file"],
                    "issue": "skills_not_skill_like",
                    "detail": skills_list[:8],
                }
            )
        # Core coverage gaps are hard failures for acceptance
        core_missing = [
            f
            for f in (c.get("coverage_missing_with_evidence") or [])
            if f in {"title", "location", "experience", "skills", "description"}
        ]
        if core_missing:
            issues.append(
                {
                    "file": r["file"],
                    "issue": "core_coverage_missing_with_evidence",
                    "detail": core_missing,
                }
            )
        if c.get("location_in_source") is False:
            issues.append({"file": r["file"], "issue": "location_not_in_source", "detail": form.get("location")})
        if (c.get("experience") or {}).get("ok") is False:
            issues.append({"file": r["file"], "issue": "experience_mismatch", "detail": c.get("experience")})
        if not c.get("has_description"):
            issues.append({"file": r["file"], "issue": "thin_description", "detail": f"len={form.get('descriptionLen')}"})
        if c.get("coverage_missing_with_evidence"):
            issues.append(
                {
                    "file": r["file"],
                    "issue": "coverage_missing_with_evidence",
                    "detail": c.get("coverage_missing_with_evidence"),
                }
            )

    report = {"summary": summary, "issues": issues, "results": results}
    (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2, default=str, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# JD Parse Evaluation Report",
        "",
        f"- Mode: `{summary['mode']}`",
        f"- Files: {summary['total_files']}",
        f"- Parsed OK: {summary['parsed_ok']}",
        f"- Failed/thin: {summary['parsed_fail']}",
        f"- Empty title: {summary['empty_title']}",
        f"- Empty skills: {summary['empty_skills']}",
        f"- Thin description: {summary['empty_description']}",
        f"- Avg title overlap vs source: {summary['title_overlap_avg']}",
        f"- Avg title overlap vs filename: {summary['title_vs_filename_avg']}",
        f"- Avg skills precision vs source: {summary['skills_precision_avg']}",
        f"- Location in-source rate: {summary['location_in_source_rate']}",
        f"- Experience plausibility rate: {summary['experience_ok_rate']}",
        f"- Coverage recovered (total field hits): {summary['coverage_recovered_total']}",
        f"- Coverage missing_with_evidence (total): {summary['coverage_missing_with_evidence_total']}",
        "",
        "## Per-file (parsed vs expected-from-filename)",
        "",
        "| File | Expected title | Parsed title | Loc | Exp | Skills | TitleΔ | SkillP | Status |",
        "|---|---|---|---|---|---:|---:|---:|---|",
    ]
    for r in results:
        form = r.get("form") or {}
        c = r.get("checks") or {}
        exp = ""
        if form.get("experienceFrom") or form.get("experienceTo"):
            exp = f"{form.get('experienceFrom', '')}-{form.get('experienceTo', '')}"
        lines.append(
            "| {file} | {exp_t} | {title} | {loc} | {exp} | {sk} | {td} | {sp} | {st} |".format(
                file=r["file"][:42],
                exp_t=(r.get("expected") or {}).get("title_from_filename", "")[:32],
                title=(form.get("title") or "")[:32],
                loc=(form.get("location") or "")[:18],
                exp=exp,
                sk=c.get("skills_count", ""),
                td=c.get("title_overlap_source", ""),
                sp=c.get("skills_precision", ""),
                st=r["status"],
            )
        )
    lines += ["", "## Issues", ""]
    if not issues:
        lines.append("None flagged.")
    else:
        for i in issues:
            lines.append(f"- **{i['file']}**: `{i['issue']}` — {i.get('detail')}")

    (OUT_DIR / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n=== SUMMARY ===", flush=True)
    print(json.dumps(summary, indent=2), flush=True)
    print(f"Issues: {len(issues)}", flush=True)
    print(f"Wrote {OUT_DIR / 'report.md'}", flush=True)


if __name__ == "__main__":
    main()
