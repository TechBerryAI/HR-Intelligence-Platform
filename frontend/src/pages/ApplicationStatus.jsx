import React, { useMemo, useEffect, useState } from 'react'
import { useApp } from '../context/AppContext.jsx'
import JobCard from '../components/JobCard.jsx'

export default function ApplicationStatus() {
  const { jobs, applicantApplications, applicantSavedJobs, toggleSaveJob, applyToJobAsApplicant, applicantProfile, fetchApplicantData, applicantAuth } = useApp()
  const [activeTab, setActiveTab] = useState('applied')

  // Refresh applications data when component mounts or when logged in
  useEffect(() => {
    if (applicantAuth.isLoggedIn && fetchApplicantData) {
      fetchApplicantData()
    }
  }, [applicantAuth.isLoggedIn, fetchApplicantData])

  const appliedJobs = useMemo(() => {
    return jobs.filter(j => {
      // Check both number and string keys
      return applicantApplications[j.id] || applicantApplications[String(j.id)]
    })
  }, [jobs, applicantApplications])

  const savedJobs = useMemo(() => {
    return jobs.filter(j => {
      const isSaved = applicantSavedJobs[j.id] || applicantSavedJobs[String(j.id)]
      const isApplied = applicantApplications[j.id] || applicantApplications[String(j.id)]
      // Show only saved jobs that are not applied
      return isSaved && !isApplied
    })
  }, [jobs, applicantSavedJobs, applicantApplications])

  const list = activeTab === 'applied' ? appliedJobs : savedJobs
  const appliedCount = appliedJobs.length
  const savedCount = savedJobs.length

  return (
    <section className="py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <h2 className="text-2xl font-bold text-gray-100">My Applications</h2>

        {/* Tabs */}
        <div className="mt-6 border-b border-zinc-800">
          <div className="flex gap-6">
            <button
              onClick={() => setActiveTab('applied')}
              className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'applied'
                  ? 'border-white text-white'
                  : 'border-transparent text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Applied Jobs ({appliedCount})
            </button>
            <button
              onClick={() => setActiveTab('saved')}
              className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'saved'
                  ? 'border-white text-white'
                  : 'border-transparent text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Saved Jobs ({savedCount})
            </button>
          </div>
        </div>

        <div className="mt-6 grid gap-4">
          {list.length === 0 ? (
            <div className="text-zinc-400">
              {activeTab === 'applied' ? 'No applied jobs yet.' : 'No saved jobs yet.'}
            </div>
          ) : (
            list.map(job => (
              <JobCard
                key={job.id}
                job={job}
                isApplied={!!applicantApplications[job.id] || !!applicantApplications[String(job.id)]}
                isSaved={!!applicantSavedJobs[job.id] || !!applicantSavedJobs[String(job.id)]}
                onApply={async () => {
                  // Only allow applying from saved jobs tab
                  if (activeTab === 'saved' && applicantProfile.completed) {
                    const result = await applyToJobAsApplicant(job.id)
                    // If successfully applied and job was saved, unsave it
                    if (result.ok && (applicantSavedJobs[job.id] || applicantSavedJobs[String(job.id)])) {
                      toggleSaveJob(job.id)
                    }
                  }
                }}
                onToggleSave={() => toggleSaveJob(job.id)}
              />
            ))
          )}
        </div>

      </div>
    </section>
  )
}
