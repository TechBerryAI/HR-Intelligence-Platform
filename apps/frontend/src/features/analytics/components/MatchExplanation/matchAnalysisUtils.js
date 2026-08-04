/**
 * Helpers for ATS match explanation UI — works with new structured fields
 * and falls back to legacy evaluation_report.skills_analysis.
 * Also filters junk skill tokens so old polluted analyses stay trustworthy.
 */

const SKILL_NOISE = new Set([
  'preferred qualifications', 'preferred qualification', 'preferred skills',
  'preferred skill', 'required skills', 'required skill', 'mandatory skills',
  'technical skills', 'primary skills', 'core skills', 'key skills',
  'bonus points', 'bonus point', 'experience level', 'soft skills',
  'soft skills & competencies', 'preferred candidate profile', 'candidate profile',
  'qualifications', 'requirements', 'responsibilities', 'nice to have',
  'nice-to-have', 'good to have', 'or related field', 'related field',
  'plus', 'and', 'for', 'the', 'with', 'from', 'into', 'onto', 'over',
  'under', 'management', 'leadership', 'communication', 'teamwork',
  'public', 'job', 'jobs', 'role', 'roles', 'etc', 'etc.', 'n/a', 'na',
  'none', 'other', 'others', 'various', 'including', 'such as',
  'years of experience', 'years experience', 'work experience',
  'information technology', 'computer science',
])

const CONNECTOR_ENDINGS = new Set(['for', 'with', 'and', 'or', 'of', 'to', 'in', 'on', 'at', 'by'])

/** Soft non-skill strength/gap phrases we still want to show as chips */
const ALLOWED_PHRASES = new Set([
  'experience aligns with role/domain',
  'education meets or exceeds requirements',
  'location compatible with role',
  'experience below or not clearly aligned with role',
  'education does not clearly meet stated qualifications',
  'location may not align with job location',
])

export function isDisplayableSkill(token) {
  const s = String(token || '').trim()
  if (!s || s.length < 2 || s.length > 48) return false
  const lower = s.toLowerCase()
  if (ALLOWED_PHRASES.has(lower)) return true
  if (SKILL_NOISE.has(lower)) return false
  const words = lower.split(/\s+/)
  if (words.length > 4) return false
  if (words.length === 1 && SKILL_NOISE.has(words[0])) return false
  if (words.length >= 2 && words.some((w) => w === 'plus' || w === 'seeking' || w === 'looking')) {
    return false
  }
  if (words.length && CONNECTOR_ENDINGS.has(words[words.length - 1])) return false
  if (/^(preferred|required|mandatory|bonus|nice)\b/i.test(s)) return false
  return true
}

export function filterSkillList(items) {
  if (typeof items === 'string') {
    items = items.split(',').map((s) => s.trim()).filter(Boolean)
  }
  if (!Array.isArray(items)) return []
  return items.map((s) => String(s || '').trim()).filter(isDisplayableSkill)
}

export function toChips(items) {
  const out = []
  const arr = Array.isArray(items)
    ? items
    : items && typeof items === 'object'
      ? Object.values(items)
      : []
  arr.forEach((item) => {
    const s = String(item).trim()
    if (!s) return
    const colon = s.indexOf(': ')
    if (colon !== -1) {
      s.slice(colon + 2)
        .split(',')
        .map((x) => x.trim())
        .filter(Boolean)
        .forEach((x) => out.push(x))
    } else {
      out.push(s)
    }
  })
  return filterSkillList(out)
}

function asSkillRows(items, status) {
  if (typeof items === 'string') {
    items = items.split(',').map((s) => s.trim()).filter(Boolean)
  }
  if (!Array.isArray(items)) return []
  return filterSkillList(items).map((skill) => ({ skill, status }))
}

function filterRequirementRows(rows) {
  if (!Array.isArray(rows)) return []
  return rows.filter((r) => r && isDisplayableSkill(r.skill)).map((r) => ({
    skill: String(r.skill).trim(),
    status: r.status === 'matched' ? 'matched' : 'missing',
  }))
}

/**
 * Normalize requirement_analysis from json_output (new) or skills_analysis (legacy).
 * Junk tokens from older parses are filtered out for display trust.
 * When filtering wipes the list, recover usable skills from strengths/gaps/analysis.
 */
