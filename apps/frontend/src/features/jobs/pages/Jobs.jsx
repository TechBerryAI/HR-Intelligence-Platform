import React, { useMemo, useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useApp } from '@/core/context/AppContext.jsx'
import FilterBar from '@/shared/components/FilterBar.jsx'
import JobCard from '@/shared/components/JobCard.jsx'
import AnimatedContainer, { AnimatedStaggerContainer } from '@/shared/components/AnimatedContainer.jsx'
import { motion } from 'framer-motion'
import { FiAlertCircle, FiRefreshCw } from 'react-icons/fi'

import { isStaffRecruiter } from '@/core/permissions/rbac.js'

export default function Jobs() {
  const { jobs, applicantAuth, applicantProfile, jobsError, jobsLoading, fetchJobs, applicantApplications, applicantSavedJobs, toggleSaveJob, applyToJobAsApplicant, auth } = useApp()
  const location = useLocation()
  const navigate = useNavigate()
  const params = new URLSearchParams(location.search)
  const query = {
    keywords: params.get('q') || '',
    location: params.get('loc') || '',
  }
  const [applyError, setApplyError] = useState('')
  const [applyingJobId, setApplyingJobId] = useState(null)

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

  const handleSearch = ({ keywords, location }) => {
    const sp = new URLSearchParams()
    if (keywords) sp.set('q', keywords)
    if (location) sp.set('loc', location)
    navigate({ pathname: '/jobs', search: `?${sp.toString()}` }, { replace: false })
  }

  useEffect(() => {
    if (!jobsError) return
    const id = setTimeout(() => {
      fetchJobs()
    }, 5000)
    return () => clearTimeout(id)
  }, [jobsError, fetchJobs])

  return (
    <div className="max-w-7xl mx-auto px-6 py-10 bg-slate-50 min-h-screen">
      <AnimatedContainer animation="slideDown">
        <h2 className="text-3xl font-bold text-slate-900">Latest Jobs</h2>
        <p className="mt-1 text-slate-500">Discover your next career opportunity</p>
      </AnimatedContainer>

      {jobsError && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-6 rounded-2xl border border-red-200 bg-red-50 p-5"
        >
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <FiAlertCircle className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-red-700 font-medium">Unable to load jobs</p>
                  <p className="text-sm text-red-600 mt-1">Please check your connection and try again</p>
                </div>
              </div>
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={fetchJobs}
                disabled={jobsLoading}
                className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-all ${
                  jobsLoading ? 'bg-slate-300 text-slate-500 cursor-not-allowed' : 'bg-red-600 hover:bg-red-500 text-white shadow-md'
                }`}
              >
                <FiRefreshCw className={`w-4 h-4 ${jobsLoading ? 'animate-spin' : ''}`} />
                {jobsLoading ? 'Retrying…' : 'Retry'}
              </motion.button>
            </div>
          </motion.div>
        )}

        <AnimatedContainer animation="fadeIn" delay={0.2}>
          <div className="mt-6">
            <FilterBar onSearch={handleSearch} initial={query} />
          </div>
        </AnimatedContainer>

        {applyError && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 rounded-2xl border border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 p-4 flex items-start justify-between gap-4"
          >
            <div className="flex items-start gap-3">
              <FiAlertCircle className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-amber-800 dark:text-amber-200 font-medium">Could not apply</p>
                <p className="text-sm text-amber-700 dark:text-amber-300 mt-1">{applyError}</p>
                {(applyError.includes('profile') || applyError.includes('resume') || applyError.includes('education')) && (
                  <button
                    type="button"
                    onClick={() => { setApplyError(''); navigate('/profile/applicant') }}
                    className="mt-2 text-sm font-medium text-amber-700 dark:text-amber-300 hover:underline"
                  >
                    Complete profile →
                  </button>
                )}
              </div>
            </div>
            <button
              type="button"
              onClick={() => setApplyError('')}
              className="text-amber-600 dark:text-amber-400 hover:text-amber-700 dark:hover:text-amber-300 text-sm px-2"
              aria-label="Dismiss"
            >
              ×
            </button>
          </motion.div>
        )}

        <div className="mt-8">
          {filtered.length === 0 ? (
            <motion.div
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/80 p-12 text-center shadow-card"
            >
              <div className="w-20 h-20 mx-auto mb-4 rounded-2xl bg-slate-100 dark:bg-slate-700 flex items-center justify-center">
                <svg className="w-10 h-10 text-slate-400 dark:text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">No jobs found</h3>
              <p className="text-slate-500 dark:text-slate-400">Try adjusting your search criteria</p>
            </motion.div>
          ) : (
            <div className="grid gap-4">
              {filtered.map((job, index) => (
                <motion.div
                  key={job.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05 }}
                >
                  <JobCard
                    job={job}
                    isApplied={!!applicantApplications[job.id] || !!applicantApplications[String(job.id)]}
                    isSaved={!!applicantSavedJobs[job.id] || !!applicantSavedJobs[String(job.id)]}
                    isAdmin={isStaffRecruiter(auth)}
                    isApplying={applyingJobId === job.id}
                    onApply={async () => {
                      setApplyError('')
                      if (!applicantAuth.isLoggedIn) {
                        const qs = new URLSearchParams({ redirect: window.location.pathname + window.location.search, applyFor: job.id }).toString()
                        navigate(`/login?${qs}`)
                        return
                      }
                      if (!applicantProfile.completed) {
                        const qs = new URLSearchParams({ redirect: window.location.pathname + window.location.search, applyFor: job.id }).toString()
                        navigate(`/profile/applicant?${qs}`)
                        return
                      }
                      setApplyingJobId(job.id)
                      const result = await applyToJobAsApplicant(job.id)
                      setApplyingJobId(null)
                      if (result.ok) {
                        if (applicantSavedJobs[job.id] || applicantSavedJobs[String(job.id)]) {
                          toggleSaveJob(job.id)
                        }
                      } else {
                        const msg = result.reason === 'profile_requirements_missing'
                          ? 'Add a resume and at least one education entry (degree + institution) to your profile to apply.'
                          : (result.message || 'Failed to apply. Please try again.')
                        setApplyError(msg)
                      }
                    }}
                    onToggleSave={() => {
                      if (!applicantAuth.isLoggedIn) {
                        navigate('/login')
                        return
                      }
                      toggleSaveJob(job.id)
                    }}
                  />
                </motion.div>
              ))}
            </div>
          )}
        </div>
      </div>
  )
}
