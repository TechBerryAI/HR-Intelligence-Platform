/**
 * Client-side executive analytics. Display-only: does not treat Applied as Rejected.
 * Non-shortlisted apps stay in the talent pool until a recruiter explicitly rejects them.
 */

const ADVANCED_STATUSES = new Set(['shortlisted', 'interview', 'offer', 'hired'])

const STATUS_ALIASES = {
  pending: 'applied',
  applied: 'applied',
  profile_viewed: 'screening',
  reviewed: 'screening',
  screening: 'screening',
  matched: 'screening',
  shortlisted: 'shortlisted',
  interview: 'interview',
  rejected: 'rejected',
  not_shortlisted: 'rejected',
  offer: 'offer',
  hired: 'hired',
  withdrawn: 'withdrawn',
  ats_failed: 'applied',
}

export const PIPELINE_STAGES = [
  { key: 'applied', label: 'Applied' },
  { key: 'screening', label: 'Screening' },
  { key: 'shortlisted', label: 'Shortlisted' },
  { key: 'interview', label: 'Interview' },
  { key: 'offer', label: 'Offer' },
  { key: 'hired', label: 'Hired' },
]

export const PIPELINE_EXITS = [
  { key: 'rejected', label: 'Rejected' },
  { key: 'withdrawn', label: 'Withdrawn' },
]

export const VERDICT_KEYS = [
  { key: 'strong', label: 'Strong Match' },
  { key: 'potential', label: 'Potential Match' },
  { key: 'notMatch', label: 'Not a Match' },
  { key: 'unknown', label: 'Unscored' },
]

function isTruthyFlag(value) {
  return value === true || value === 1 || value === '1' || value === 'true'
}

export function normalizePipelineStatus(app) {
  const raw = String(app?.status ?? app?.Status ?? 'applied').toLowerCase().trim()
  const mapped = STATUS_ALIASES[raw] || (raw && STATUS_ALIASES[raw.replace(/\s+/g, '_')]) || 'applied'
  if (ADVANCED_STATUSES.has(mapped)) return mapped
  if (mapped === 'rejected' || mapped === 'withdrawn') return mapped
  if (isTruthyFlag(app?.shortlisted) && mapped !== 'rejected' && mapped !== 'withdrawn') {
    return 'shortlisted'
  }
  return mapped
}

export function outcomeBucket(app) {
  const status = normalizePipelineStatus(app)
  if (status === 'rejected') return 'rejected'
  if (status === 'withdrawn') return 'withdrawn'
  if (isTruthyFlag(app?.shortlisted) || ADVANCED_STATUSES.has(status)) return 'shortlisted'
  return 'notShortlisted'
}

export function classifyVerdict(app) {
  const raw = String(app?.verdict || '').trim()
  if (/strong match/i.test(raw)) return 'strong'
  if (/potential match/i.test(raw)) return 'potential'
  if (/not a match|ats failed/i.test(raw)) return 'notMatch'

  const score = app?.match_score != null ? Number(app.match_score) : NaN
  if (!Number.isNaN(score)) {
    if (score >= 80) return 'strong'
    if (score >= 40) return 'potential'
    return 'notMatch'
  }
  return 'unknown'
}

function emptyJobAgg() {
  return {
    count: 0,
    shortlisted: 0,
    notShortlisted: 0,
    rejected: 0,
    withdrawn: 0,
    scoreSum: 0,
    scoreN: 0,
  }
}

export function computeExecutiveAnalytics(applications = [], jobs = []) {
  const apps = Array.isArray(applications) ? applications : []
  const total = apps.length

  const byPipeline = {
    applied: 0,
    screening: 0,
    shortlisted: 0,
    interview: 0,
    offer: 0,
    hired: 0,
    rejected: 0,
    withdrawn: 0,
  }
  const byOutcome = { shortlisted: 0, notShortlisted: 0, rejected: 0, withdrawn: 0 }
  const byVerdict = { strong: 0, potential: 0, notMatch: 0, unknown: 0 }
  const scoreBuckets = { high: 0, medium: 0, low: 0 }
  const byJob = {}
  let scoreSum = 0
  let scoreCount = 0

  apps.forEach((app) => {
    const pipeline = normalizePipelineStatus(app)
    byPipeline[pipeline] = (byPipeline[pipeline] || 0) + 1

    const outcome = outcomeBucket(app)
    byOutcome[outcome] += 1

    byVerdict[classifyVerdict(app)] += 1

    const jobId = app.job_id || app.jobId
    if (jobId) {
      if (!byJob[jobId]) byJob[jobId] = emptyJobAgg()
      const row = byJob[jobId]
      row.count += 1
      if (outcome === 'shortlisted') row.shortlisted += 1
      else if (outcome === 'rejected') row.rejected += 1
      else if (outcome === 'withdrawn') row.withdrawn += 1
      else row.notShortlisted += 1
    }

    const score = app.match_score != null ? Number(app.match_score) : NaN
    if (!Number.isNaN(score)) {
      scoreSum += score
      scoreCount += 1
      if (score >= 60) scoreBuckets.high += 1
      else if (score >= 30) scoreBuckets.medium += 1
      else scoreBuckets.low += 1
      if (jobId && byJob[jobId]) {
        byJob[jobId].scoreSum += score
        byJob[jobId].scoreN += 1
      }
    }
  })

  const jobTitleById = {}
  ;(Array.isArray(jobs) ? jobs : []).forEach((j) => {
    jobTitleById[j.jdid || j.id] = j.title || j.jdid || j.id
  })

  const topJobs = Object.entries(byJob)
    .map(([id, data]) => ({
      id,
      title: jobTitleById[id] || id,
      count: data.count,
      shortlisted: data.shortlisted,
      notShortlisted: data.notShortlisted,
      rejected: data.rejected,
      withdrawn: data.withdrawn,
      conversion: data.count > 0 ? Math.round((data.shortlisted / data.count) * 100) : 0,
      avgScore: data.scoreN > 0 ? Math.round((data.scoreSum / data.scoreN) * 10) / 10 : null,
    }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 6)

  const avgScore = scoreCount > 0 ? Math.round((scoreSum / scoreCount) * 10) / 10 : null
  const shortlistedCount = byOutcome.shortlisted
  const shortlistRate = total > 0 ? Math.round((shortlistedCount / total) * 100) : 0

  return {
    total,
    byPipeline,
    byOutcome,
    byVerdict,
    scoreBuckets,
    scoreCount,
    avgScore,
    shortlistedCount,
    shortlistRate,
    notShortlistedCount: byOutcome.notShortlisted,
    rejectedCount: byOutcome.rejected,
    withdrawnCount: byOutcome.withdrawn,
    topJobs,
  }
}