export function getRequirementAnalysis(jsonOut = {}) {
  const skillsAnalysis = jsonOut?.evaluation_report?.skills_analysis ?? {}
  const storedPct = jsonOut?.mandatory_skills_match_pct ?? skillsAnalysis?.mandatory_skills_match_pct
  const threshold = 60

  const existing = jsonOut?.requirement_analysis
  let mandatory = []
  let preferred = []
  let gateBase = null
  let filteredNoise = false

  if (existing && (Array.isArray(existing.mandatory) || Array.isArray(existing.preferred))) {
    mandatory = filterRequirementRows(existing.mandatory)
    preferred = filterRequirementRows(existing.preferred)
    gateBase = existing.gate || null
    filteredNoise = (existing.mandatory || []).length > mandatory.length
  } else {
    const matchedMand =
      skillsAnalysis.mandatory_matched_skills ||
      (Array.isArray(skillsAnalysis.skills_matched) ? skillsAnalysis.skills_matched : [])
    const missingMand = skillsAnalysis.missing_mandatory_skills || []
    const matchedPref = skillsAnalysis.preferred_matched_skills || []
    const missingPref = skillsAnalysis.missing_preferred_skills || []

    const mandMatched = asSkillRows(
      Array.isArray(skillsAnalysis.mandatory_matched_skills)
        ? skillsAnalysis.mandatory_matched_skills
        : matchedMand.filter((s) => !missingMand.includes(s) && !missingPref.includes(s)),
      'matched',
    )
    const mandMissing = asSkillRows(missingMand, 'missing')
    preferred = [...asSkillRows(matchedPref, 'matched'), ...asSkillRows(missingPref, 'missing')]
    mandatory = [...mandMatched, ...mandMissing]
    filteredNoise = (missingMand.length + matchedMand.length) > mandatory.length
  }

  // Recover from chips when checklist emptied by noise filter
  if (!mandatory.length) {
    const recovered = recoverSkillsFromLegacy(jsonOut)
    mandatory = recovered.mandatory
    if (!preferred.length) preferred = recovered.preferred
    if (recovered.mandatory.length) filteredNoise = true
  }

  const matched = mandatory.filter((r) => r.status === 'matched').length
  const total = mandatory.length
  const cleanedPct = total > 0
    ? Math.round((1000 * matched) / total) / 10
    : (storedPct != null ? Number(storedPct) : gateBase?.mandatory_pct)
  const pct = cleanedPct != null ? Number(cleanedPct) : null
  const defined = total > 0 || (pct != null && Number.isFinite(pct))
  const passed = !defined ? true : Number(pct) >= (gateBase?.threshold || threshold)

  return {
    mandatory,
    preferred,
    gate: {
      passed,
      mandatory_pct: pct,
      threshold: gateBase?.threshold || threshold,
      mandatory_defined: defined,
    },
    filtered_noise: filteredNoise,
  }
}

function recoverSkillsFromLegacy(jsonOut = {}) {
  const skillsAnalysis = jsonOut?.evaluation_report?.skills_analysis ?? {}
  const strengths = toChips(jsonOut?.key_strengths || [])
  const gaps = toChips(jsonOut?.key_gaps || [])
  // Drop soft non-skill phrases from strength/gap chips for the skill board
  const soft = ALLOWED_PHRASES
  const present = strengths.filter((s) => !soft.has(String(s).toLowerCase()))
  const missingFromGaps = gaps.filter((s) => !soft.has(String(s).toLowerCase()))

  const matchedFromAnalysis = filterSkillList(
    skillsAnalysis.mandatory_matched_skills
      || skillsAnalysis.skills_matched
      || [],
  )
  const missingFromAnalysis = filterSkillList(skillsAnalysis.missing_mandatory_skills || [])
  const prefMatched = filterSkillList(skillsAnalysis.preferred_matched_skills || [])
  const prefMissing = filterSkillList(skillsAnalysis.missing_preferred_skills || [])

  const matched = [...new Set([...matchedFromAnalysis, ...present])]
  const missing = [...new Set([...missingFromAnalysis, ...missingFromGaps])]
    .filter((s) => !matched.some((m) => m.toLowerCase() === s.toLowerCase()))

  return {
    mandatory: [
      ...matched.map((skill) => ({ skill, status: 'matched' })),
      ...missing.map((skill) => ({ skill, status: 'missing' })),
    ],
    preferred: [
      ...prefMatched.map((skill) => ({ skill, status: 'matched' })),
      ...prefMissing.map((skill) => ({ skill, status: 'missing' })),
    ],
  }
}

function statusLabel(status) {
  if (status === 'match') return 'Matched'
  if (status === 'partial') return 'Partial'
  if (status === 'unclear') return 'Unclear'
  return 'Not matched'
}

function scoreToStatus(score, matchAt, partialAt) {
  const n = Number(score)
  if (n >= matchAt) return 'match'
  if (n >= partialAt) return 'partial'
  return 'missing'
}

function firstNonEmpty(...lists) {
  for (const list of lists) {
    const clean = (Array.isArray(list) ? list : [])
      .map((x) => String(x || '').trim())
      .filter(Boolean)
    if (clean.length) return clean
  }
  return []
}

function buildEducationComparison(eduText, eduCat, score) {
  const text = String(eduText || eduCat?.reason || '').trim()
  const noDegree = /no degree requirement/i.test(text)
  const neededFromCat = firstNonEmpty(eduCat?.needed)
  const presentFromCat = firstNonEmpty(eduCat?.present)
  const status = scoreToStatus(score, 80, 40)

  if (noDegree) {
    return {
      status: 'match',
      rows: [{
        needed: 'No degree / qualification required',
        present: 'Not required — passes by default',
        status: 'match',
        label: 'Matched',
      }],
      reason: 'Role did not state a degree requirement, so education is a full match.',
    }
  }

  if (/Degree required; no education/i.test(text)) {
    return {
      status: 'missing',
      rows: [{
        needed: neededFromCat[0] || 'Degree or equivalent qualification',
        present: 'No education listed on resume',
        status: 'missing',
        label: 'Not matched',
      }],
      reason: text,
    }
  }

  if (/meets or exceeds|education meets/i.test(text)) {
    return {
      status: 'match',
      rows: [{
        needed: neededFromCat[0] || 'Degree / qualification as stated in the job',
        present: presentFromCat[0] || 'Degree or equivalent evidenced on resume',
        status: 'match',
        label: 'Matched',
      }],
      reason: text || 'Candidate education meets the stated requirements.',
    }
  }

  if (/does not clearly meet/i.test(text)) {
    return {
      status: 'partial',
      rows: [{
        needed: neededFromCat[0] || 'Degree / qualification as stated in the job',
        present: presentFromCat[0] || 'Education listed, but fit to the requirement is unclear',
        status: 'partial',
        label: 'Partial',
      }],
      reason: text,
    }
  }

  return {
    status,
    rows: [{
      needed: neededFromCat[0] || (text ? text.split('.')[0] : 'Education requirements for the role'),
      present: presentFromCat[0] || (status === 'match' ? 'Meets stated requirements' : status === 'partial' ? 'Partly evidenced on resume' : 'Not clearly evidenced on resume'),
      status,
      label: statusLabel(status),
    }],
    reason: eduCat?.reason || text || `Education scored ${score}% based on role requirements.`,
  }
}

