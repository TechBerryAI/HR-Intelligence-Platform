import React, { useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { useApp } from '@/core/context/AppContext.jsx'
import AuthPageLayout from '@/layouts/AuthPageLayout.jsx'
import { Input } from '@/shared/components/ui/Input.jsx'
import { FiKey } from 'react-icons/fi'

/** Staff password reset is limited to Techberry Infotech work emails. */
const ALLOWED_EMAIL_DOMAIN = 'techberryinfotech.com'

function isTechberryStaffEmail(email) {
  const normalized = String(email || '').trim().toLowerCase()
  const at = normalized.lastIndexOf('@')
  if (at < 1) return false
  return normalized.slice(at + 1) === ALLOWED_EMAIL_DOMAIN
}

export default function ForgotPasswordRequest() {
  const { variant } = useParams()
  const { requestHrPasswordReset } = useApp()
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  if (variant !== 'admin') {
    return <Navigate to="/forgot-password/admin" replace />
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setStatus('')
    setError('')
    const normalized = email.trim().toLowerCase()
    if (!isTechberryStaffEmail(normalized)) {
      setError('Invalid email')
      return
    }
    setLoading(true)
    const res = await requestHrPasswordReset(normalized)
    setLoading(false)
    if (res.ok) {
      setStatus('OTP sent to your email. Continue to verification.')
      navigate(`/forgot-password/admin/verify?email=${encodeURIComponent(normalized)}`)
    } else {
      setError(res.message || 'Failed to send OTP')
    }
  }

  return (
    <AuthPageLayout
      title="Forgot password"
      subtitle="We will email a one-time code so you can reset your staff password."
    >
      <div className="auth-glass-card">
        <div
          className="mb-5 flex h-12 w-12 items-center justify-center rounded-[14px] border border-[rgba(67,158,255,0.2)]"
          style={{
            background: 'linear-gradient(135deg, rgba(0,166,255,0.18), rgba(92,72,255,0.18))',
          }}
        >
          <FiKey className="h-6 w-6 text-[#0284c7] dark:text-[#55B9FF]" aria-hidden="true" />
        </div>
        <h2 className="text-xl font-semibold text-[var(--ei-text-primary)]">Reset with OTP</h2>
        <p className="mt-1 text-sm text-[var(--ei-text-secondary)]">
          Enter your Techberry Infotech work email (Recruiter, Head HR, or CEO).
        </p>

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
          <div>
            <label className="mb-1.5 block text-sm font-medium text-[var(--ei-text-label)]">Work email</label>
            <Input
              type="email"
              className="input-premium h-12 min-h-[3rem] text-base"
              placeholder="name@techberryinfotech.com"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value)
                if (error) setError('')
              }}
              required
              autoFocus
            />
          </div>
          <button type="submit" className="auth-cta" disabled={loading || !email.trim()}>
            {loading ? 'Sending OTP…' : 'Send OTP'}
          </button>
          <p className="pt-1 text-center text-sm text-[var(--ei-text-secondary)]">
            Remembered your password?{' '}
            <Link to="/login/admin" className="text-[#55B9FF] hover:underline">
              Back to login
            </Link>
          </p>
        </form>
      </div>
    </AuthPageLayout>
  )
}
