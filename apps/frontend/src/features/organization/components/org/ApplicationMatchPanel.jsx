import React from 'react'
import { FiAlertTriangle, FiZap } from 'react-icons/fi'
import { MatchHeader, ScoreCard, ChipGroup, CollapsibleSection } from '@/features/analytics/components/MatchExplanation'

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

function StatusDot({ status, shortlisted }) {
  const label = shortlisted ? 'Shortlisted' : (status || '—')
  const tone = shortlisted
    ? 'bg-[#36D6A0]'
    : /reject|fail/i.test(String(status))
      ? 'bg-[#FF5D73]'
      : 'bg-[#00A6FF]'
  return (
    <span className="inline-flex items-center gap-2 capitalize">
      <span className={`w-1.5 h-1.5 rounded-full ${tone}`} aria-hidden />
      {label}
    </span>
  )
}

export default function ApplicationMatchPanel({ application, hideHeaderClose }) {
  if (!application) {
    return (
      <div className="rounded-[16px] bg-white/[0.025] border border-white/[0.08] p-6 text-sm text-[#8796A5]">
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
  const educationAssessment = evalReport?.education_certification_assessment
  const finalReasoning = (jsonOut?.final_reasoning || jsonOut?.rationale || application?.ats_reasoning || '').trim() || 'No detailed reasoning available.'
  const score = application.match_score != null ? Math.round(Number(application.match_score)) : null
  const hasMatchDetails = application.ats_analysis != null && typeof application.ats_analysis === 'object'
  const status = String(application.status || '').toLowerCase()
  const isNegativeVerdict =
    status === 'ats_failed' ||
    (verdict && /not a match/i.test(verdict)) ||
    (mandatoryPct != null && Number(mandatoryPct) < 60)

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

  const reason = getVerdictReason()

  return (
    <div className="space-y-6">
      {/* Application overview — compact metadata; score de-emphasized vs hero */}
      <section className="rounded-[16px] bg-white/[0.025] border border-white/[0.08] px-5 py-[18px]">
        <h3 className="text-[12px] font-semibold uppercase tracking-[0.08em] text-[#738394] mb-4">
          Application Overview
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <p className="text-[12px] text-[#738394] mb-1">Status</p>
            <p className="text-[14px] sm:text-[15px] font-semibold text-[#F2F5F8]">
              <StatusDot status={application.status} shortlisted={application.shortlisted} />
            </p>
          </div>
          <div>
            <p className="text-[12px] text-[#738394] mb-1">Applied</p>
            <p className="text-[14px] sm:text-[15px] font-medium text-[#F2F5F8]">{formatDate(application.applied_at)}</p>
          </div>
          <div>
            <p className="text-[12px] text-[#738394] mb-1">Recruiter</p>
            <p className="text-[14px] sm:text-[15px] font-medium text-[#F2F5F8] truncate">{application.hr_name || '—'}</p>
          </div>
          <div>
            <p className="text-[12px] text-[#738394] mb-1">Match score</p>
            <p className="text-[14px] sm:text-[15px] font-medium text-[#A0ABB6] tabular-nums">
              {score != null ? `${score}%` : '—'}
            </p>
          </div>
        </div>
      </section>

      {/* Primary match analysis */}
      <section className="rounded-[20px] border border-white/[0.08] overflow-hidden bg-[rgba(16,23,30,0.82)] shadow-[0_18px_45px_rgba(0,0,0,0.20)]">
        <div className="px-5 sm:px-6 pt-5 pb-1">
          <h3 className="text-[12px] font-semibold uppercase tracking-[0.08em] text-[#83909C]">
            Match Analysis
          </h3>
        </div>

        <MatchHeader
          variant="enterprise"
          score={score ?? 0}
          candidateName={application.candidate_name || 'Candidate'}
          candidateEmail={application.candidate_email || ''}
          verdict={status === 'ats_failed' ? 'ATS Failed' : verdict}
          onClose={hideHeaderClose ? undefined : () => {}}
        />

        <div className="p-5 sm:p-6 space-y-6">
          {/* Why this verdict */}
          <div
            className={`rounded-[14px] px-4 py-3.5 border-l-[3px] ${
              isNegativeVerdict
                ? 'bg-[rgba(255,82,105,0.035)] border border-[rgba(255,82,105,0.12)] border-l-[rgba(255,82,105,0.65)]'
                : 'bg-[rgba(55,214,160,0.04)] border border-[rgba(55,214,160,0.12)] border-l-[rgba(55,214,160,0.55)]'
            }`}
          >
            <div className="flex items-start gap-3">
              <div
                className={`mt-0.5 flex-shrink-0 w-8 h-8 rounded-[10px] grid place-items-center ${
                  isNegativeVerdict
                    ? 'bg-[rgba(255,82,105,0.12)] text-[#FF758A]'
                    : 'bg-[rgba(55,214,160,0.12)] text-[#67DFB4]'
                }`}
              >
                {isNegativeVerdict ? <FiAlertTriangle className="w-4 h-4" /> : <FiZap className="w-4 h-4" />}
              </div>
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#83909C]">
                  Why this verdict
                </p>
                <p className="mt-1.5 text-sm font-medium text-[#F2F5F8] leading-relaxed">{reason}</p>
                {mandatoryPct != null && Number(mandatoryPct) < 60 && (
                  <p className="mt-1.5 text-xs text-[#8796A5]">
                    Required threshold: 60% · Current mandatory skills match: {Number(mandatoryPct)}%
                  </p>
                )}
              </div>
            </div>
          </div>

          {hasMatchDetails && (
            <div>
              <div className="mb-3">
                <h3 className="text-[12px] font-semibold uppercase tracking-[0.08em] text-[#83909C]">
                  Score breakdown
                </h3>
                <p className="mt-1 text-xs text-[#738394]">
                  How this candidate scored across the evaluation criteria
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {SCORE_FACTORS.map(({ name, key, weight }) => {
                  const value = breakdown[key]
                  if (value == null) return null
                  return (
                    <ScoreCard
                      key={key}
                      variant="enterprise"
                      factorName={name}
                      scorePct={value}
                      weightPct={weight}
                      badge={key === 'skills' ? 'Mandatory' : undefined}
                    />
                  )
                })}
              </div>
            </div>
          )}

          <ChipGroup
            theme="enterprise"
            title="Strengths"
            items={toChips(rawStrengths)}
            variant="strength"
            id="job-cand-strengths"
          />
          <ChipGroup
            theme="enterprise"
            title="Gaps"
            items={toChips(rawGaps)}
            variant="gap"
            id="job-cand-gaps"
          />

          {hasMatchDetails && (decisionBullets.length > 0 || educationAssessment || finalReasoning) && (
            <div
              className="rounded-[14px] p-4 border border-[rgba(103,128,255,0.13)]"
              style={{
                background: 'linear-gradient(135deg, rgba(105,80,255,0.07), rgba(0,166,255,0.04))',
              }}
            >
              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#83909C] flex items-center gap-2 mb-3">
                <FiZap className="w-3.5 h-3.5 text-[#00A6FF]" />
                AI Match Insight
              </p>
              <CollapsibleSection label="Detailed Analysis" variant="enterprise">
                <div className="space-y-4 text-sm">
                  {decisionBullets.length > 0 && (
                    <ul className="list-disc list-inside space-y-1 text-[#A0ABB6]">
                      {decisionBullets.map((bullet, i) => (
                        <li key={i}>{bullet}</li>
                      ))}
                    </ul>
                  )}
                  {educationAssessment && (
                    <p className="text-[#A0ABB6]">{educationAssessment}</p>
                  )}
                  <p className="text-[#A0ABB6] whitespace-pre-wrap">{finalReasoning}</p>
                </div>
              </CollapsibleSection>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
