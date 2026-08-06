import React from 'react'
import { useApp } from '@/core/context/AppContext.jsx'
import AnimatedContainer from '@/shared/components/AnimatedContainer.jsx'
import { PageContainer } from '@/shared/components/PageContainer.jsx'
import RecruiterJobDashboard from '@/features/dashboard/components/recruiter/RecruiterJobDashboard.jsx'
import ExternalPublishingSection from '@/features/dashboard/components/ExternalPublishingSection.jsx'
import { FiBriefcase, FiLayers } from 'react-icons/fi'

function EnterpriseStatCard({ title, value, subtitle, icon: Icon }) {
  return (
    <div className="org-glass-card hover:transform-none p-5 sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-[var(--ei-text-muted)]">{title}</p>
          <p className="mt-1 text-3xl font-bold text-[var(--ei-text-primary)] tabular-nums">{value ?? '—'}</p>
          {subtitle && <p className="mt-0.5 text-xs text-[var(--ei-text-muted)]">{subtitle}</p>}
        </div>
        {Icon && (
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[var(--ei-surface-hover)] text-[#55B9FF] ring-1 ring-[var(--ei-border-primary)]">
            <Icon className="h-6 w-6" />
          </div>
        )}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { jobs } = useApp()
  const activeJobs = jobs.filter((j) => j.enabled !== false).length

  return (
    <PageContainer className="max-w-5xl">
      <AnimatedContainer animation="slideDown">
        <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--ei-text-muted)]">
              Recruiter workspace
            </p>
            <h2 className="mt-1 text-3xl font-bold text-[var(--ei-text-primary)] tracking-tight">
              Job Posting Dashboard
            </h2>
            <p className="mt-1.5 text-sm text-[var(--ei-text-secondary)]">
              Create and manage your company job postings
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 sm:gap-6 mb-8">
          <EnterpriseStatCard title="Total jobs" value={jobs.length} icon={FiBriefcase} />
          <EnterpriseStatCard title="Active" value={activeJobs} subtitle="Currently visible" icon={FiLayers} />
        </div>
      </AnimatedContainer>

      <ExternalPublishingSection />

      {/* Match Head HR enterprise glass surfaces */}
      <RecruiterJobDashboard embedded />
    </PageContainer>
  )
}
