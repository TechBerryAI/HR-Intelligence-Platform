import React, { useMemo, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'
import FilterBar from '../components/FilterBar.jsx'
import JobCard from '../components/JobCard.jsx'
import AnimatedContainer, { AnimatedStaggerContainer } from '../components/AnimatedContainer.jsx'
import { motion } from 'framer-motion'
import { FiAlertCircle, FiRefreshCw } from 'react-icons/fi'

export default function Jobs() {
  const { jobs, applicantAuth, applicantProfile, jobsError, jobsLoading, fetchJobs, applicantApplications, applicantSavedJobs, toggleSaveJob, applyToJobAsApplicant, auth } = useApp()
  const location = useLocation()
  const navigate = useNavigate()
  const params = new URLSearchParams(location.search)
  const query = {
    keywords: params.get('q') || '',
    location: params.get('loc') || '',
  }

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
    <section className="py-8 relative min-h-screen">
      {/* Animated background */}
      <div className="pointer-events-none absolute inset-0">
        <motion.div
          animate={{
            scale: [1, 1.1, 1],
            opacity: [0.1, 0.2, 0.1],
          }}
          transition={{ duration: 15, repeat: Infinity }}
          className="absolute top-40 left-20 h-96 w-96 rounded-full bg-purple-500/20 blur-3xl"
        />
        <motion.div
          animate={{
            scale: [1.1, 1, 1.1],
            opacity: [0.1, 0.2, 0.1],
          }}
          transition={{ duration: 18, repeat: Infinity }}
          className="absolute bottom-40 right-20 h-96 w-96 rounded-full bg-blue-500/20 blur-3xl"
        />
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <AnimatedContainer animation="slideDown">
          <h2 className="text-4xl font-bold bg-gradient-to-r from-white to-zinc-400 bg-clip-text text-transparent">
            Latest Jobs
          </h2>
          <p className="mt-2 text-zinc-400">Discover your next career opportunity</p>
        </AnimatedContainer>

        {jobsError && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 glass-card border-2 border-red-500/30 bg-red-500/10 rounded-2xl p-5"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <FiAlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-red-300 font-medium">Unable to load jobs</p>
                  <p className="text-sm text-red-400 mt-1">Please check your connection and try again</p>
                </div>
              </div>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={fetchJobs}
                disabled={jobsLoading}
                className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-all ${
                  jobsLoading 
                    ? 'bg-red-900/40 text-red-300 cursor-not-allowed' 
                    : 'bg-red-600 hover:bg-red-500 text-white shadow-glow-sm'
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

        <div className="mt-8">
          {filtered.length === 0 ? (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="glass-card rounded-2xl p-12 text-center"
            >
              <div className="w-20 h-20 mx-auto mb-4 bg-gradient-to-r from-purple-600/20 to-blue-600/20 rounded-full flex items-center justify-center">
                <svg className="w-10 h-10 text-zinc-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <h3 className="text-xl font-semibold text-white mb-2">No jobs found</h3>
              <p className="text-zinc-400">Try adjusting your search criteria</p>
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
                    isAdmin={auth.role === 'HR' || auth.role === 'admin'}
                    onApply={async () => {
                      if (!applicantAuth.isLoggedIn) {
                        const qs = new URLSearchParams({ redirect: window.location.pathname + window.location.search, applyFor: job.id }).toString()
                        navigate(`/login/applicant?${qs}`)
                        return
                      }
                      if (applicantProfile.completed) {
                        const result = await applyToJobAsApplicant(job.id)
                        if (result.ok && (applicantSavedJobs[job.id] || applicantSavedJobs[String(job.id)])) {
                          toggleSaveJob(job.id)
                        }
                      } else {
                        const qs = new URLSearchParams({ redirect: window.location.pathname + window.location.search, applyFor: job.id }).toString()
                        navigate(`/profile/applicant?${qs}`)
                      }
                    }}
                    onToggleSave={() => {
                      if (!applicantAuth.isLoggedIn) {
                        navigate('/login/applicant')
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
    </section>
  )
}