function buildLocationComparison(locCat, score) {
  const needed = firstNonEmpty(locCat?.needed)[0]
  const present = firstNonEmpty(locCat?.present)[0]
  const status = scoreToStatus(score, 70, 40)
  if (!needed) {
    return {
      status: 'match',
      rows: [{
        needed: 'No specific location requirement',
        present: present || 'Not required — passes by default',
        status: 'match',
        label: 'Matched',
      }],
      reason: locCat?.reason || 'Role did not state a location requirement, so location is a match.',
    }
  }
  return {
    status,
    rows: [{
      needed: `Work from / based in: ${needed}`,
      present: present
        || (status === 'match' ? 'Compatible location on resume' : status === 'partial' ? 'Location only partly clear' : 'No compatible location found'),
      status,
      label: statusLabel(status),
    }],
    reason: locCat?.reason,
  }
}

function buildExperienceComparison(exp, expCat, score) {
  const neededTitle = firstNonEmpty(expCat?.needed)[0]
  const presentSummary = exp?.relevant_experience_summary
    || firstNonEmpty(expCat?.present)[0]
    || '—'
  const expGaps = exp?.gaps_vs_role_expectations && exp.gaps_vs_role_expectations !== 'N/A'
    ? exp.gaps_vs_role_expectations
    : ''
  const status = scoreToStatus(score, 70, 40)
  const rows = [
    {
      needed: neededTitle
        ? `Experience relevant to “${neededTitle}”`
        : 'Relevant experience for the role',
      present: presentSummary,
      status,
      label: statusLabel(status),
    },
  ]
  if (expGaps) {
    rows.push({
      needed: 'Experience gaps to watch',
      present: expGaps,
      status: 'partial',
      label: 'Note',
    })
  }
  return { status, rows, reason: expCat?.reason }
}

/**
 * Premium comparison boards for skills / experience / education / location.
 */
export function getComparisonBoard(jsonOut = {}, { score } = {}) {
  const reconciled = withReconciledScores(jsonOut, { storedScore: score })
  jsonOut = reconciled.jsonOut
  score = reconciled.score
  const explanation = getDecisionExplanation(jsonOut, { score })
  const req = getRequirementAnalysis(jsonOut)
  const breakdown = reconciled.recon.score_breakdown || jsonOut?.score_breakdown || {}
  const evalReport = jsonOut?.evaluation_report || {}
  const exp = evalReport.experience_assessment || {}
  const eduText = String(evalReport.education_certification_assessment || '').trim()
  const skillsCat = (explanation.category_reasons || []).find((c) => c.key === 'skills')
  const expCat = (explanation.category_reasons || []).find((c) => c.key === 'experience')
  const eduCat = (explanation.category_reasons || []).find((c) => c.key === 'education')
  const locCat = (explanation.category_reasons || []).find((c) => c.key === 'location')

  const skillRows = (req.mandatory || []).map((r) => ({
    needed: r.skill,
    present: r.status === 'matched' ? r.skill : '—',
    status: r.status === 'matched' ? 'match' : 'missing',
    label: r.status === 'matched' ? 'Matched' : 'Not matched',
  }))
  const preferredRows = (req.preferred || []).map((r) => ({
    needed: r.skill,
    present: r.status === 'matched' ? r.skill : '—',
    status: r.status === 'matched' ? 'match' : 'missing',
    label: r.status === 'matched' ? 'Matched' : 'Not matched',
    tier: 'preferred',
  }))

  const gate = req.gate || {}
  const gateFailed = Boolean(gate.mandatory_defined) && Number(gate.mandatory_pct) < (gate.threshold || 60)
  const matchedCount = skillRows.filter((r) => r.status === 'match').length
  const missingCount = skillRows.filter((r) => r.status === 'missing').length

  let skillsResult = 'unclear'
  let skillsLabel = 'Checklist unavailable'
  let skillsReason = skillsCat?.reason
  if (skillRows.length) {
    if (!matchedCount) {
      skillsResult = 'not_match'
      skillsLabel = 'Not a skills match'
    } else if (missingCount) {
      skillsResult = gateFailed ? 'not_match' : 'partial'
      skillsLabel = gateFailed ? 'Skills below gate' : 'Partial skills match'
    } else {
      skillsResult = 'match'
      skillsLabel = 'Skills match'
    }
    skillsReason = skillsCat?.reason && skillsCat.result !== 'unclear'
      ? skillsCat.reason
      : (
        missingCount
          ? `Role needed ${skillRows.length} mandatory skill(s). Present: ${skillRows.filter((r) => r.status === 'match').map((r) => r.needed).slice(0, 8).join(', ') || 'none'}. Missing: ${skillRows.filter((r) => r.status === 'missing').map((r) => r.needed).slice(0, 8).join(', ')}.`
          : `Candidate has all ${skillRows.length} mandatory skill(s) on the checklist.`
      )
  } else if (skillsCat) {
    skillsResult = skillsCat.result || 'unclear'
    skillsLabel = skillsCat.result_label || skillsLabel
  }

  const experience = buildExperienceComparison(exp, expCat, breakdown.experience)
  const education = buildEducationComparison(eduText, eduCat, breakdown.education)
  const location = buildLocationComparison(locCat, breakdown.location)

  return {
    explanation,
    scoreReconciliation: reconciled.recon,
    displayScore: reconciled.score,
    displayVerdict: reconciled.verdict,
    skills: {
      score: breakdown.skills,
      result: skillsResult,
      result_label: skillsLabel,
      reason: skillsReason,
      gate,
      gateFailed,
      rows: skillRows,
      preferredRows,
      matchedCount,
      missingCount,
    },
    experience: {
      score: breakdown.experience,
      result: expCat?.result || experience.status,
      result_label: expCat?.result_label || (
        experience.status === 'match' ? 'Experience match'
          : experience.status === 'partial' ? 'Partial experience match'
            : 'Experience not a match'
      ),
      reason: experience.reason,
      rows: experience.rows,
    },
    education: {
      score: breakdown.education,
      result: education.status === 'missing' ? 'not_match' : (eduCat?.result || education.status),
      result_label: eduCat?.result_label || (
        education.status === 'match' ? 'Education match'
          : education.status === 'partial' ? 'Partial education match'
            : 'Education not a match'
      ),
      reason: education.reason,
      rows: education.rows,
    },
    location: {
      score: breakdown.location,
      result: locCat?.result || location.status,
      result_label: locCat?.result_label || (
        location.status === 'match' ? 'Location match'
          : location.status === 'partial' ? 'Partial location match'
            : 'Location not a match'
      ),
      reason: location.reason,
      rows: location.rows,
    },
  }
}

