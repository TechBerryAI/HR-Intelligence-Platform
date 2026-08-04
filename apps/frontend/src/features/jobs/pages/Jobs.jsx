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
import { apiRequest } from '@/core/api/api.js'
import { useTheme } from '@/core/context/ThemeContext.jsx'

export default function Jobs() {
  const { auth, jobsBoardRevision } = useApp()
  const { surfaceTheme } = useTheme()
  const location = useLocation()
  const navigate = useNavigate()
  const params = new URLSearchParams(location.search)
  const query = {
    keywords: params.get('q') || '',
    location: params.get('loc') || '',
  }
  const [jobs, setJobs] = useState([])
  const [jobsLoading, setJobsLoading] = useState(true)
  const [jobsError, setJobsError] = useState('')
  const [applyError, setApplyError] = useState('')
  const [applySuccess, setApplySuccess] = useState('')
  const [applyJob, setApplyJob] = useState(null)

  const fetchPublicJobs = async () => {
    setJobsLoading(true)
    setJobsError('')
    try {
      const data = await apiRequest('/api/jobs', { method: 'GET' })
      if (Array.isArray(data)) setJobs(data)
      else if (data && Array.isArray(data.jobs)) setJobs(data.jobs)
      else setJobs([])
    } catch (err) {
      setJobsError(err?.message || 'Failed to load jobs')
    } finally {
      setJobsLoading(false)
    }
  }

  // Refetch on mount, navigation, and after staff enable/disable/delete
  useEffect(() => {
    fetchPublicJobs()
  }, [location.key, jobsBoardRevision])

  // Refetch when returning to the tab (portal stays in sync)
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === 'visible') fetchPublicJobs()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [])

  const filtered = useMemo(() => {
    const kw = query.keywords.toLowerCase()
    const loc = query.location.toLowerCase()
    return jobs
      .filter((j) => j.enabled !== false)
      .filter((j) => {
        const inKw = kw
          ? [j.title, j.company, j.description].join(' ').toLowerCase().includes(kw)
          : true
        const inLoc = loc ? String(j.location || '').toLowerCase().includes(loc) : true
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
      fetchPublicJobs()
    }, 5000)
    return () => clearTimeout(id)
  }, [jobsError])

  return (
    <div className="min-h-[calc(100vh-4rem)]">
      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
        <AnimatedContainer animation="slideDown">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--ei-text-muted)]">
                Open roles
              </p>
              <h2 className="mt-1 text-3xl font-semibold tracking-tight text-[var(--ei-text-primary)] sm:text-[2rem]">
                Latest jobs
              </h2>
              <p className="mt-1.5 text-sm text-[var(--ei-text-secondary)]">
                Browse openings and apply in one step — no account required.
              </p>
            </div>
            {filtered.length > 0 && (
              <p className="text-sm font-medium text-[var(--ei-text-secondary)]">
                {filtered.length} {filtered.length === 1 ? 'role' : 'roles'}
              </p>
            )}
          </div>
        </AnimatedContainer>

        {jobsError && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 rounded-xl border border-[rgba(255,102,133,0.28)] bg-[rgba(255,102,133,0.1)] p-5"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <FiAlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-[#FF7B8E]" />
                <div>
                  <p className="font-medium text-[#FFB0BB]">Unable to load jobs</p>
                  <p className="mt-1 text-sm text-[#FF7B8E]">Check your connection and try again</p>
                </div>
              </div>
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={fetchPublicJobs}
                disabled={jobsLoading}
                className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all ${
                  jobsLoading
                    ? 'cursor-not-allowed bg-white/10 text-[#71808E]'
                    : 'bg-[#FF6685] text-white hover:bg-[#FF7B8E]'
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
            <FilterBar theme={surfaceTheme} onSearch={handleSearch} initial={query} />
          </div>
        </AnimatedContainer>

        {applyError && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-5 flex items-start justify-between gap-4 rounded-xl border border-[rgba(245,185,76,0.28)] bg-[rgba(245,185,76,0.1)] px-4 py-3"
          >
            <p className="text-sm text-[#F5D08A]">{applyError}</p>
            <button type="button" className="text-sm text-[#F5B94C] underline" onClick={() => setApplyError('')}>
              Dismiss
            </button>
          </motion.div>
        )}

        {applySuccess && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-5 flex items-start gap-3 rounded-xl border border-[rgba(54,214,160,0.28)] bg-[rgba(54,214,160,0.1)] px-4 py-3"
          >
            <FiCheck className="mt-0.5 h-5 w-5 shrink-0 text-[#36D6A0]" />
            <p className="text-sm text-[#67DFB4]">{applySuccess}</p>
          </motion.div>
        )}

        <div className="mt-7">
          {jobsLoading && !filtered.length ? (
            <div className="overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.03]">
              {[0, 1, 2].map((i) => (
                <div key={i} className="animate-pulse border-b border-white/[0.06] px-7 py-6 last:border-b-0">
                  <div className="h-5 w-48 rounded bg-white/[0.08]" />
                  <div className="mt-2 h-3.5 w-36 rounded bg-white/[0.06]" />
                  <div className="mt-3 h-3 w-full max-w-xl rounded bg-white/[0.05]" />
                </div>
              ))}
            </div>
          ) : !filtered.length ? (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/15 bg-white/[0.03] px-6 py-16 text-center">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-white/[0.06] text-[var(--ei-text-muted)]">
                <FiBriefcase className="h-5 w-5" />
              </div>
              <p className="font-medium text-[var(--ei-text-primary)]">No matching roles</p>
              <p className="mt-1 max-w-sm text-sm text-[var(--ei-text-secondary)]">
                Try a different title, skill, or location.
              </p>
            </div>
          ) : (
            <div className="overflow-hidden rounded-2xl border border-[var(--ei-border-primary)] bg-[var(--ei-surface-glass-soft)] shadow-[0_12px_40px_rgba(0,0,0,0.12)]">
              {filtered.map((job) => (
                <JobCard
                  key={job.id}
                  theme={surfaceTheme}
                  job={job}
                  isAdmin={isStaffRecruiter(auth)}
                  onApply={() => {
                    setApplyError('')
                    setApplySuccess('')
                    if (isStaffRecruiter(auth)) return
                    setApplyJob(job)
                  }}
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
