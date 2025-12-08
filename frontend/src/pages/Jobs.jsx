import React, { useMemo, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'
import FilterBar from '../components/FilterBar.jsx'
import JobCard from '../components/JobCard.jsx'

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
    <section className="py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <h2 className="text-2xl font-bold text-gray-100">Latest Jobs</h2>
        {jobsError && (
          <div className="mt-4 flex items-start justify-between rounded-lg border border-red-600/40 bg-red-950/50 text-red-200 px-4 py-3">
            <div className="pr-3">Unable to load jobs. Please try again.</div>
            <button
              onClick={fetchJobs}
              disabled={jobsLoading}
              className={`ml-4 inline-flex items-center rounded-md px-3 py-1.5 text-sm font-medium ${jobsLoading ? 'bg-red-900/40 text-red-300 cursor-not-allowed' : 'bg-red-700 hover:bg-red-600 text-white'}`}
            >
              {jobsLoading ? 'Retrying…' : 'Retry'}
            </button>
          </div>
        )}
        <div className="mt-4">
          <FilterBar onSearch={handleSearch} initial={query} />
        </div>

        <div className="mt-6 grid gap-4">
          {filtered.length === 0 ? (
            <div className="text-gray-400">No jobs found. Try different search.</div>
          ) : (
            filtered.map((job) => (
              <JobCard
                key={job.id}
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
                  // If profile is completed, apply directly
                  if (applicantProfile.completed) {
                    const result = await applyToJobAsApplicant(job.id)
                    // If successfully applied and job was saved, unsave it
                    if (result.ok && (applicantSavedJobs[job.id] || applicantSavedJobs[String(job.id)])) {
                      toggleSaveJob(job.id)
                    }
                  } else {
                    // Redirect to profile page to complete
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
            ))
          )}
        </div>
      </div>
      {/* Application overlay removed; flow proceeds via applicant profile */}
    </section>
  )
}


