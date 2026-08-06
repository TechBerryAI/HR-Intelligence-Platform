import React, { useState } from 'react'
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useApp } from '@/core/context/AppContext.jsx'
import AuthPageLayout from '@/layouts/AuthPageLayout.jsx'
import PasswordInput from '@/shared/components/PasswordInput.jsx'
import { PASSWORD_RULES, isPasswordStrong } from '@/shared/utils/passwordValidation.js'
import { FiCheck, FiLock, FiX } from 'react-icons/fi'

export default function ForgotPasswordReset() {
  const { variant } = useParams()
  const { resetHrPassword } = useApp()
  const [searchParams] = useSearchParams()
  const email = (searchParams.get('email') || '').trim().toLowerCase()
  const otp = (searchParams.get('otp') || '').trim()

  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  if (variant !== 'admin') {
    return <Navigate to="/forgot-password/admin" replace />
  }

  const newPasswordValid = isPasswordStrong(newPassword)
  const confirmMatches = Boolean(newPassword && newPassword === confirmPassword)
  const canSubmit = email && otp && newPasswordValid && confirmMatches && !loading

  const handleSubmit = async (event) => {
    event.preventDefault()
    setStatus('')
    setError('')
    if (!email || !otp) {
      setError('Missing verification data. Please restart the reset process.')
      return
    }
    if (!newPasswordValid) {
      setError('New password must meet all requirements below.')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }
    setLoading(true)
    const res = await resetHrPassword({ email, otp, newPassword, confirmPassword })
    setLoading(false)
    if (res.ok) {
      setStatus('Password updated. Redirecting to login…')
      setTimeout(() => navigate('/login/admin'), 1200)
    } else {
      setError(res.message || 'Failed to reset password')
    }
  }

  return (
    <AuthPageLayout
      title="Set new password"
      subtitle="Choose a strong password you have not used before."
    >
      <div className="auth-glass-card">
        <div
          className="mb-5 flex h-12 w-12 items-center justify-center rounded-[14px] border border-[rgba(67,158,255,0.2)]"
          style={{
            background: 'linear-gradient(135deg, rgba(0,166,255,0.18), rgba(92,72,255,0.18))',
          }}
        >
          <FiLock className="h-6 w-6 text-[#0284c7] dark:text-[#55B9FF]" aria-hidden="true" />
        </div>
        <h2 className="text-xl font-semibold text-[var(--ei-text-primary)]">Create new password</h2>
        <p className="mt-1 text-sm text-[var(--ei-text-secondary)]">
          After saving, sign in with your new password.
        </p>

        {(!email || !otp) ? (
          <p className="mt-6 text-sm text-[#FF7B8E]">
            We could not detect your verified OTP. Please{' '}
            <Link to="/forgot-password/admin" className="underline text-[var(--ei-text-primary)]">
              restart password reset
            </Link>
            .
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            {error && (
              <div className="rounded-xl border border-[rgba(255,90,110,0.55)] bg-[rgba(255,102,133,0.1)] px-4 py-3 text-sm text-[#FF7B8E]">
                {error}
              </div>
            )}
            {status && (
              <div className="rounded-xl border border-[rgba(54,214,160,0.4)] bg-[rgba(54,214,160,0.1)] px-4 py-3 text-sm text-[#36D6A0]">
                {status}
              </div>
            )}
            <p className="text-xs text-[var(--ei-text-muted)]">New password must meet all of the following:</p>
            <ul className="space-y-1.5">
              {PASSWORD_RULES.map(({ id, label, test }) => {
                const pass = test(newPassword)
                return (
                  <li key={id} className="flex items-center gap-2 text-xs">
                    {pass ? (
                      <FiCheck className="h-3.5 w-3.5 flex-shrink-0 text-green-400" />
                    ) : (
                      <FiX className="h-3.5 w-3.5 flex-shrink-0 text-[var(--ei-text-muted)]" />
                    )}
                    <span className={pass ? 'text-[var(--ei-text-secondary)]' : 'text-[var(--ei-text-muted)]'}>
                      {label}
                    </span>
                  </li>
                )
              })}
            </ul>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[var(--ei-text-label)]">New password</label>
              <PasswordInput
                className="input-premium"
                placeholder="Meet all requirements above"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                minLength={8}
                required
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[var(--ei-text-label)]">Confirm password</label>
              <PasswordInput
                className="input-premium"
                placeholder="Confirm new password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                minLength={8}
                required
              />
            </div>
            <button type="submit" className="auth-cta" disabled={!canSubmit}>
              {loading ? 'Updating…' : 'Reset password'}
            </button>
            <p className="text-center text-sm text-[var(--ei-text-secondary)]">
              <Link
                to={`/forgot-password/admin/verify?email=${encodeURIComponent(email || '')}`}
                className="text-[var(--ei-text-muted)] hover:text-[var(--ei-text-primary)]"
              >
                ← Back to OTP verification
              </Link>
            </p>
          </form>
        )}
      </div>
    </AuthPageLayout>
  )
}
