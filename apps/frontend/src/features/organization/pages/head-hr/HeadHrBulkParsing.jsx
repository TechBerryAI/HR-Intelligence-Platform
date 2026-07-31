import React from 'react'
import HeadHrLayout from './HeadHrLayout.jsx'
import BulkResumeParser from '@/features/admin/pages/admin/BulkResumeParser.jsx'

export default function HeadHrBulkParsing() {
  return (
    <HeadHrLayout>
      <BulkResumeParser embedded />
    </HeadHrLayout>
  )
}
