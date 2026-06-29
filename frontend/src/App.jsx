import React, { lazy, Suspense, useEffect } from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { AppProvider, useApp } from './context/AppContext.jsx'
import Navbar from './components/Navbar.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import { ToastProvider, useToast } from './components/Toast.jsx'
import ConnectionStatus from './components/ConnectionStatus.jsx'

const Home = lazy(() => import('./pages/Home.jsx'))
const Jobs = lazy(() => import('./pages/Jobs.jsx'))
const Login = lazy(() => import('./pages/Login.jsx'))
const LoginApplicant = lazy(() => import('./pages/LoginApplicant.jsx'))
const LoginAdmin = lazy(() => import('./pages/LoginAdmin.jsx'))
const ForgotPasswordRequest = lazy(() => import('./pages/ForgotPasswordRequest.jsx'))
const ForgotPasswordVerify = lazy(() => import('./pages/ForgotPasswordVerify.jsx'))
const ForgotPasswordReset = lazy(() => import('./pages/ForgotPasswordReset.jsx'))
const SignupApplicant = lazy(() => import('./pages/SignupApplicant.jsx'))
const SignupAdmin = lazy(() => import('./pages/SignupAdmin.jsx'))
const Dashboard = lazy(() => import('./pages/Dashboard.jsx'))
const ApplicantProfile = lazy(() => import('./pages/ApplicantProfile.jsx'))
const ApplicationStatus = lazy(() => import('./pages/ApplicationStatus.jsx'))
const AppliedCandidates = lazy(() => import('./pages/AppliedCandidates.jsx'))
const BulkResumeParser = lazy(() => import('./pages/admin/BulkResumeParser.jsx'))
const FeedbackAdmin = lazy(() => import('./pages/admin/FeedbackAdmin.jsx'))
const FAQ = lazy(() => import('./pages/FAQ.jsx'))
const ContactUs = lazy(() => import('./pages/ContactUs.jsx'))
const HRMSTestingFeedback = lazy(() => import('./pages/HRMSTestingFeedback.jsx'))
const NotFound = lazy(() => import('./pages/NotFound.jsx'))
const HeadHrDashboard = lazy(() => import('./pages/head-hr/HeadHrDashboard.jsx'))
const HeadHrAdmins = lazy(() => import('./pages/head-hr/HeadHrAdmins.jsx'))
const HeadHrCandidates = lazy(() => import('./pages/head-hr/HeadHrCandidates.jsx'))
const HeadHrCandidateDetail = lazy(() => import('./pages/head-hr/HeadHrCandidateDetail.jsx'))
const HeadHrJobs = lazy(() => import('./pages/head-hr/HeadHrJobs.jsx'))
const HeadHrJobDetail = lazy(() => import('./pages/head-hr/HeadHrJobDetail.jsx'))
const HeadHrJobCandidateDetail = lazy(() => import('./pages/head-hr/HeadHrJobCandidateDetail.jsx'))
const HeadHrApplications = lazy(() => import('./pages/head-hr/HeadHrApplications.jsx'))
const HeadHrApplicationDetail = lazy(() => import('./pages/head-hr/HeadHrApplicationDetail.jsx'))
const HeadHrSettings = lazy(() => import('./pages/head-hr/HeadHrSettings.jsx'))
const Settings = lazy(() => import('./pages/Settings.jsx'))

import RecruiterGuard from './guards/RecruiterGuard.jsx'
import CandidateGuard from './guards/CandidateGuard.jsx'
import HeadHrGuard from './guards/HeadHrGuard.jsx'
import CeoGuard from './guards/CeoGuard.jsx'

const CeoDashboard = lazy(() => import('./pages/ceo/CeoDashboard.jsx'))

function StaffSettingsRoute({ children }) {
  const { auth } = useApp()
  const staffRoles = new Set(['RECRUITER', 'HEAD_HR', 'CEO'])
  if (!auth.isLoggedIn || !staffRoles.has(auth.role)) {
    return <Navigate to="/login/admin" replace />
  }
  return children
}