const WEIGHTS = { skills: 60, experience: 25, education: 10, location: 5 }

/**
 * Recalculate skills + overall when the cleaned checklist no longer matches
 * the stored (often polluted) skills score. Keeps experience/education/location.
 */
export function reconcileMatchScores(jsonOut = {}, { storedScore } = {}) {
  const req = getRequirementAnalysis(jsonOut)
  const storedBreakdown = jsonOut?.score_breakdown || {}
  const mand = req.mandatory || []
  const pref = req.preferred || []
  const storedSkills = Number(storedBreakdown.skills)
  const exp = Number(storedBreakdown.experience ?? 0)
  const edu = Number(storedBreakdown.education ?? 0)
  const loc = Number(storedBreakdown.location ?? 0)
  const originalOverall = storedScore != null
    ? Number(storedScore)
    : Number(jsonOut?.overall_match_score ?? jsonOut?.final_score)

  let skillsScore = Number.isFinite(storedSkills) ? storedSkills : 0
  let adjusted = false

  if (mand.length > 0 || pref.length > 0) {
    const mandPct = mand.length
      ? (100 * mand.filter((r) => r.status === 'matched').length) / mand.length
      : 100
    const prefPct = pref.length
      ? (100 * pref.filter((r) => r.status === 'matched').length) / pref.length
      : 100
    // Same blend as backend: mandatory 40 and preferred 20 within the 60% skills bucket
    const wm = mand.length ? 40 / 60 : 0
    const wp = pref.length ? 20 / 60 : 0
    const cleanedSkills = Math.round(((wm * mandPct + wp * prefPct) / (wm + wp)) * 10) / 10
    const diverges = !Number.isFinite(storedSkills) || Math.abs(cleanedSkills - storedSkills) >= 5
    if (req.filtered_noise || diverges) {
      skillsScore = cleanedSkills
      adjusted = Math.abs(cleanedSkills - (Number.isFinite(storedSkills) ? storedSkills : 0)) >= 1
    }
  }

  const overall = Math.round((skillsScore * 0.6 + exp * 0.25 + edu * 0.1 + loc * 0.05) * 10) / 10
  const gate = req.gate || {}
  const gateFailed = Boolean(gate.mandatory_defined) && Number(gate.mandatory_pct) < (gate.threshold || 60)

  let verdict = 'Not a Match'
  if (!gateFailed) {
    if (overall >= 75) verdict = 'Strong Match'
    else if (overall >= 60) verdict = 'Potential Match (Recruiter Review)'
  }

  if (!adjusted && Number.isFinite(originalOverall) && Math.abs(overall - originalOverall) < 1) {
    return {
      adjusted: false,
      score_breakdown: {
        skills: Number.isFinite(storedSkills) ? storedSkills : skillsScore,
        experience: exp,
        education: edu,
        location: loc,
      },
      overall_match_score: Number.isFinite(originalOverall) ? originalOverall : overall,
      display_score: Math.round(Number.isFinite(originalOverall) ? originalOverall : overall),
      verdict: (jsonOut?.verdict || '').trim() || verdict,
      gate,
      note: null,
      original_skills: storedSkills,
      original_overall: originalOverall,
    }
  }

  return {
    adjusted,
    score_breakdown: {
      skills: skillsScore,
      experience: exp,
      education: edu,
      location: loc,
    },
    overall_match_score: overall,
    display_score: Math.round(overall),
    verdict,
    gate,
    note: adjusted
      ? `Skills were recalculated from the cleaned checklist (${skillsScore}% vs stored ${Number.isFinite(storedSkills) ? storedSkills : '—'}%). Overall moved from ${Number.isFinite(originalOverall) ? Math.round(originalOverall) : '—'}% to ${Math.round(overall)}%.`
      : null,
    original_skills: storedSkills,
    original_overall: originalOverall,
  }
}

