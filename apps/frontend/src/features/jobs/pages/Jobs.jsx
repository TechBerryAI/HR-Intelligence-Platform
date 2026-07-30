import React, { useMemo, useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useApp } from '@/core/context/AppContext.jsx'
import FilterBar from '@/shared/components/FilterBar.jsx'
import JobCard from '@/shared/components/JobCard.jsx'
import ApplyJobModal from '@/features/jobs/components/ApplyJobModal.jsx'
import AnimatedContainer from '@/shared/components/AnimatedContainer.jsx'
import { motion } from 'framer-motion'
import { FiAlertCircle, FiRefreshCw, FiCheck, FiBriefcase } from 'react-icons/fi'
import { isStaffRecruiter } from '@/core/permissions/rbac.js'

const APPLIED_SESSION_KEY = 'publicAppliedJobIds'

function readAppliedIds() {
  try {
    const raw = sessionStorage.getItem(APPLIED_SESSION_KEY)
    const arr = raw ? JSON.parse(raw) : []
    return new Set(Array.isArray(arr) ? arr : [])
  } catch {
    return new Set()
  }
}

function writeAppliedIds(set) {
  try {
    sessionStorage.setItem(APPLIED_SESSION_KEY, JSON.stringify([...set]))
  } catch {
    // ignore
  }
}

export default function Jobs() {
  const { jobs, jobsError, jobsLoading, fetchJobs, applicantSavedJobs, toggleSaveJob, auth } = useApp()
  const location = useLocation()
  const navigate = useNavigate()
  const params = new URLSearchParams(location.search)
  const query = {
    keywords: params.get('q') || '',
    location: params.get('loc') || '',
  }
  const [applyError, setApplyError] = useState('')
  const [applySuccess, setApplySuccess] = useState('')
  const [appliedIds, setAppliedIds] = useState(() => readAppliedIds())
  const [applyJob, setApplyJob] = useState(null)

  const filtered = useMemo(() => {
    const kw = query.keywords.toLowerCase()
    const loc = query.location.toLowerCase()
    return jobs
      .filter((j) => j.enabled !== false)
      .filter((j) => {
        const inKw = kw
          ? [j.title, j.company, j.description].join(' ').toLowerCase().includes(kw)
          : true
        const inLoc = loc ? j.location.toLowerCase().includes(loc) : true
        return inKw && inLoc
      })
  }, [jobs, query.keywords, query.location])

  const handleSearch = ({ keywords, location: loc }) => {
    const sp = new URLSearchParams()
    if (keywords) sp.set('q', keywords)
    if (loc) sp.set('loc', loc)
    navigate({ pathname: '/jobs', search: `?${sp.toString()}` }, { replace: false })
  }

  useEffect(() => {
    if (!jobsError) return
    const id = setTimeout(() => {
      fetchJobs()
    }, 5000)
    return () => clearTimeout(id)
  }, [jobsError, fetchJobs])

  const markApplied = (jobId) => {
    setAppliedIds((prev) => {
      const next = new Set(prev)
      next.add(String(jobId))
      writeAppliedIds(next)
      return next
    })
  }

  return (
    <div className="min-h-screen bg-[#f7f8fa]">
      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
        <AnimatedContainer animation="slideDown">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                Open roles
              </p>
              <h2 className="mt-1 text-3xl font-semibold tracking-tight text-slate-900 sm:text-[2rem]">
                Latest jobs
              </h2>
              <p className="mt-1.5 text-sm text-slate-500">
                Browse openings and apply in one step — no account required.
              </p>
            </div>
            {filtered.length > 0 && (
              <p className="text-sm font-medium text-slate-500">
                {filtered.length} {filtered.length === 1 ? 'role' : 'roles'}
              </p>
            )}
          </div>
        </AnimatedContainer>

        {jobsError && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 rounded-xl border border-red-200 bg-red-50 p-5"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <FiAlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-600" />
                <div>
                  <p className="font-medium text-red-700">Unable to load jobs</p>
                  <p className="mt-1 text-sm text-red-600">Check your connection and try again</p>
                </div>
              </div>
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={fetchJobs}
                disabled={jobsLoading}
                className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all ${
                  jobsLoading
                    ? 'cursor-not-allowed bg-slate-300 text-slate-500'
                    : 'bg-red-600 text-white hover:bg-red-500'
                }`}
              >
                <FiRefreshCw className={`h-4 w-4 ${jobsLoading ? 'animate-spin' : ''}`} />
                {jobsLoading ? 'Retrying…' : 'Retry'}
              </motion.button>
            </div>
          </motion.div>
        )}

        <AnimatedContainer animation="fadeIn" delay={0.12}>
          <div className="mt-7">
            <FilterBar onSearch={handleSearch} initial={query} />
          </div>
        </AnimatedContainer>

        {applyError && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-5 flex items-start justify-between gap-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3"
          >
            <p className="text-sm text-amber-800">{applyError}</p>
            <button type="button" className="text-sm text-amber-700 underline" onClick={() => setApplyError('')}>
              Dismiss
            </button>
          </motion.div>
        )}

        {applySuccess && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-5 flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3"
          >
            <FiCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
            <p className="text-sm text-emerald-800">{applySuccess}</p>
          </motion.div>
        )}

        <div className="mt-7">
          {jobsLoading && !filtered.length ? (
            <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
              {[0, 1, 2].map((i) => (
                <div key={i} className="animate-pulse border-b border-slate-100 px-7 py-6 last:border-b-0">
                  <div className="h-5 w-48 rounded bg-slate-100" />
                  <div className="mt-2 h-3.5 w-36 rounded bg-slate-100" />
                  <div className="mt-3 h-3 w-full max-w-xl rounded bg-slate-100" />
                </div>
              ))}
            </div>
          ) : !filtered.length ? (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white px-6 py-16 text-center">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-400">
                <FiBriefcase className="h-5 w-5" />
              </div>
              <p className="font-medium text-slate-800">No matching roles</p>
              <p className="mt-1 max-w-sm text-sm text-slate-500">
                Try a different title, skill, or location.
              </p>
            </div>
          ) : (
            <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
              {filtered.map((job) => (
                <JobCard
                  key={job.id}
                  job={job}
                  isApplied={appliedIds.has(String(job.id))}
                  isSaved={!!applicantSavedJobs?.[job.id] || !!applicantSavedJobs?.[String(job.id)]}
                  isAdmin={isStaffRecruiter(auth)}
                  onApply={() => {
                    setApplyError('')
                    setApplySuccess('')
                    if (isStaffRecruiter(auth)) return
                    setApplyJob(job)
                  }}
                  onToggleSave={() => toggleSaveJob?.(job.id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      <ApplyJobModal
        open={!!applyJob}
        job={applyJob}
        onClose={() => setApplyJob(null)}
        onSuccess={(data) => {
          if (applyJob?.id) markApplied(applyJob.id)
          setApplySuccess(
            data?.message ||
              (data?.matchScore != null
                ? `Application submitted (match score: ${data.matchScore}).`
                : 'Application submitted successfully.')
          )
        }}
      />
    </div>
  )
}