export default function App() {
  const location = useLocation()
  const isHeadHrRoute = location.pathname.startsWith('/head-hr')
  const isCeoRoute = location.pathname.startsWith('/ceo')
  const isLandingRoute = location.pathname === '/'
  const hideChrome = isHeadHrRoute || isCeoRoute || isLandingRoute

  return (
    <AppProvider>
      <ToastProvider>
        <ErrorBoundary>
          <ConnectionStatus />
          <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900">
            {!hideChrome && <Navbar />}
            <ErrorToasts />
            <main className={hideChrome ? 'flex-1 flex flex-col min-h-screen' : 'flex-1'}>
              <Suspense fallback={<div className="max-w-7xl mx-auto px-6 py-10"><div className="h-10 w-48 rounded-xl bg-slate-200 animate-pulse" /></div>}>
                <Routes>
                  <Route path="/" element={<Home />} />
                  <Route path="/jobs" element={<Jobs />} />
                  <Route path="/support/faq" element={<FAQ />} />
                  <Route path="/support/contact" element={<ContactUs />} />
                  <Route path="/support/hrms-feedback" element={<HRMSTestingFeedback />} />
                  <Route path="/login" element={<Login />} />
                  <Route path="/login/applicant" element={<LoginApplicant />} />
                  <Route path="/login/admin" element={<LoginAdmin />} />
                  <Route
                    path="/profile/applicant"
                    element={
                      <CandidateGuard>
                        <ApplicantProfile />
                      </CandidateGuard>
                    }
                  />
                  <Route
                    path="/settings/applicant"
                    element={
                      <CandidateGuard>
                        <Settings />
                      </CandidateGuard>
                    }
                  />
                  <Route path="/forgot-password/:variant" element={<ForgotPasswordRequest />} />
                  <Route path="/forgot-password/:variant/verify" element={<ForgotPasswordVerify />} />
                  <Route path="/forgot-password/:variant/reset" element={<ForgotPasswordReset />} />
                  <Route
                    path="/applications"
                    element={
                      <CandidateGuard>
                        <ApplicationStatus />
                      </CandidateGuard>
                    }
                  />
                  <Route path="/signup" element={<Navigate to="/signup/applicant" replace />} />
                  <Route path="/signup/applicant" element={<SignupApplicant />} />
                  <Route path="/signup/admin" element={<SignupAdmin />} />
                  <Route
                    path="/dashboard"
                    element={
                      <RecruiterGuard>
                        <Dashboard />
                      </RecruiterGuard>
                    }
                  />
                  <Route
                    path="/candidates"
                    element={
                      <RecruiterGuard>
                        <AppliedCandidates />
                      </RecruiterGuard>
                    }
                  />
                  <Route
                    path="/ceo"
                    element={
                      <CeoGuard>
                        <CeoDashboard />
                      </CeoGuard>
                    }
                  />
                  <Route path="/ceo/candidates" element={<Navigate to="/ceo/jobs" replace />} />
                  <Route path="/ceo/candidates/:cid" element={<Navigate to="/ceo/jobs" replace />} />
                  <Route path="/ceo/applications" element={<Navigate to="/ceo/jobs" replace />} />
                  <Route path="/ceo/applications/:id" element={<Navigate to="/ceo/jobs" replace />} />
                  <Route
                    path="/ceo/jobs/:jdid/candidates/:cid"
                    element={
                      <CeoGuard>
                        <HeadHrJobCandidateDetail />
                      </CeoGuard>
                    }
                  />
                  <Route
                    path="/ceo/jobs"
                    element={
                      <CeoGuard>
                        <HeadHrJobs />
                      </CeoGuard>
                    }
                  />
                  <Route
                    path="/ceo/jobs/:jdid"
                    element={
                      <CeoGuard>
                        <HeadHrJobDetail />
                      </CeoGuard>
                    }
                  />
                  <Route
                    path="/settings"
                    element={
                      <StaffSettingsRoute>
                        <Settings />
                      </StaffSettingsRoute>
                    }
                  />
                  <Route
                    path="/admin/bulk-resume-parser"
                    element={
                      <RecruiterGuard>
                        <BulkResumeParser />
                      </RecruiterGuard>
                    }
                  />
                  <Route
                    path="/admin/feedback"
                    element={
                      <RecruiterGuard>
                        <FeedbackAdmin />
                      </RecruiterGuard>
                    }
                  />
                  {/* Head of HR (HEAD_HR) uses /login/admin */}
                  <Route
                    path="/head-hr"
                    element={
                      <HeadHrGuard>
                        <HeadHrDashboard />
                      </HeadHrGuard>
                    }
                  />
                  <Route
                    path="/head-hr/admins"
                    element={
                      <HeadHrGuard>
                        <HeadHrAdmins />
                      </HeadHrGuard>
                    }
                  />
                  <Route path="/head-hr/candidates" element={<Navigate to="/head-hr/jobs" replace />} />
                  <Route path="/head-hr/candidates/:cid" element={<Navigate to="/head-hr/jobs" replace />} />
                  <Route path="/head-hr/applications" element={<Navigate to="/head-hr/jobs" replace />} />
                  <Route path="/head-hr/applications/:id" element={<Navigate to="/head-hr/jobs" replace />} />
                  <Route
                    path="/head-hr/jobs/:jdid/candidates/:cid"
                    element={
                      <HeadHrGuard>
                        <HeadHrJobCandidateDetail />
                      </HeadHrGuard>
                    }
                  />
                  <Route
                    path="/head-hr/jobs"
                    element={
                      <HeadHrGuard>
                        <HeadHrJobs />
                      </HeadHrGuard>
                    }
                  />
                  <Route
                    path="/head-hr/jobs/:jdid"
                    element={
                      <HeadHrGuard>
                        <HeadHrJobDetail />
                      </HeadHrGuard>
                    }
                  />
                  <Route
                    path="/head-hr/settings"
                    element={
                      <HeadHrGuard>
                        <HeadHrSettings />
                      </HeadHrGuard>
                    }
                  />
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </Suspense>
            </main>
            {!hideChrome && (
              <footer className="py-8 text-center text-sm text-slate-500 border-t border-slate-200">
                © {new Date().getFullYear()} Job Portal
              </footer>
            )}
          </div>
        </ErrorBoundary>
      </ToastProvider>
    </AppProvider>
  )
}

function ErrorToasts() {
  const { authError } = useApp()
  const toast = useToast()
  useEffect(() => {
    if (authError) toast.push(authError, { type: 'error' })
  }, [authError])
  return null
}