/**
 * Return a display-ready analysis copy with reconciled scores/verdict so the UI
 * never says “all skills matched” while still showing a polluted 20% skills score.
 */
export function withReconciledScores(jsonOut = {}, { storedScore } = {}) {
  const recon = reconcileMatchScores(jsonOut, { storedScore })
  if (!recon.adjusted) {
    return { jsonOut, recon, score: recon.display_score, verdict: recon.verdict }
  }
  const {
    decision_explanation: _dropExplain,
    decision_summary: _dropSummary,
    ...rest
  } = jsonOut || {}
  const displayJson = {
    ...rest,
    score_breakdown: recon.score_breakdown,
    overall_match_score: recon.overall_match_score,
    final_score: recon.overall_match_score,
    verdict: recon.verdict,
    mandatory_skills_match_pct: recon.gate?.mandatory_pct,
    // Keep requirement_analysis / skills evidence; force explanation rebuild
    category_reasons: Array.isArray(jsonOut?.category_reasons)
      ? jsonOut.category_reasons.map((cat) => (
        cat?.key === 'skills'
          ? { ...cat, score: recon.score_breakdown.skills }
          : cat
      ))
      : jsonOut?.category_reasons,
  }
  return {
    jsonOut: displayJson,
    recon,
    score: recon.display_score,
    verdict: recon.verdict,
  }
}

/**
 * Single source for displaying an application's match score everywhere
 * (tables, cards, detail). Uses reconciled analysis when present so UI
 * never shows a stale polluted score next to a cleaned checklist.
 */
export function getApplicationDisplayMatch(application = {}) {
  const analysis =
    application.ats_analysis
    || application.atsAnalysis
    || null
  const rawJson = analysis && typeof analysis === 'object'
    ? (analysis.json_output ?? analysis)
    : {}
  const storedRaw =
    application.match_score ?? application.matchScore ?? application.score ?? null
  const storedScore = storedRaw != null && storedRaw !== ''
    ? Math.round(Number(storedRaw))
    : null
  if (!rawJson || typeof rawJson !== 'object' || !Object.keys(rawJson).length) {
    return {
      score: storedScore,
      verdict: application.verdict || null,
      adjusted: false,
      note: null,
    }
  }
  const { score, verdict, recon } = withReconciledScores(rawJson, { storedScore })
  return {
    score: score != null ? score : storedScore,
    verdict: verdict || application.verdict || null,
    adjusted: Boolean(recon?.adjusted),
    note: recon?.note || null,
  }
}

function refreshSkillsCategory(category_reasons, req, jsonOut, ctx) {
  const matched = ctx.matched || []
  const missing = ctx.missing || []
  if (!matched.length && !missing.length) return category_reasons || []
  const rebuilt = buildCategoryReasonsFromLegacy(jsonOut, req, ctx)
  const freshSkills = rebuilt.find((c) => c.key === 'skills')
  if (!Array.isArray(category_reasons) || !category_reasons.length) return rebuilt
  return category_reasons.map((cat) => {
    if (cat.key !== 'skills' || !freshSkills) return cat
    const hadCleanNeeded = filterSkillList(cat.needed || []).length > 0
    if (cat.result === 'unclear' || !hadCleanNeeded) return freshSkills
    return {
      ...cat,
      needed: filterSkillList(cat.needed).length ? filterSkillList(cat.needed) : freshSkills.needed,
      present: filterSkillList(cat.present).length ? filterSkillList(cat.present) : freshSkills.present,
      missing: filterSkillList(cat.missing).length ? filterSkillList(cat.missing) : freshSkills.missing,
    }
  })
}

/**
 * Build transparent decision explanation for UI — prefers backend payload,
 * otherwise reconstructs from score breakdown so older applications still read clearly.
 */
