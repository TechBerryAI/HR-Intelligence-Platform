import React from 'react'
import { MatchHeader, ScoreCard, ChipGroup, CollapsibleSection } from '../MatchExplanation'

const SCORE_FACTORS = [
  { name: 'Core Skills', key: 'skills', weight: 60 },
  { name: 'Experience', key: 'experience', weight: 25 },
  { name: 'Education', key: 'education', weight: 10 },
  { name: 'Location', key: 'location', weight: 5 },
]

function toChips(items) {
  const out = []
  const arr = Array.isArray(items) ? items : (items && typeof items === 'object' ? Object.values(items) : [])
  arr.forEach((item) => {
    const s = String(item).trim()
    if (!s) return
    const colon = s.indexOf(': ')
    if (colon !== -1) {
      s.slice(colon + 2).split(',').map((x) => x.trim()).filter(Boolean).forEach((x) => out.push(x))
    } else {
      out.push(s)
    }
  })
  return out
}

function formatDate(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

export default function ApplicationMatchPanel({ application, hideHeaderClose }) {
  if (!application) {
    return (
      <div className="rounded-xl bg-zinc-900/60 border border-zinc-800 p-6 text-sm text-zinc-500">
        No application record found for this job.
      </div>
    )
  }

  const analysis = application.ats_analysis != null && typeof application.ats_analysis === 'object'
    ? application.ats_analysis
    : {}
  const jsonOut = analysis?.json_output ?? analysis
  const breakdown = jsonOut?.score_breakdown ?? {}
  const rawStrengths = Array.isArray(jsonOut?.key_strengths) ? jsonOut.key_strengths : []
  const rawGaps = Array.isArray(jsonOut?.key_gaps) ? jsonOut.key_gaps : []
  const verdict = (jsonOut?.verdict || (jsonOut?.decision || '').replace(/_/g, ' ') || '').trim()
  const evalReport = jsonOut?.evaluation_report ?? {}
  const skillsAnalysis = evalReport?.skills_analysis ?? {}
  const mandatoryPct = jsonOut?.mandatory_skills_match_pct ?? skillsAnalysis?.mandatory_skills_match_pct
  const decisionBullets = Array.isArray(evalReport?.final_decision_logic) ? evalReport.final_decision_logic : []
  const experienceAssessment = evalReport?.experience_assessment ?? {}
  const educationAssessment = evalReport?.education_certification_assessment
  const finalReasoning = (jsonOut?.final_reasoning || jsonOut?.rationale || application?.ats_reasoning || '').trim() || 'No detailed reasoning available.'
  const score = application.match_score != null ? Math.round(Number(application.match_score)) : null
  const hasMatchDetails = application.ats_analysis != null && typeof application.ats_analysis === 'object'
  const status = String(application.status || '').toLowerCase()

  const getVerdictReason = () => {
    if (status === 'ats_failed') {
      return application.ats_reasoning || 'ATS matching failed for this application.'
    }
    if (!hasMatchDetails || score == null) return 'Match details were not generated for this application.'
    if (mandatoryPct != null && Number(mandatoryPct) < 60) {
      return `Mandatory skills match is ${Number(mandatoryPct)}% (below 60% threshold).`
    }
    if (verdict && /not a match/i.test(verdict)) {
      return `Overall score is ${score}%, below the required threshold for this role.`
    }
    return finalReasoning.split(/\n/)[0]?.trim().slice(0, 200) || 'See detailed analysis below.'
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl bg-zinc-900/60 border border-zinc-800 p-4 text-sm grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <span className="text-zinc-500">Status</span>
          <p className="text-zinc-100 capitalize">{application.shortlisted ? 'Shortlisted' : application.status || '—'}</p>
        </div>
        <div>
          <span className="text-zinc-500">Applied</span>
          <p className="text-zinc-300">{formatDate(application.applied_at)}</p>
        </div>
        <div>
          <span className="text-zinc-500">Match score</span>
          <p className="text-zinc-100 font-semibold">{score != null ? `${score}%` : '—'}</p>
        </div>
        <div>
          <span className="text-zinc-500">Recruiter</span>
          <p className="text-zinc-300">{application.hr_name || '—'}</p>
        </div>
      </div>

      <div className="rounded-2xl border border-zinc-800 overflow-hidden bg-zinc-900/30">
        <MatchHeader
          score={score ?? 0}
          candidateName={application.candidate_name || 'Candidate'}
          candidateEmail={application.candidate_email || ''}
          verdict={status === 'ats_failed' ? 'ATS Failed' : verdict}
          onClose={hideHeaderClose ? undefined : () => {}}
        />
        <div className="p-6 space-y-6">
          <div className="rounded-xl bg-zinc-800/50 ring-1 ring-zinc-700/50 px-4 py-3">
            <p className="text-sm font-medium text-zinc-300 leading-snug">
              <span className="text-zinc-500 font-semibold uppercase tracking-wider text-xs">Why this verdict</span>
              <span className="block mt-1.5 text-white">{getVerdictReason()}</span>
            </p>
          </div>

          {hasMatchDetails && (
            <div>
              <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">Score breakdown</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {SCORE_FACTORS.map(({ name, key, weight }) => {
                  const value = breakdown[key]
                  if (value == null) return null
                  return <ScoreCard key={key} factorName={name} scorePct={value} weightPct={weight} />
                })}
              </div>
            </div>
          )}

          <ChipGroup title="Strengths" items={toChips(rawStrengths)} variant="strength" id="job-cand-strengths" />
          <ChipGroup title="Gaps" items={toChips(rawGaps)} variant="gap" id="job-cand-gaps" />

          {hasMatchDetails && (
            <CollapsibleSection label="Detailed Analysis">
              <div className="space-y-4 text-sm">
                {decisionBullets.length > 0 && (
                  <ul className="list-disc list-inside space-y-1 text-zinc-300">
                    {decisionBullets.map((bullet, i) => (
                      <li key={i}>{bullet}</li>
                    ))}
                  </ul>
                )}
                {educationAssessment && (
                  <p className="text-zinc-300">{educationAssessment}</p>
                )}
                <p className="text-zinc-300 whitespace-pre-wrap">{finalReasoning}</p>
              </div>
            </CollapsibleSection>
          )}
        </div>
      </div>
    </div>
  )
}
