import React, { useState } from 'react'
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useApp } from '@/core/context/AppContext.jsx'
import AuthPageLayout from '@/layouts/AuthPageLayout.jsx'
import { FiShield } from 'react-icons/fi'

const ALLOWED_EMAIL_DOMAIN = 'techberryinfotech.com'

function isTechberryStaffEmail(email) {
  const normalized = String(email || '').trim().toLowerCase()
  const at = normalized.lastIndexOf('@')
  if (at < 1) return false
  return normalized.slice(at + 1) === ALLOWED_EMAIL_DOMAIN
}

export default function ForgotPasswordVerify() {
  const { variant } = useParams()
  const { verifyHrPasswordOtp, resendHrPasswordOtp } = useApp()
  const [searchParams] = useSearchParams()
  const email = (searchParams.get('email') || '').trim().toLowerCase()
  const [otp, setOtp] = useState('')
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [resending, setResending] = useState(false)
  const navigate = useNavigate()

  if (variant !== 'admin') {
    return <Navigate to="/forgot-password/admin" replace />
  }

  if (email && !isTechberryStaffEmail(email)) {
    return <Navigate to="/forgot-password/admin" replace />
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setStatus('')
    setError('')
    if (!email || !isTechberryStaffEmail(email)) {
      setError('Invalid email')
      return
    }
    if (otp.length !== 6) {
      setError('Enter the 6-digit OTP from your email.')
      return
    }
    setLoading(true)
    const res = await verifyHrPasswordOtp({ email, otp })
    setLoading(false)
    if (res.ok) {
      setStatus('OTP verified. Continue to set a new password.')
      navigate(
        `/forgot-password/admin/reset?email=${encodeURIComponent(email)}&otp=${encodeURIComponent(otp)}`
      )
    } else {
      setError(res.message || 'OTP verification failed')
    }
  }

  const handleResend = async () => {
    if (!email || !isTechberryStaffEmail(email)) {
      setError('Invalid email')
      return
    }
    setError('')
    setStatus('')
    setResending(true)
    const res = await resendHrPasswordOtp(email)
    setResending(false)
    if (res.ok) {
      setStatus('A new OTP was sent to your email.')
      setOtp('')
    } else {
      setError(res.message || 'Failed to resend OTP')
    }
  }

  return (
    <AuthPageLayout
      title="Verify OTP"
      subtitle={email ? `We sent a code to ${email}.` : 'Enter the code from your email.'}
    >
      <div className="auth-glass-card">
        <div
          className="mb-5 flex h-12 w-12 items-center justify-center rounded-[14px] border border-[rgba(67,158,255,0.2)]"
          style={{
            background: 'linear-gradient(135deg, rgba(0,166,255,0.18), rgba(92,72,255,0.18))',
          }}
        >
          <FiShield className="h-6 w-6 text-[#0284c7] dark:text-[#55B9FF]" aria-hidden="true" />
        </div>
        <h2 className="text-xl font-semibold text-[var(--ei-text-primary)]">Enter verification code</h2>
        <p className="mt-1 text-sm text-[var(--ei-text-secondary)]">
          Check your inbox for the 6-digit OTP (valid 10 minutes).
        </p>

        {!email ? (
          <p className="mt-6 text-sm text-[#FF7B8E]">
            We could not detect your email. Please{' '}
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
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[var(--ei-text-label)]">Email</label>
              <input
                type="email"
                value={email}
                disabled
                className="input-premium opacity-70"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[var(--ei-text-label)]">OTP</label>
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={6}
                autoFocus
                className="input-premium text-center text-2xl tracking-widest font-mono"
                placeholder="000000"
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                required
              />
            </div>
            <button type="submit" className="auth-cta" disabled={loading || otp.length !== 6}>
              {loading ? 'Verifying…' : 'Verify OTP'}
            </button>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleResend}
                disabled={resending}
                className="flex-1 text-sm text-[#55B9FF] hover:underline disabled:opacity-50"
              >
                {resending ? 'Resending…' : 'Resend OTP'}
              </button>
              <Link
                to="/forgot-password/admin"
                className="flex-1 text-center text-sm text-[var(--ei-text-secondary)] hover:text-[var(--ei-text-primary)]"
              >
                ← Change email
              </Link>
            </div>
          </form>
        )}

        <p className="mt-4 text-center text-sm text-[var(--ei-text-secondary)]">
          <Link to="/login/admin" className="text-[var(--ei-text-muted)] hover:text-[var(--ei-text-primary)]">
            ← Back to login
          </Link>
        </p>
      </div>
    </AuthPageLayout>
  )
}