export function getDecisionExplanation(jsonOut = {}, { score } = {}) {
  const reconciled = withReconciledScores(jsonOut, { storedScore: score })
  jsonOut = reconciled.jsonOut
  if (score == null || reconciled.recon?.adjusted) score = reconciled.score
  const existing = jsonOut?.decision_explanation
  if (existing && existing.primary_reason) {
    const req = getRequirementAnalysis(jsonOut)
    const matched = (req.mandatory || []).filter((r) => r.status === 'matched').map((r) => r.skill)
    const missing = (req.mandatory || []).filter((r) => r.status === 'missing').map((r) => r.skill)
    const gateFailed = req.gate?.mandatory_defined && Number(req.gate?.mandatory_pct) < (req.gate?.threshold || 60)
    const baseReasons = Array.isArray(existing.category_reasons) && existing.category_reasons.length
      ? existing.category_reasons
      : (Array.isArray(jsonOut?.category_reasons) && jsonOut.category_reasons.length
        ? jsonOut.category_reasons
        : buildCategoryReasonsFromLegacy(jsonOut, req, {
          matched,
          missing,
          gateFailed,
          breakdown: jsonOut?.score_breakdown || {},
        }))
    const category_reasons = refreshSkillsCategory(baseReasons, req, jsonOut, {
      matched,
      missing,
      gateFailed,
      breakdown: jsonOut?.score_breakdown || {},
    })
    const skills_evidence = {
      ...(existing.skills_evidence || {}),
      mandatory_matched: matched,
      mandatory_missing: missing,
      preferred_matched: (req.preferred || []).filter((r) => r.status === 'matched').map((r) => r.skill),
      preferred_missing: (req.preferred || []).filter((r) => r.status === 'missing').map((r) => r.skill),
      mandatory_match_pct: req.gate?.mandatory_pct ?? existing.skills_evidence?.mandatory_match_pct,
      gate_threshold: req.gate?.threshold || 60,
      gate_passed: !gateFailed,
      comparisons: [
        ...matched.map((s) => ({ skill: s, status: 'present', present: true, needed: true })),
        ...missing.map((s) => ({ skill: s, status: 'missing', present: false, needed: true })),
      ],
    }
    return {
      ...existing,
      category_reasons,
      skills_evidence,
      score_math: existing.score_math || jsonOut?.score_math || buildScoreMathFromBreakdown(jsonOut, score),
    }
  }

  const breakdown = jsonOut?.score_breakdown || {}
  const req = getRequirementAnalysis(jsonOut)
  const gate = req.gate || {}
  const verdict = (jsonOut?.verdict || '').trim()
  const overall = score != null ? score : Number(jsonOut?.overall_match_score ?? jsonOut?.final_score ?? 0)
  const missing = (req.mandatory || []).filter((r) => r.status === 'missing').map((r) => r.skill)
  const matched = (req.mandatory || []).filter((r) => r.status === 'matched').map((r) => r.skill)
  const gateFailed = gate.mandatory_defined && Number(gate.mandatory_pct) < (gate.threshold || 60)

  let outcome = 'reject'
  let outcome_label = 'Not selected'
  if (/strong match/i.test(verdict)) {
    outcome = 'shortlist'
    outcome_label = 'Auto-shortlist'
  } else if (/potential match/i.test(verdict)) {
    outcome = 'review'
    outcome_label = 'Recruiter review'
  }

  const what_happened = []
  let primary_reason = (jsonOut?.decision_summary || '').trim()
  if (gateFailed) {
    primary_reason = primary_reason || (
      missing.length
        ? `Rejected: only ${gate.mandatory_pct}% of mandatory skills matched (need at least ${gate.threshold || 60}%). Still missing: ${missing.slice(0, 5).join(', ')}.`
        : `Rejected: mandatory skills match is ${gate.mandatory_pct}% (below the ${gate.threshold || 60}% minimum).`
    )
    what_happened.push(
      `The mandatory skills gate failed at ${gate.mandatory_pct}% (need ${gate.threshold || 60}%), so the candidate is rejected even if experience or education look strong.`,
    )
    if (missing.length) {
      what_happened.push(`Missing mandatory skills that drove this decision: ${missing.slice(0, 8).join(', ')}.`)
    }
    if (matched.length) {
      what_happened.push(`Mandatory skills that did match: ${matched.slice(0, 8).join(', ')}.`)
    }
  } else if (outcome === 'shortlist') {
    primary_reason = primary_reason || `Selected for auto-shortlist at ${overall}%.`
    what_happened.push(`Gate passed and overall score ${overall}% meets the auto-shortlist bar.`)
  } else if (outcome === 'review') {
    primary_reason = primary_reason || `Hold for recruiter review at ${overall}%.`
    what_happened.push(`Gate passed but overall score ${overall}% is below the auto-shortlist bar.`)
  } else {
    primary_reason = primary_reason || `Rejected: overall score ${overall}% is below the match floor.`
    what_happened.push(`Overall score ${overall}% did not meet the minimum match threshold.`)
  }

  const expScore = Number(breakdown.experience)
  let reconciliation = ''
  if (expScore >= 70 && gateFailed) {
    reconciliation =
      `Experience scored ${expScore}% because the resume title/domain aligns with the role. ` +
      `That does not replace the skills checklist — mandatory skills still only matched ` +
      `${gate.mandatory_pct}%, so the gate fails and the candidate is not selected.`
  }

  const score_math = jsonOut?.score_math || buildScoreMathFromBreakdown(jsonOut, overall)
  const next_step = {
    shortlist: 'Move this candidate to the next hiring stage.',
    review: 'Review the missing skills below, then decide to shortlist or reject.',
    reject: 'Do not shortlist on ATS rules alone. Override only with clear hiring context outside this comparison.',
  }[outcome]

  const category_reasons = refreshSkillsCategory(
    Array.isArray(existing?.category_reasons) && existing.category_reasons.length
      ? existing.category_reasons
      : (Array.isArray(jsonOut?.category_reasons) && jsonOut.category_reasons.length
        ? jsonOut.category_reasons
        : buildCategoryReasonsFromLegacy(jsonOut, req, {
          overall,
          gateFailed,
          matched,
          missing,
          breakdown,
        })),
    req,
    jsonOut,
    { overall, gateFailed, matched, missing, breakdown },
  )

  return {
    outcome,
    outcome_label,
    verdict,
    primary_reason,
    what_happened,
    rules_applied: [
      'A candidate must have most mandatory skills (at least 60%) or they are not selected.',
      'Strong overall fit (75%+) with the skills gate passed → auto-shortlist.',
      'Decent overall fit (60–74%) with the skills gate passed → recruiter review.',
      'Below 60% overall, or skills gate failed → not a match.',
    ],
    score_math,
    category_reasons,
    skills_evidence: {
      mandatory_matched: matched,
      mandatory_missing: missing,
      preferred_matched: (req.preferred || []).filter((r) => r.status === 'matched').map((r) => r.skill),
      preferred_missing: (req.preferred || []).filter((r) => r.status === 'missing').map((r) => r.skill),
      mandatory_match_pct: gate.mandatory_pct,
      gate_threshold: gate.threshold || 60,
      gate_passed: !gateFailed,
      comparisons: [
        ...matched.map((s) => ({ skill: s, status: 'present', present: true, needed: true })),
        ...missing.map((s) => ({ skill: s, status: 'missing', present: false, needed: true })),
      ],
    },
    other_factors: {
      experience: {
        score: breakdown.experience,
        summary: jsonOut?.evaluation_report?.experience_assessment?.relevant_experience_summary || '',
      },
      education: {
        score: breakdown.education,
        summary: jsonOut?.evaluation_report?.education_certification_assessment || '',
      },
      location: { score: breakdown.location, summary: '' },
    },
    reconciliation,
    next_step,
  }
}

