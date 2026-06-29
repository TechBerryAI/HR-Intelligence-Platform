import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'
import { useAsyncAction } from '../hooks/useAsyncAction.js'
import PasswordInput from '../components/PasswordInput.jsx'
import AuthPageLayout from '../components/AuthPageLayout.jsx'
import { Input } from '../components/ui/Input.jsx'
import { ROLES, getRole } from '../utils/rbac.js'

export default function LoginAdmin() {
  const { loginHR, auth } = useApp()
  const navigate = useNavigate()
  const { run, loading } = useAsyncAction()
  const [adminEmail, setAdminEmail] = useState('')
  const [adminPassword, setAdminPassword] = useState('')
  const [adminError, setAdminError] = useState('')

  useEffect(() => {
    if (!auth.isLoggedIn) return
    const role = getRole(auth)
    if (role === ROLES.CEO) navigate('/ceo', { replace: true })
    else if (role === ROLES.HEAD_HR) navigate('/head-hr', { replace: true })
    else if (role === ROLES.RECRUITER) navigate('/dashboard', { replace: true })
  }, [auth.isLoggedIn, auth.role, navigate])

  const onAdminSubmit = (e) => {
    e.preventDefault()
    setAdminError('')
    run(async () => {
      const email = adminEmail.trim()
      const res = await loginHR(email, adminPassword)
      if (!res.ok) {
        setAdminError(res.message || 'Login failed')
        return
      }
      const role = res.user?.role || getRole({ isLoggedIn: true, role: res.user?.role })
      if (role === ROLES.CEO) navigate('/ceo')
      else if (role === ROLES.HEAD_HR) navigate('/head-hr')
      else navigate('/dashboard')
    })
  }

  if (auth.isLoggedIn && getRole(auth)) return null

  return (
    <AuthPageLayout
      title="HR / Admin Login"
      subtitle="Manage job postings, candidates, and analytics."
    >
      <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 shadow-premium p-6 sm:p-8">
        <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Sign in</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">HR, Head of HR, or Executive access</p>
        <form onSubmit={onAdminSubmit} className="mt-6 space-y-4">
          {adminError && (
            <div className="rounded-xl bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 px-4 py-3 text-sm text-red-700 dark:text-red-300">
              {adminError}
            </div>
          )}
          <div className="w-full">
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">Email</label>
            <Input
              type="email"
              className="input-premium h-12 min-h-[3rem] text-base"
              placeholder="hr@company.com"
              value={adminEmail}
              onChange={(e) => setAdminEmail(e.target.value)}
              required
            />
          </div>
          <div className="w-full">
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">Password</label>
            <PasswordInput
              className="input-premium h-12 min-h-[3rem] text-base"
              placeholder="••••••••"
              value={adminPassword}
              onChange={(e) => setAdminPassword(e.target.value)}
              required
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl bg-primary dark:bg-accent-blue text-white font-semibold py-3 px-4 hover:opacity-90 transition-opacity shadow-md disabled:opacity-70 disabled:cursor-not-allowed"
          >
            {loading ? (
              <span className="inline-flex items-center justify-center gap-2">
                <span className="spinner-premium w-4 h-4 border-2" />
                Signing in…
              </span>
            ) : (
              'Sign in'
            )}
          </button>
          <p className="text-center text-sm text-slate-500 dark:text-slate-400 pt-2">
            <Link to="/login" className="hover:text-primary dark:hover:text-accent-blue-light">← Back to login</Link>
          </p>
        </form>
      </div>
    </AuthPageLayout>
  )
}
