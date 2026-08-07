import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useApp } from '@/core/context/AppContext.jsx'
import { useAsyncAction } from '@/shared/hooks/useAsyncAction.js'
import PasswordInput from '@/shared/components/PasswordInput.jsx'
import AuthPageLayout from '@/layouts/AuthPageLayout.jsx'
import { Input } from '@/shared/components/ui/Input.jsx'
import { ROLES, getRole } from '@/core/permissions/rbac.js'
import { FiShield, FiArrowLeft } from 'react-icons/fi'

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
      <div className="mb-5">
        <Link
          to="/"
          className="mb-4 inline-flex items-center gap-2 text-sm font-medium text-[var(--ei-text-muted)] transition-colors hover:text-[var(--ei-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#38A9FF]/40 rounded-lg"
        >
          <FiArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to home
        </Link>
        <h2 className="font-display text-[clamp(1.75rem,3vw,2.15rem)] font-bold tracking-tight text-[var(--ei-text-primary)]">
          Welcome back
        </h2>
        <p className="mt-1.5 text-[14px] sm:text-[15px] text-[var(--ei-text-secondary)]">
          Sign in to your HR Intelligence account
        </p>
      </div>

      <div className="auth-glass-card">
        <div
          className="mb-5 flex h-12 w-12 items-center justify-center rounded-[14px] border border-[rgba(67,158,255,0.2)]"
          style={{
            background: 'linear-gradient(135deg, rgba(0,166,255,0.18), rgba(92,72,255,0.18))',
          }}
        >
          <FiShield className="h-6 w-6 text-[#0284c7] dark:text-[#55B9FF]" aria-hidden="true" />
        </div>
        <h3 className="text-xl font-semibold text-[var(--ei-text-primary)]">Sign in</h3>
        <p className="mt-1 text-sm text-[var(--ei-text-secondary)]">HR, Head of HR, or Executive access</p>

        <form onSubmit={onAdminSubmit} className="mt-6 space-y-4">
          {adminError && (
            <div className="rounded-xl border border-[rgba(255,90,110,0.55)] bg-[rgba(255,102,133,0.1)] px-4 py-3 text-sm text-[#FF7B8E]">
              {adminError}
            </div>
          )}
          <div className="w-full">
            <label className="mb-1.5 block text-sm font-medium text-[var(--ei-text-label)]">Email</label>
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
            <div className="mb-1.5 flex items-center justify-between gap-3">
              <label className="block text-sm font-medium text-[var(--ei-text-label)]">Password</label>
              <Link
                to="/forgot-password/admin"
                className="text-sm font-medium text-[#55B9FF] transition-colors hover:underline"
              >
                Forgot password?
              </Link>
            </div>
            <PasswordInput
              className="input-premium h-12 min-h-[3rem] text-base"
              placeholder="••••••••"
              value={adminPassword}
              onChange={(e) => setAdminPassword(e.target.value)}
              required
            />
          </div>
          <button type="submit" disabled={loading} className="auth-cta mt-2">
            {loading ? (
              <span className="inline-flex items-center justify-center gap-2">
                <span className="spinner-premium w-4 h-4 border-2" />
                Signing in…
              </span>
            ) : (
              'Sign in'
            )}
          </button>
          <p className="pt-2 text-center text-sm text-[var(--ei-text-secondary)]">
            <Link to="/login" className="text-[var(--ei-text-muted)] transition-colors hover:text-[var(--ei-text-primary)]">
              ← Back to login
            </Link>
          </p>
        </form>
      </div>
    </AuthPageLayout>
  )
}