function buildCategoryReasonsFromLegacy(jsonOut, req, ctx) {
  const breakdown = jsonOut?.score_breakdown || {}
  const expSummary = jsonOut?.evaluation_report?.experience_assessment?.relevant_experience_summary || ''
  const eduSummary = jsonOut?.evaluation_report?.education_certification_assessment || ''
  const matched = ctx.matched || []
  const missing = ctx.missing || []
  const needed = [...matched, ...missing]
  const mandPct = req?.gate?.mandatory_pct
  const skillsScore = Number(breakdown.skills ?? 0)
  const expScore = Number(breakdown.experience ?? 0)
  const eduScore = Number(breakdown.education ?? 0)
  const locScore = Number(breakdown.location ?? 0)

  let skillsReason
  let skillsResult
  let skillsLabel
  if (!needed.length) {
    skillsResult = 'unclear'
    skillsLabel = 'No clear skill checklist'
    skillsReason = 'The job did not yield a clean mandatory skill checklist for item-by-item comparison.'
  } else if (missing.length && !matched.length) {
    skillsResult = 'not_match'
    skillsLabel = 'Not a skills match'
    skillsReason = `Role needed: ${needed.slice(0, 8).join(', ')}. Candidate had none of these on the resume.`
  } else if (missing.length) {
    skillsResult = 'partial'
    skillsLabel = 'Partial skills match'
    skillsReason = `Role needed these skills. Present: ${matched.slice(0, 8).join(', ') || 'none'}. Missing: ${missing.slice(0, 8).join(', ')}. That is a ${mandPct}% mandatory match${ctx.gateFailed ? ' (below the 60% minimum, so not selected)' : ''}.`
  } else {
    skillsResult = 'match'
    skillsLabel = 'Skills match'
    skillsReason = `Role needed: ${needed.slice(0, 8).join(', ')}. Candidate has all of them.`
  }

  return [
    {
      key: 'skills',
      label: 'Core skills',
      score: skillsScore,
      result: skillsResult,
      result_label: skillsLabel,
      needed,
      present: matched,
      missing,
      reason: skillsReason,
    },
    {
      key: 'experience',
      label: 'Experience',
      score: expScore,
      result: expScore >= 70 ? 'match' : expScore >= 40 ? 'partial' : 'not_match',
      result_label: expScore >= 70 ? 'Experience match' : expScore >= 40 ? 'Partial experience match' : 'Experience not a match',
      needed: [],
      present: expSummary ? [expSummary] : [],
      missing: [],
      reason: expScore >= 70
        ? `Role needed relevant experience. Present: ${expSummary || 'aligned experience'}. So experience is a match.`
        : `Role needed relevant experience. Present: ${expSummary || 'limited or unclear experience'}. So experience is only a partial/no match.`,
    },
    {
      key: 'education',
      label: 'Education',
      score: eduScore,
      result: eduScore >= 80 ? 'match' : eduScore >= 40 ? 'partial' : 'not_match',
      result_label: eduScore >= 80 ? 'Education match' : eduScore >= 40 ? 'Partial education match' : 'Education not a match',
      needed: /no degree requirement/i.test(eduSummary || '')
        ? ['No degree / qualification required']
        : (eduSummary ? [eduSummary.split('.')[0]] : []),
      present: /no degree requirement/i.test(eduSummary || '')
        ? ['Not required — passes by default']
        : (/meets or exceeds/i.test(eduSummary || '') ? ['Degree or equivalent evidenced on resume'] : []),
      missing: /no education data/i.test(eduSummary || '') ? ['No matching education on resume'] : [],
      reason: /no degree requirement/i.test(eduSummary || '')
        ? 'Role needed: no degree requirement stated. Nothing missing, so education is a match.'
        : (eduSummary || `Education scored ${eduScore}% based on the role requirements.`),
    },
    {
      key: 'location',
      label: 'Location',
      score: locScore,
      result: locScore >= 70 ? 'match' : locScore >= 40 ? 'partial' : 'not_match',
      result_label: locScore >= 70 ? 'Location match' : locScore >= 40 ? 'Partial location match' : 'Location not a match',
      needed: [],
      present: [],
      missing: [],
      reason: locScore >= 70
        ? 'Role location requirement is met (or none was stated), so location is a match.'
        : 'Role location and candidate location only partly align.',
    },
  ]
}

