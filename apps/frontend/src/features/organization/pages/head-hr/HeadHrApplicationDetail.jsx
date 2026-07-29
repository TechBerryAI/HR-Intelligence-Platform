import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { apiRequest } from '@/core/api/api.js'
import { tokenService } from '@/core/auth/tokenService.js'
import PanelShell, { usePanelBasePath } from '@/features/organization/pages/org/PanelShell.jsx'
import { FiArrowLeft, FiFileText } from 'react-icons/fi'
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
      const rest = s.slice(colon + 2).split(',').map((x) => x.trim()).filter(Boolean)
      rest.forEach((x) => out.push(x))
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

export default function HeadHrApplicationDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const basePath = usePanelBasePath()
  const [application, setApplication] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      try {
        const token = tokenService.getToken()
        const data = await apiRequest(`/api/head-hr/applications/${id}`, { method: 'GET', token })
        if (!cancelled) setApplication(data)
      } catch (err) {
        if (!cancelled) setError(err?.message || 'Failed to load application')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [id])

  if (loading) {
    return (
      <PanelShell>
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="org-skeleton" />
          ))}
        </div>
      </PanelShell>
    )
  }

  if (error || !application) {
    return (
      <PanelShell>
        <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
          {error || 'Application not found'}
        </div>
        <button
          type="button"
          onClick={() => navigate(`${basePath}/applications`)}
          className="org-back-link !mb-0"
        >
          <FiArrowLeft className="w-4 h-4" /> Back to Applications
        </button>
      </PanelShell>
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

  const getVerdictReason = () => {
    if (!hasMatchDetails || score == null) return 'Match details were not generated for this application.'
    const isNotMatch = verdict && /not a match/i.test(verdict)
    if (mandatoryPct != null && Number(mandatoryPct) < 60 && (skillsAnalysis.missing_mandatory_skills?.length > 0 || breakdown.skills === 0)) {
      return `Mandatory skills match is ${Number(mandatoryPct)}% (below 60% threshold). Candidate does not meet required technical skills.`
    }
    if (isNotMatch) {
      return `Overall score is ${score}%, below the required threshold for this role.`
    }
    if (verdict && /strong match/i.test(verdict)) {
      return `Overall score is ${score}%. Candidate meets or exceeds key requirements.`
    }
    if (verdict && /potential match/i.test(verdict)) {
      return `Overall score is ${score}%. Recommended for recruiter review.`
    }
    return finalReasoning.split(/\n/)[0]?.trim().slice(0, 200) || 'See detailed analysis below.'
  }

  const strengthChips = toChips(rawStrengths)
  const gapChips = toChips(rawGaps)

  return (
    <PanelShell>
      <div className="max-w-3xl mx-auto">
        <button
          type="button"
          onClick={() => navigate(`${basePath}/applications`)}
          className="org-back-link"
        >
          <FiArrowLeft className="w-4 h-4" /> Back to Applications
        </button>

        <div className="flex items-center gap-2 mb-4">
          <FiFileText className="w-5 h-5 text-slate-400" />
          <h1 className="text-xl font-bold text-slate-900 dark:text-white">Application #{application.id}</h1>
        </div>

        <div className="org-section mb-6 space-y-2 text-sm">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div>
              <span className="org-section-label">Job</span>
              <p className="text-slate-900 dark:text-slate-100 font-medium">{application.job_title || '—'}</p>
              <p className="text-slate-500 text-xs">{application.job_company}</p>
            </div>
            <div>
              <span className="org-section-label">HR Admin</span>
              <p className="org-section-value">{application.hr_name || '—'}</p>
            </div>
            <div>
              <span className="org-section-label">Status</span>
              <p className="org-section-value capitalize">{application.shortlisted ? 'Shortlisted' : application.status || '—'}</p>
            </div>
            <div>
              <span className="org-section-label">Applied</span>
              <p className="org-section-value">{formatDate(application.applied_at)}</p>
            </div>
          </div>
        </div>

        <div className="org-card overflow-hidden">
          <MatchHeader
            score={score ?? 0}
            candidateName={application.candidate_name || 'Candidate'}
            candidateEmail={application.candidate_email || ''}
            verdict={verdict}
            onClose={() => navigate(`${basePath}/applications`)}
          />
          <div className="p-6 space-y-6">
            <div className="rounded-xl bg-slate-50 dark:bg-slate-800/50 ring-1 ring-slate-200 dark:ring-slate-700 px-4 py-3">
              <p className="text-sm font-medium text-slate-700 dark:text-slate-300 leading-snug">
                <span className="org-section-label">Why this verdict</span>
                <span className="block mt-1.5 text-slate-900 dark:text-white">{getVerdictReason()}</span>
              </p>
            </div>

            {hasMatchDetails && (breakdown.skills != null || breakdown.experience != null || breakdown.education != null || breakdown.location != null) && (
              <div>
                <h3 className="org-section-label mb-3">Score breakdown</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {SCORE_FACTORS.map(({ name, key, weight }) => {
                    const value = breakdown[key]
                    if (value == null) return null
                    return (
                      <ScoreCard
                        key={key}
                        factorName={name}
                        scorePct={value}
                        weightPct={weight}
                      />
                    )
                  })}
                </div>
              </div>
            )}

            <ChipGroup title="Strengths" items={strengthChips} variant="strength" id="detail-strengths" />
            <ChipGroup title="Gaps" items={gapChips} variant="gap" id="detail-gaps" />

            {hasMatchDetails && (
              <CollapsibleSection label="Detailed Analysis">
                <div className="space-y-4 text-sm">
                  {decisionBullets.length > 0 && (
                    <div>
                      <p className="org-section-label mb-2">Decision logic</p>
                      <ul className="list-disc list-inside space-y-1 text-slate-700 dark:text-slate-300">
                        {decisionBullets.map((bullet, i) => (
                          <li key={i} className="leading-relaxed">{bullet}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {(experienceAssessment.relevant_experience_summary || experienceAssessment.gaps_vs_role_expectations) && (
                    <div className="pt-3 border-t border-slate-200 dark:border-slate-600/50">
                      <p className="org-section-label mb-2">Experience</p>
                      <div className="space-y-1.5 text-slate-700 dark:text-slate-300">
                        {experienceAssessment.relevant_experience_summary && (
                          <p><span className="text-slate-500">Relevant:</span> {experienceAssessment.relevant_experience_summary}</p>
                        )}
                        {experienceAssessment.gaps_vs_role_expectations && (
                          <p><span className="text-slate-500">Gaps:</span> {experienceAssessment.gaps_vs_role_expectations}</p>
                        )}
                      </div>
                    </div>
                  )}
                  {educationAssessment != null && String(educationAssessment).trim() !== '' && (
                    <div className="pt-3 border-t border-slate-200 dark:border-slate-600/50">
                      <p className="org-section-label mb-2">Education & certifications</p>
                      <p className="text-slate-700 dark:text-slate-300 leading-relaxed">{educationAssessment}</p>
                    </div>
                  )}
                  <div className="pt-3 border-t border-slate-200 dark:border-slate-600/50">
                    <p className="org-section-label mb-2">Full reasoning</p>
                    <p className="text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-wrap">{finalReasoning}</p>
                  </div>
                </div>
              </CollapsibleSection>
            )}
          </div>
        </div>
      </div>
    </PanelShell>
  )
}
