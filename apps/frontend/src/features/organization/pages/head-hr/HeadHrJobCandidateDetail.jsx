import React, { useEffect, useState } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { apiRequest } from '@/core/api/api.js'
import { tokenService } from '@/core/auth/tokenService.js'
import PanelShell, { usePanelBasePath } from '@/features/organization/pages/org/PanelShell.jsx'
import CandidateProfilePanel from '@/features/organization/components/org/CandidateProfilePanel.jsx'
import ApplicationMatchPanel from '@/features/organization/components/org/ApplicationMatchPanel.jsx'
import { FiArrowLeft } from 'react-icons/fi'

export default function HeadHrJobCandidateDetail() {
  const { jdid, cid } = useParams()
  const navigate = useNavigate()
  const basePath = usePanelBasePath()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') === 'application' ? 'application' : 'profile'

  const [candidate, setCandidate] = useState(null)
  const [application, setApplication] = useState(null)
  const [jobTitle, setJobTitle] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      try {
        const token = tokenService.getToken()
        const [candidateRes, appsRes, jobRes] = await Promise.all([
          apiRequest(`/api/head-hr/candidates/${encodeURIComponent(cid)}`, { method: 'GET', token }),
          apiRequest('/api/head-hr/applications', { method: 'GET', token }),
          apiRequest(`/api/head-hr/jobs/${encodeURIComponent(jdid)}`, { method: 'GET', token }),
        ])
        if (cancelled) return
        setCandidate(candidateRes)
        setJobTitle(jobRes?.title || jdid)
        const apps = appsRes?.applications || []
        const match = apps.find(
          (a) => String(a.candidate_id || a.candidateId) === String(cid) && String(a.job_id || a.jobId) === String(jdid),
        )
        if (match?.id) {
          const detail = await apiRequest(`/api/head-hr/applications/${match.id}`, { method: 'GET', token })
          if (!cancelled) setApplication(detail)
        } else {
          setApplication(null)
        }
      } catch (err) {
        if (!cancelled) setError(err?.message || 'Failed to load candidate')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [jdid, cid])

  const setTab = (next) => {
    setSearchParams(next === 'application' ? { tab: 'application' } : {}, { replace: true })
  }

  const candidateName = candidate?.fullName || candidate?.email || 'Candidate'

  if (loading) {
    return (
      <PanelShell>
        <div className="space-y-3 max-w-[1280px] mx-auto">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="org-skeleton" />
          ))}
        </div>
      </PanelShell>
    )
  }

  if (error || !candidate) {
    return (
      <PanelShell>
        <div className="max-w-[1280px] mx-auto">
          <div className="org-error-banner">{error || 'Not found'}</div>
          <button
            type="button"
            onClick={() => navigate(`${basePath}/jobs/${encodeURIComponent(jdid)}`)}
            className="org-back-link group !mb-0"
          >
            <FiArrowLeft className="w-4 h-4 transition-transform duration-[180ms] group-hover:-translate-x-0.5" />
            Back to job
          </button>
        </div>
      </PanelShell>
    )
  }

  return (
    <PanelShell>
      <div className="max-w-[1280px] mx-auto pb-8">
        <button
          type="button"
          onClick={() => navigate(`${basePath}/jobs/${encodeURIComponent(jdid)}`)}
          className="group inline-flex items-center gap-2 text-sm text-[#8FA1B3] hover:text-white mb-6 transition-colors duration-[180ms]"
        >
          <FiArrowLeft className="w-4 h-4 transition-transform duration-[180ms] group-hover:-translate-x-0.5" />
          Back to {jobTitle}
        </button>

        <header className="mb-6">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#83909C] mb-2">
            Candidate Evaluation
          </p>
          <h1 className="font-display text-[28px] sm:text-[30px] font-bold text-[#F5F7FA] tracking-tight leading-tight">
            {candidateName}
          </h1>
          <p className="mt-1.5 text-sm text-[#8E9BA8]">
            Application for {jobTitle}
          </p>
        </header>

        <div className="flex gap-6 mb-6 border-b border-white/[0.08]">
          {[
            { id: 'profile', label: 'Profile & Resume' },
            { id: 'application', label: 'Application & Match' },
          ].map(({ id, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`relative px-1 py-3 text-sm font-medium transition-colors duration-[180ms] ${
                tab === id
                  ? 'text-white'
                  : 'text-[#77899B] hover:text-[#DCE3EA]'
              }`}
            >
              {label}
              {tab === id && (
                <span
                  className="absolute left-0 right-0 bottom-0 h-0.5 rounded-full"
                  style={{ background: 'linear-gradient(90deg, #00A6FF, #7657FF)' }}
                  aria-hidden
                />
              )}
            </button>
          ))}
        </div>

        {tab === 'profile' ? (
          <CandidateProfilePanel candidate={candidate} cid={cid} />
        ) : (
          <ApplicationMatchPanel application={application} hideHeaderClose />
        )}
      </div>
    </PanelShell>
  )
}
