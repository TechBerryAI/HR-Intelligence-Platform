import React from 'react'
import HeadHrLayout from './HeadHrLayout.jsx'
import Settings from '@/features/settings/pages/Settings.jsx'

export default function HeadHrSettings() {
  return (
    <HeadHrLayout>
      <div className="p-4 sm:p-6 lg:p-8 overflow-y-auto h-full">
        <Settings theme="enterprise" />
      </div>
    </HeadHrLayout>
  )
}
