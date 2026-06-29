import React from 'react'
import { useApp } from '../context/AppContext.jsx'
import AnimatedContainer from '../components/AnimatedContainer.jsx'
import { StatCard } from '../components/ui/index.js'
import { PageContainer } from '../components/PageContainer.jsx'
import RecruiterJobDashboard from '../components/recruiter/RecruiterJobDashboard.jsx'
import { FiBriefcase, FiLayers } from 'react-icons/fi'

export default function Dashboard() {
  const { jobs } = useApp()
  const activeJobs = jobs.filter((j) => j.enabled !== false).length

  return (
    <PageContainer className="max-w-5xl">
      <AnimatedContainer animation="slideDown">
        <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-3xl font-bold text-slate-900 dark:text-white">Job Posting Dashboard</h2>
            <p className="mt-1 text-slate-500 dark:text-slate-400">Create and manage your job postings</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 mb-8">
          <StatCard title="Total jobs" value={jobs.length} icon={FiBriefcase} />
          <StatCard title="Active" value={activeJobs} subtitle="Currently visible" icon={FiLayers} />
        </div>
      </AnimatedContainer>

      <RecruiterJobDashboard />
    </PageContainer>
  )
}
