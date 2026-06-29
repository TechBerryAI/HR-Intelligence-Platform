import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { apiRequest } from '../../utils/api.js'
import { tokenService } from '../../utils/tokenService.js'
import HeadHrLayout from './HeadHrLayout.jsx'
import JobDescriptionView from '../../components/JobDescriptionView.jsx'
import { FiArrowLeft, FiBriefcase, FiMapPin, FiDollarSign, FiUser, FiCalendar } from 'react-icons/fi'

function formatDate(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

export default function HeadHrJobDetail() {
  const { jdid } = useParams()
  const navigate = useNavigate()
  const [job, setJob] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      try {
        const token = tokenService.getToken()
        const data = await apiRequest(`/api/head-hr/jobs/${encodeURIComponent(jdid)}`, { method: 'GET', token })
        if (!cancelled) setJob(data)
      } catch (err) {
        if (!cancelled) setError(err?.message || 'Failed to load job')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [jdid])

  if (loading) {
    return (
      <HeadHrLayout>
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-16 rounded-xl bg-zinc-900/60 border border-zinc-800 animate-pulse" />
          ))}
        </div>
      </HeadHrLayout>
    )
  }

  if (error || !job) {
    return (
      <HeadHrLayout>
        <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
          {error || 'Job not found'}
        </div>
        <button
          type="button"
          onClick={() => navigate('/head-hr/jobs')}
          className="mt-4 inline-flex items-center gap-2 text-sm text-zinc-400 hover:text-white"
        >
          <FiArrowLeft className="w-4 h-4" /> Back to Jobs
        </button>
      </HeadHrLayout>
    )
  }

  const sectionClass = 'rounded-xl bg-zinc-900/60 border border-zinc-800 p-4'
  const labelClass = 'text-xs font-semibold text-zinc-500 uppercase tracking-wider'

  return (
    <HeadHrLayout>
      <div className="max-w-3xl mx-auto">
        <button
          type="button"
          onClick={() => navigate('/head-hr/jobs')}
          className="inline-flex items-center gap-2 text-sm text-zinc-400 hover:text-white mb-6 transition-colors"
        >
          <FiArrowLeft className="w-4 h-4" /> Back to Jobs
        </button>

        <div className="flex items-start gap-3 mb-6">
          <div className="w-12 h-12 rounded-xl bg-zinc-800 flex items-center justify-center flex-shrink-0">
            <FiBriefcase className="w-6 h-6 text-zinc-400" />
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="text-xl font-bold text-white">{job.title || 'Job'}</h1>
            <p className="text-zinc-400 mt-0.5">{job.company || '—'}</p>
            <p className="text-zinc-500 text-sm font-mono mt-1">{job.jdid}</p>
          </div>
          <span
            className={`flex-shrink-0 inline-flex items-center px-3 py-1 rounded-full text-xs font-medium ${
              job.enabled ? 'bg-green-500/15 text-green-400 border border-green-500/20' : 'bg-zinc-700/50 text-zinc-500 border border-zinc-700'
            }`}
          >
            {job.enabled ? 'Active' : 'Disabled'}
          </span>
        </div>

        <div className={`${sectionClass} mb-4`}>
          <h2 className={labelClass}>Details (filled by admin)</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-3">
            {job.location && (
              <div className="flex items-start gap-2">
                <FiMapPin className="w-4 h-4 text-zinc-500 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs text-zinc-500">Location</p>
                  <p className="text-sm text-zinc-200">{job.location}</p>
                </div>
              </div>
            )}
            {job.salary != null && job.salary !== '' && (
              <div className="flex items-start gap-2">
                <FiDollarSign className="w-4 h-4 text-zinc-500 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs text-zinc-500">Salary</p>
                  <p className="text-sm text-zinc-200">{job.salary}</p>
                </div>
              </div>
            )}
            {job.experience != null && job.experience !== '' && (
              <div className="flex items-start gap-2">
                <FiBriefcase className="w-4 h-4 text-zinc-500 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs text-zinc-500">Experience</p>
                  <p className="text-sm text-zinc-200">{job.experience}</p>
                </div>
              </div>
            )}
            <div className="flex items-start gap-2">
              <FiUser className="w-4 h-4 text-zinc-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-xs text-zinc-500">Posted by</p>
                <p className="text-sm text-zinc-200">{job.posted_by_name || '—'}</p>
                {job.posted_by_email && (
                  <p className="text-xs text-zinc-500">{job.posted_by_email}</p>
                )}
              </div>
            </div>
            <div className="flex items-start gap-2">
              <FiCalendar className="w-4 h-4 text-zinc-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-xs text-zinc-500">Posted on</p>
                <p className="text-sm text-zinc-200">{formatDate(job.posted_on)}</p>
              </div>
            </div>
          </div>
        </div>

        <div className={sectionClass}>
          <h2 className={labelClass}>Job description</h2>
          <div className="mt-3">
            <JobDescriptionView
              description={job.description}
              titleClassName="text-zinc-400"
              textClassName="text-zinc-300"
            />
          </div>
        </div>
      </div>
    </HeadHrLayout>
  )
}
