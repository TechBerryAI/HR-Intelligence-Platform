import React, { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useApp } from '@/core/context/AppContext.jsx'
import PasswordInput from '@/shared/components/PasswordInput.jsx'
import AuthPageLayout from '@/layouts/AuthPageLayout.jsx'

export default function LoginApplicant() {
  const navigate = useNavigate()
  const location = useLocation()
  const { loginApplicant } = useApp()
  const [applicantId, setApplicantId] = useState('')
  const [applicantPassword, setApplicantPassword] = useState('')
  const [error, setError] = useState('')

  const onApplicantSubmit = async (e) => {
    e.preventDefault()
    setError('')
    const res = await loginApplicant(applicantId, applicantPassword)
    if (res.ok) {
      const sp = new URLSearchParams(location.search)
      const redirectTo = sp.get('redirect') || '/jobs'
      const applyFor = sp.get('applyFor')
      const profileUrl = new URLSearchParams({ redirect: applyFor ? `${redirectTo}${redirectTo.includes('?') ? '&' : '?'}applyFor=${applyFor}` : redirectTo }).toString()
      navigate(`/profile/applicant?${profileUrl}`)
    } else {
      setError(res.message || 'Login failed')
    }
  }

  return (
    <AuthPageLayout
      title="Applicant Login"
      subtitle="Sign in to apply for jobs, track applications, and manage your profile."
    >
      <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 shadow-premium p-6 sm:p-8">
        <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Sign in</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Use your email or username</p>
        <form onSubmit={onApplicantSubmit} className="mt-6 space-y-4">
          {error && (
            <div className="rounded-xl bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 px-4 py-3 text-sm text-red-700 dark:text-red-300">
              {error}
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">Email or Username</label>
            <input
              type="text"
              className="input-premium"
              placeholder="you@example.com"
              value={applicantId}
              onChange={(e) => setApplicantId(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">Password</label>
            <PasswordInput
              className="input-premium"
              placeholder="••••••••"
              value={applicantPassword}
              onChange={(e) => setApplicantPassword(e.target.value)}
              required
            />
          </div>
          <button
            type="submit"
            className="w-full rounded-xl bg-primary dark:bg-accent-blue text-white font-semibold py-3 px-4 hover:opacity-90 transition-opacity shadow-md"
          >
            Sign in
          </button>
          <div className="flex items-center justify-between text-sm pt-2">
            <Link to="/forgot-password/applicant" className="text-slate-500 dark:text-slate-400 hover:text-primary dark:hover:text-accent-blue-light">
              Forgot password?
            </Link>
            <Link to="/signup/applicant" className="font-medium text-primary dark:text-accent-blue-light hover:underline">
              Create account
            </Link>
          </div>
        </form>
      </div>
    </AuthPageLayout>
  )
}
