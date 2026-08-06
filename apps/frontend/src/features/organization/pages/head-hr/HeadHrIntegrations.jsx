import React from 'react'
import HeadHrLayout from '@/features/organization/pages/head-hr/HeadHrLayout.jsx'
import IntegrationsDashboard from '@/features/dashboard/pages/IntegrationsDashboard.jsx'

export default function HeadHrIntegrations() {
  return (
    <HeadHrLayout>
      <IntegrationsDashboard embedded />
    </HeadHrLayout>
  )
}
