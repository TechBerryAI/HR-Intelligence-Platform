import React, { useState } from 'react'
import { FiAlertTriangle, FiZap, FiDownload } from 'react-icons/fi'
import {
  MatchHeader,
  ScoreCard,
  ChipGroup,
  CollapsibleSection,
  RequirementsChecklist,
  DetailedAnalysisPanel,
  toChips,
  getRequirementAnalysis,
  getDecisionSummary,
  getDecisionExplanation,
  withReconciledScores,
} from '@/features/analytics/components/MatchExplanation'
import { generateApplicationMatchPdf } from '@/shared/utils/pdfReportUtils.js'

const SCORE_FACTORS = [
  { name: 'Core Skills', key: 'skills', weight: 60 },
  { name: 'Experience', key: 'experience', weight: 25 },
  { name: 'Education', key: 'education', weight: 10 },
  { name: 'Location', key: 'location', weight: 5 },
]

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

export default function ApplicationMatchPanel({ application, hideHeaderClose, jobTitle }) {
  const [reportLoading, setReportLoading] = useState(false)
  const [reportError, setReportError] = useState('')

  if (!application) {
    return (
      <div className="rounded-[16px] bg-[var(--ei-surface-hover)] border border-[var(--ei-border-primary)] p-6 text-sm text-[var(--ei-text-muted)]">
        No application record found for this job.
      </div>
    )
  }

  const analysis = application.ats_analysis != null && typeof application.ats_analysis === 'object'
    ? application.ats_analysis
    : {}
  const rawJsonOut = analysis?.json_output ?? analysis
  const storedScore = application.match_score != null ? Math.round(Number(application.match_score)) : null
  const { jsonOut, recon, score, verdict: reconciledVerdict } = withReconciledScores(rawJsonOut, { storedScore })
  const breakdown = jsonOut?.score_breakdown ?? {}
  const rawStrengths = Array.isArray(jsonOut?.key_strengths) ? jsonOut.key_strengths : []
  const rawGaps = Array.isArray(jsonOut?.key_gaps) ? jsonOut.key_gaps : []
  const verdict = (reconciledVerdict || (jsonOut?.verdict || (jsonOut?.decision || '').replace(/_/g, ' ') || '').trim())
  const evalReport = jsonOut?.evaluation_report ?? {}
  const skillsAnalysis = evalReport?.skills_analysis ?? {}
  const mandatoryPct = jsonOut?.mandatory_skills_match_pct ?? skillsAnalysis?.mandatory_skills_match_pct
  const experienceAssessment = evalReport?.experience_assessment ?? {}
  const educationAssessment = evalReport?.education_certification_assessment
  const requirementAnalysis = getRequirementAnalysis(jsonOut)
  const decisionExplanation = getDecisionExplanation(jsonOut, { score })
  const categoryReasons = Array.isArray(decisionExplanation?.category_reasons) ? decisionExplanation.category_reasons : []
  const reasonByKey = Object.fromEntries(categoryReasons.map((c) => [c.key, c]))
  const hasMatchDetails = application.ats_analysis != null && typeof application.ats_analysis === 'object'
  const status = String(application.status || '').toLowerCase()
  const displayMandatoryPct = requirementAnalysis?.gate?.mandatory_pct ?? mandatoryPct
  const isNegativeVerdict =
    status === 'ats_failed' ||
    (verdict && /not a match/i.test(verdict)) ||
    (displayMandatoryPct != null && Number(displayMandatoryPct) < 60)

  const reason = !hasMatchDetails || score == null
    ? (status === 'ats_failed'
      ? (application.ats_reasoning || 'ATS matching failed for this application.')
      : 'Match details were not generated for this application.')
    : getDecisionSummary(jsonOut, {
      score,
      status,
      atsReasoning: application.ats_reasoning,
    })

  const missingMandatory = (requirementAnalysis.mandatory || [])
    .filter((r) => r.status === 'missing')
    .map((r) => r.skill)
    .slice(0, 5)

  const handleDownloadReport = () => {
    setReportError('')
    setReportLoading(true)
    try {
      generateApplicationMatchPdf(application, {
        jobTitle: jobTitle || application.job_title,
      })
    } catch (e) {
      console.error('Match PDF generation failed:', e)
      setReportError(e?.message || 'Failed to generate PDF')
    } finally {
      setReportLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {reportError && (
        <div className="org-error-banner">{reportError}</div>
      )}

      <section className="rounded-[16px] bg-[var(--ei-surface-hover)] border border-[var(--ei-border-primary)] px-5 py-[18px]">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
          <h3 className="text-[12px] font-semibold uppercase tracking-[0.08em] text-[var(--ei-text-muted)]">
            Application Overview
          </h3>
          <button
            type="button"
            onClick={handleDownloadReport}
            disabled={reportLoading}
            className="org-btn-secondary !py-2 !px-3 !text-sm self-start sm:self-auto"
          >
            {reportLoading ? (
              <span className="spinner-premium w-4 h-4 border-2" />
            ) : (
              <FiDownload className="w-4 h-4" aria-hidden="true" />
            )}
            {reportLoading ? 'Preparing…' : 'Download Report'}
          </button>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <p className="text-[12px] text-[var(--ei-text-muted)] mb-1">Status</p>
            <p className="text-[14px] sm:text-[15px] font-semibold text-[var(--ei-text-primary)]">
              <StatusDot status={application.status} shortlisted={application.shortlisted} />
            </p>
          </div>
          <div>
            <p className="text-[12px] text-[var(--ei-text-muted)] mb-1">Applied</p>
            <p className="text-[14px] sm:text-[15px] font-medium text-[var(--ei-text-primary)]">{formatDate(application.applied_at)}</p>
          </div>
          <div>
            <p className="text-[12px] text-[var(--ei-text-muted)] mb-1">Recruiter</p>
            <p className="text-[14px] sm:text-[15px] font-medium text-[var(--ei-text-primary)] truncate">{application.hr_name || '—'}</p>
          </div>
          <div>
            <p className="text-[12px] text-[var(--ei-text-muted)] mb-1">Match score</p>
            <p className="text-[14px] sm:text-[15px] font-semibold text-[var(--ei-text-primary)] tabular-nums">
              {score != null ? `${score}%` : '—'}
            </p>
          </div>
        </div>
      </section>

      <section className="rounded-[20px] border border-[var(--ei-border-primary)] overflow-hidden bg-[var(--ei-surface-glass)] shadow-[0_8px_28px_rgba(15,23,42,0.06)] text-[var(--ei-text-primary)]">
        <div className="px-5 sm:px-6 pt-5 pb-1">
          <h3 className="text-[12px] font-semibold uppercase tracking-[0.08em] text-[var(--ei-text-muted)]">
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
          <div
            className="rounded-[14px] px-4 py-3.5 border border-l-[3px]"
            style={
              isNegativeVerdict
                ? {
                    background: 'var(--ei-tone-danger-bg)',
                    borderColor: 'var(--ei-tone-danger-border)',
                    borderLeftColor: 'var(--ei-tone-danger)',
                  }
                : {
                    background: 'var(--ei-tone-success-bg)',
                    borderColor: 'var(--ei-tone-success-border)',
                    borderLeftColor: 'var(--ei-tone-success)',
                  }
            }
          >
            <div className="flex items-start gap-3">
              <div
                className="mt-0.5 flex-shrink-0 w-8 h-8 rounded-[10px] grid place-items-center"
                style={
                  isNegativeVerdict
                    ? { background: 'var(--ei-tone-danger-bg)', color: 'var(--ei-tone-danger)' }
                    : { background: 'var(--ei-tone-success-bg)', color: 'var(--ei-tone-success)' }
                }
              >
                {isNegativeVerdict ? <FiAlertTriangle className="w-4 h-4" /> : <FiZap className="w-4 h-4" />}
              </div>
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--ei-text-muted)]">
                  Why this verdict
                </p>
                <p className="mt-1.5 text-sm font-medium text-[var(--ei-text-primary)] leading-relaxed">{reason}</p>
                {recon?.note && (
                  <p className="mt-2 text-xs text-[var(--ei-text-muted)] leading-relaxed">{recon.note}</p>
                )}
                {displayMandatoryPct != null && Number(displayMandatoryPct) < 40 && (
                  <p className="mt-1.5 text-xs text-[var(--ei-text-muted)]">
                    Required threshold: 40% · Current mandatory skills match: {Number(displayMandatoryPct)}%
                    {missingMandatory.length > 0 ? ` · Missing: ${missingMandatory.join(', ')}` : ''}
                  </p>
                )}
              </div>
            </div>
          </div>

          {hasMatchDetails && (
            <div>
              <div className="mb-3">
                <h3 className="text-[12px] font-semibold uppercase tracking-[0.08em] text-[var(--ei-text-muted)]">
                  Score breakdown
                </h3>
                <p className="mt-1 text-xs text-[var(--ei-text-muted)]">
                  How well the candidate fits each area of the role
                  {displayMandatoryPct != null
                    ? ` · Mandatory skills: ${Number(displayMandatoryPct)}% matched`
                    : ''}
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {SCORE_FACTORS.map(({ name, key, weight }) => {
                  const value = breakdown[key]
                  if (value == null) return null
                  const cat = reasonByKey[key]
                  const gateFailed = key === 'skills' && displayMandatoryPct != null && Number(displayMandatoryPct) < 60
                  return (
                    <ScoreCard
                      key={key}
                      variant="enterprise"
                      factorName={name}
                      scorePct={value}
                      weightPct={weight}
                      badge={gateFailed ? 'Not enough skills' : (cat?.result_label || undefined)}
                      reason={cat?.reason || (
                        key === 'skills'
                          ? 'Compares skills the role needs with skills on the resume'
                          : key === 'experience'
                            ? 'Compares role experience needed with resume experience'
                            : key === 'education'
                              ? 'Compares education needed with resume education'
                              : 'Compares job location with candidate location'
                      )}
                    />
                  )
                })}
              </div>
            </div>
          )}

          <RequirementsChecklist
            theme="enterprise"
            requirementAnalysis={requirementAnalysis}
            mandatoryPct={displayMandatoryPct}
          />

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

          {hasMatchDetails && (
            <div
              className="rounded-[14px] p-4 border border-[var(--ei-border-primary)] bg-[var(--ei-surface-hover)]"
            >
              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--ei-text-muted)] flex items-center gap-2 mb-3">
                <FiZap className="w-3.5 h-3.5 text-[var(--ei-accent-blue)]" />
                Match Insight
              </p>
              <CollapsibleSection label="Detailed Analysis" variant="enterprise" defaultOpen>
                <DetailedAnalysisPanel
                  jsonOut={jsonOut}
                  score={score}
                  variant="enterprise"
                  experienceAssessment={experienceAssessment}
                  educationAssessment={educationAssessment}
                />
              </CollapsibleSection>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
