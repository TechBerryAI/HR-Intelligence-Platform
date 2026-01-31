/**
 * Admin-only: Job Matches (ATS results). List jobs with application and shortlisted counts; view applications per job with ATS scores.
 */
import React, { useState, useEffect } from 'react'
import { getJobMatches, getJobApplications } from '../../services/adminService.js'
import { useNavigate } from 'react-router-dom'

export default function JobMatches() {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedJobId, setSelectedJobId] = useState(null)
  const [applications, setApplications] = useState([])
  const [appsLoading, setAppsLoading] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getJobMatches()
      .then((data) => {
        if (!cancelled) setJobs(data.jobs || [])
      })
      .catch((e) => {
        if (!cancelled) setError(e?.message || e?.data?.error || 'Failed to load jobs')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!selectedJobId) {
      setApplications([])
      return
    }
    let cancelled = false
    setAppsLoading(true)
    getJobApplications(selectedJobId)
      .then((data) => {
        if (!cancelled) setApplications(Array.isArray(data) ? data : data?.applications || [])
      })
      .catch(() => {
        if (!cancelled) setApplications([])
      })
      .finally(() => {
        if (!cancelled) setAppsLoading(false)
      })
    return () => { cancelled = true }
  }, [selectedJobId])

  const selectedJob = jobs.find((j) => j.jobId === selectedJobId)

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-2xl font-bold text-white mb-2">Job Matches (ATS Results)</h1>
      <p className="text-zinc-400 text-sm mb-6">
        View applications per job with ATS match score and shortlist status.
      </p>

      {loading && <p className="text-zinc-400">Loading jobs…</p>}
      {error && (
        <div className="mb-4 p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-red-200 text-sm">
          {error}
        </div>
      )}

      {!loading && jobs.length === 0 && !error && (
        <p className="text-zinc-400">No jobs yet. Create jobs from the Dashboard.</p>
      )}

      {!loading && jobs.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2">
          <div className="border border-white/10 rounded-lg p-4">
            <h2 className="text-lg font-semibold text-white mb-3">Your jobs</h2>
            <ul className="space-y-2">
              {jobs.map((j) => (
                <li key={j.jobId}>
                  <button
                    type="button"
                    onClick={() => setSelectedJobId(j.jobId)}
                    className={`w-full text-left px-3 py-2 rounded-lg transition-colors ${
                      selectedJobId === j.jobId ? 'bg-white/15 text-white' : 'bg-white/5 text-zinc-300 hover:bg-white/10'
                    }`}
                  >
                    <span className="font-medium">{j.title}</span>
                    <span className="block text-xs text-zinc-400">
                      Applications: {j.applicationCount ?? 0} · Shortlisted: {j.shortlistedCount ?? 0}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
          <div className="border border-white/10 rounded-lg p-4">
            <h2 className="text-lg font-semibold text-white mb-3">
              {selectedJob ? selectedJob.title : 'Select a job'}
            </h2>
            {!selectedJobId && (
              <p className="text-zinc-400 text-sm">Select a job to see applications and ATS scores.</p>
            )}
            {selectedJobId && appsLoading && <p className="text-zinc-400 text-sm">Loading applications…</p>}
            {selectedJobId && !appsLoading && applications.length === 0 && (
              <p className="text-zinc-400 text-sm">No applications for this job.</p>
            )}
            {selectedJobId && !appsLoading && applications.length > 0 && (
              <ul className="space-y-2 max-h-96 overflow-y-auto">
                {applications.map((app) => (
                  <li key={app.id || app.candidateId} className="text-sm border-b border-white/5 pb-2">
                    <span className="font-medium text-white">{app.fullName || app.name || app.candidateId}</span>
                    <span className="block text-zinc-400">
                      Score: {app.matchScore != null ? `${app.matchScore}%` : '—'}
                      {app.shortlisted && <span className="text-emerald-400 ml-2">Shortlisted</span>}
                    </span>
                    {app.atsReasoning && (
                      <p className="text-xs text-zinc-500 mt-1 line-clamp-2">{app.atsReasoning}</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      <div className="mt-6">
        <button
          type="button"
          onClick={() => navigate('/candidates')}
          className="text-zinc-400 hover:text-white text-sm"
        >
          View all candidates (by job) →
        </button>
      </div>
    </div>
  )
}
