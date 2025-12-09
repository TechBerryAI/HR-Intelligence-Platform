import React, { lazy, Suspense, useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
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
const NotFound = lazy(() => import('./pages/NotFound.jsx'))

function PrivateRoute({ children }) {
  const { auth } = useApp()
  return auth.isLoggedIn && auth.role === 'HR' ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <AppProvider>
      <ToastProvider>
        <ErrorBoundary>
          <ConnectionStatus />
          <div className="min-h-screen flex flex-col bg-zinc-950 text-gray-100">
            <Navbar />
            <ErrorToasts />
            <main className="flex-1">
              <Suspense fallback={<div className="p-6">Loading...</div>}>
                <Routes>
                  <Route path="/" element={<Home />} />
                  <Route path="/jobs" element={<Jobs />} />
                  <Route path="/login" element={<Login />} />
                  <Route path="/login/applicant" element={<LoginApplicant />} />
                  <Route path="/login/admin" element={<LoginAdmin />} />
                  <Route path="/profile/applicant" element={<ApplicantProfile />} />
                  <Route path="/forgot-password/:variant" element={<ForgotPasswordRequest />} />
                  <Route path="/forgot-password/:variant/verify" element={<ForgotPasswordVerify />} />
                  <Route path="/forgot-password/:variant/reset" element={<ForgotPasswordReset />} />
                  <Route path="/applications" element={<ApplicationStatus />} />
                  <Route path="/signup" element={<Navigate to="/signup/applicant" replace />} />
                  <Route path="/signup/applicant" element={<SignupApplicant />} />
                  <Route path="/signup/admin" element={<SignupAdmin />} />
                  <Route
                    path="/dashboard"
                    element={
                      <PrivateRoute>
                        <Dashboard />
                      </PrivateRoute>
                    }
                  />
                  <Route
                    path="/candidates"
                    element={
                      <PrivateRoute>
                        <AppliedCandidates />
                      </PrivateRoute>
                    }
                  />
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </Suspense>
            </main>
            <footer className="py-10 text-center text-sm text-zinc-500"> {new Date().getFullYear()} Job Portal</footer>
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
