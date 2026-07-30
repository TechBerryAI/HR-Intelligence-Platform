import React, { lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import RecruiterGuard from '@/core/auth/RecruiterGuard.jsx'
import HeadHrGuard from '@/core/auth/HeadHrGuard.jsx'
import CeoGuard from '@/core/auth/CeoGuard.jsx'
import { useApp } from '@/core/context/AppContext.jsx'

const Home = lazy(() => import('@/features/jobs/pages/Home.jsx'))
const Jobs = lazy(() => import('@/features/jobs/pages/Jobs.jsx'))
const Login = lazy(() => import('@/features/auth/pages/Login.jsx'))
const LoginAdmin = lazy(() => import('@/features/auth/pages/LoginAdmin.jsx'))
const ForgotPasswordRequest = lazy(() => import('@/features/auth/pages/ForgotPasswordRequest.jsx'))
const ForgotPasswordVerify = lazy(() => import('@/features/auth/pages/ForgotPasswordVerify.jsx'))
const ForgotPasswordReset = lazy(() => import('@/features/auth/pages/ForgotPasswordReset.jsx'))
const SignupAdmin = lazy(() => import('@/features/auth/pages/SignupAdmin.jsx'))
const Dashboard = lazy(() => import('@/features/dashboard/pages/Dashboard.jsx'))
const AppliedCandidates = lazy(() => import('@/features/dashboard/pages/AppliedCandidates.jsx'))
const BulkResumeParser = lazy(() => import('@/features/admin/pages/admin/BulkResumeParser.jsx'))
const FeedbackAdmin = lazy(() => import('@/features/admin/pages/admin/FeedbackAdmin.jsx'))
const FAQ = lazy(() => import('@/features/support/pages/FAQ.jsx'))
const ContactUs = lazy(() => import('@/features/support/pages/ContactUs.jsx'))
const HRMSTestingFeedback = lazy(() => import('@/features/support/pages/HRMSTestingFeedback.jsx'))
const NotFound = lazy(() => import('@/features/auth/pages/NotFound.jsx'))
const HeadHrDashboard = lazy(() => import('@/features/organization/pages/head-hr/HeadHrDashboard.jsx'))
const HeadHrAdmins = lazy(() => import('@/features/organization/pages/head-hr/HeadHrAdmins.jsx'))
const HeadHrJobCandidateDetail = lazy(() => import('@/features/organization/pages/head-hr/HeadHrJobCandidateDetail.jsx'))
const HeadHrJobs = lazy(() => import('@/features/organization/pages/head-hr/HeadHrJobs.jsx'))
const HeadHrJobDetail = lazy(() => import('@/features/organization/pages/head-hr/HeadHrJobDetail.jsx'))
const HeadHrSettings = lazy(() => import('@/features/organization/pages/head-hr/HeadHrSettings.jsx'))
const Settings = lazy(() => import('@/features/settings/pages/Settings.jsx'))
const CeoDashboard = lazy(() => import('@/features/organization/pages/ceo/CeoDashboard.jsx'))

function StaffSettingsRoute({ children }) {
  const { auth } = useApp()
  const staffRoles = new Set(['RECRUITER', 'HEAD_HR', 'CEO'])
  if (!auth.isLoggedIn || !staffRoles.has(auth.role)) {
    return <Navigate to="/login/admin" replace />
  }
  return children
}

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/jobs" element={<Jobs />} />
      <Route path="/support/faq" element={<FAQ />} />
      <Route path="/support/contact" element={<ContactUs />} />
      <Route path="/support/hrms-feedback" element={<HRMSTestingFeedback />} />
      <Route path="/login" element={<Login />} />
      <Route path="/login/admin" element={<LoginAdmin />} />
      <Route path="/forgot-password/:variant" element={<ForgotPasswordRequest />} />
      <Route path="/forgot-password/:variant/verify" element={<ForgotPasswordVerify />} />
      <Route path="/forgot-password/:variant/reset" element={<ForgotPasswordReset />} />
      <Route path="/signup" element={<Navigate to="/signup/admin" replace />} />
      <Route path="/signup/admin" element={<SignupAdmin />} />
      <Route path="/dashboard" element={<RecruiterGuard><Dashboard /></RecruiterGuard>} />
      <Route path="/candidates" element={<RecruiterGuard><AppliedCandidates /></RecruiterGuard>} />
      <Route path="/ceo" element={<CeoGuard><CeoDashboard /></CeoGuard>} />
      <Route path="/ceo/candidates" element={<Navigate to="/ceo/jobs" replace />} />
      <Route path="/ceo/candidates/:cid" element={<Navigate to="/ceo/jobs" replace />} />
      <Route path="/ceo/applications" element={<Navigate to="/ceo/jobs" replace />} />
      <Route path="/ceo/applications/:id" element={<Navigate to="/ceo/jobs" replace />} />
      <Route path="/ceo/jobs/:jdid/candidates/:cid" element={<CeoGuard><HeadHrJobCandidateDetail /></CeoGuard>} />
      <Route path="/ceo/jobs" element={<CeoGuard><HeadHrJobs /></CeoGuard>} />
      <Route path="/ceo/jobs/:jdid" element={<CeoGuard><HeadHrJobDetail /></CeoGuard>} />
      <Route path="/settings" element={<StaffSettingsRoute><Settings /></StaffSettingsRoute>} />
      <Route path="/admin/bulk-resume-parser" element={<RecruiterGuard><BulkResumeParser /></RecruiterGuard>} />
      <Route path="/admin/feedback" element={<RecruiterGuard><FeedbackAdmin /></RecruiterGuard>} />
      <Route path="/head-hr" element={<HeadHrGuard><HeadHrDashboard /></HeadHrGuard>} />
      <Route path="/head-hr/admins" element={<HeadHrGuard><HeadHrAdmins /></HeadHrGuard>} />
      <Route path="/head-hr/candidates" element={<Navigate to="/head-hr/jobs" replace />} />
      <Route path="/head-hr/candidates/:cid" element={<Navigate to="/head-hr/jobs" replace />} />
      <Route path="/head-hr/applications" element={<Navigate to="/head-hr/jobs" replace />} />
      <Route path="/head-hr/applications/:id" element={<Navigate to="/head-hr/jobs" replace />} />
      <Route path="/head-hr/jobs/:jdid/candidates/:cid" element={<HeadHrGuard><HeadHrJobCandidateDetail /></HeadHrGuard>} />
      <Route path="/head-hr/jobs" element={<HeadHrGuard><HeadHrJobs /></HeadHrGuard>} />
      <Route path="/head-hr/jobs/:jdid" element={<HeadHrGuard><HeadHrJobDetail /></HeadHrGuard>} />
      <Route path="/head-hr/settings" element={<HeadHrGuard><HeadHrSettings /></HeadHrGuard>} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
