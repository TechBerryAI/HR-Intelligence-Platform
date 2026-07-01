import React, { useEffect, useState } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { apiRequest } from '../../utils/api.js'
import { tokenService } from '../../utils/tokenService.js'
import PanelShell, { usePanelBasePath } from '../org/PanelShell.jsx'
import CandidateProfilePanel from '../../components/org/CandidateProfilePanel.jsx'
import ApplicationMatchPanel from '../../components/org/ApplicationMatchPanel.jsx'
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

  if (loading) {
    return (
      <PanelShell>
        <div className="space-y-2 max-w-4xl mx-auto">
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
        <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">{error || 'Not found'}</div>
        <button type="button" onClick={() => navigate(`${basePath}/jobs/${encodeURIComponent(jdid)}`)} className="org-back-link !mb-0">
          <FiArrowLeft className="w-4 h-4" /> Back to job
        </button>
      </PanelShell>
    )
  }

  return (
    <PanelShell>
      <div className="max-w-4xl mx-auto">
        <button
          type="button"
          onClick={() => navigate(`${basePath}/jobs/${encodeURIComponent(jdid)}`)}
          className="org-back-link !mb-4"
        >
          <FiArrowLeft className="w-4 h-4" /> Back to {jobTitle}
        </button>

        <div className="flex gap-1 mb-6 border-b border-zinc-800">
          {[
            { id: 'profile', label: 'Profile & Resume' },
            { id: 'application', label: 'Application & Match' },
          ].map(({ id, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
                tab === id
                  ? 'border-purple-500 text-white'
                  : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-300'
              }`}
            >
              {label}
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