export function buildScoreMathFromBreakdown(jsonOut = {}, overallScore) {
  const breakdown = jsonOut?.score_breakdown || {}
  const table = jsonOut?.evaluation_report?.score_breakdown_table
  if (Array.isArray(table) && table.length) {
    const rows = table.map((row) => ({
      key: String(row.category || '').toLowerCase().includes('experience')
        ? 'experience'
        : String(row.category || '').toLowerCase().includes('education')
          ? 'education'
          : String(row.category || '').toLowerCase().includes('location')
            ? 'location'
            : 'skills',
      label: row.category,
      raw_pct: row.raw_score_pct,
      weight_pct: row.weight_pct,
      points: row.weighted_score,
      how: `${row.raw_score_pct}% × ${row.weight_pct}% weight`,
    }))
    const total = overallScore != null
      ? overallScore
      : Math.round(rows.reduce((sum, r) => sum + Number(r.points || 0), 0) * 10) / 10
    const parts = rows.map((r) => r.points).join(' + ')
    return {
      rows,
      total,
      equation: `${parts} = ${total}`,
      explainer: `Overall match score ${total}% = sum of weighted category points (${parts}).`,
    }
  }

  const rows = Object.entries(WEIGHTS).map(([key, weight]) => {
    const raw = Number(breakdown[key] ?? 0)
    const points = Math.round(raw * (weight / 100) * 100) / 100
    const labels = {
      skills: 'Core technical skills',
      experience: 'Relevant experience',
      education: 'Education / certifications',
      location: 'Location / availability',
    }
    return {
      key,
      label: labels[key],
      raw_pct: raw,
      weight_pct: weight,
      points,
      how: `${raw}% category score × ${weight}% weight`,
    }
  })
  const total = overallScore != null
    ? overallScore
    : Math.round(rows.reduce((sum, r) => sum + r.points, 0) * 10) / 10
  const parts = rows.map((r) => r.points).join(' + ')
  return {
    rows,
    total,
    equation: `${parts} = ${total}`,
    explainer: `Overall match score ${total}% = sum of weighted category points (${parts}). Each category is scored 0–100, then multiplied by its weight.`,
  }
}

export function getDecisionSummary(jsonOut = {}, { score, status, atsReasoning } = {}) {
  if (status === 'ats_failed') {
    return atsReasoning || 'ATS matching failed for this application.'
  }
  const explanation = getDecisionExplanation(jsonOut, { score })
  if (explanation?.primary_reason) return explanation.primary_reason

  const summary = (jsonOut?.decision_summary || '').trim()
  if (summary && !/preferred qualifications|,\s*plus\b/i.test(summary)) return summary

  const req = getRequirementAnalysis(jsonOut)
  const missing = (req.mandatory || [])
    .filter((r) => r.status === 'missing')
    .map((r) => r.skill)
    .slice(0, 5)
  const mandatoryPct = req.gate?.mandatory_pct ?? jsonOut?.mandatory_skills_match_pct
  const verdict = (jsonOut?.verdict || '').trim()

  if (mandatoryPct != null && Number(mandatoryPct) < 60) {
    const extra = missing.length ? ` Still missing: ${missing.join(', ')}.` : ''
    return `Rejected: only ${Number(mandatoryPct)}% of mandatory skills matched (need at least 60%).${extra}`
  }
  if (verdict && /not a match/i.test(verdict) && score != null) {
    return `Rejected: overall score is ${score}%, below the required threshold for this role.`
  }
  if (verdict && /strong match/i.test(verdict) && score != null) {
    return `Selected for auto-shortlist at ${score}%. Candidate meets or exceeds key requirements.`
  }
  if (verdict && /potential match/i.test(verdict) && score != null) {
    return `Hold for recruiter review at ${score}%.`
  }
  const narrative = (jsonOut?.narrative || jsonOut?.final_reasoning || jsonOut?.rationale || '').trim()
  return narrative.split(/\n/)[0]?.trim().slice(0, 280) || 'See detailed analysis below.'
}

export function getNarrative(jsonOut = {}, fallback = '') {
  const explanation = getDecisionExplanation(jsonOut, {})
  if (explanation?.what_happened?.length) {
    return [explanation.primary_reason, ...explanation.what_happened, explanation.reconciliation, explanation.next_step]
      .filter(Boolean)
      .join(' ')
  }
  const raw = (
    (jsonOut?.narrative || '').trim() ||
    (jsonOut?.final_reasoning || '').trim() ||
    (jsonOut?.rationale || '').trim() ||
    fallback ||
    ''
  )
  // Avoid showing polluted "Missing: Preferred Qualifications, plus..." blobs
  if (/preferred qualifications|,\s*plus\b|azure database for/i.test(raw)) {
    return explanation?.primary_reason || 'See the score breakdown and requirements checklist for the decision details.'
  }
  return raw
}
