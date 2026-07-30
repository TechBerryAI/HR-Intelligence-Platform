import React, { useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useApp } from '@/core/context/AppContext.jsx'
import PasswordInput from '@/shared/components/PasswordInput.jsx'
import { PASSWORD_RULES, isPasswordStrong } from '@/shared/utils/passwordValidation.js'
import { FiCheck, FiX } from 'react-icons/fi'

export default function ForgotPasswordReset() {
  const { variant = 'applicant' } = useParams()
  const isAdmin = variant === 'admin'
  const { resetApplicantPassword, resetHrPassword } = useApp()
  const resetPassword = isAdmin ? resetHrPassword : resetApplicantPassword

  const [searchParams] = useSearchParams()
  const email = (searchParams.get('email') || '').trim().toLowerCase()
  const otp = (searchParams.get('otp') || '').trim()

  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const newPasswordValid = isPasswordStrong(newPassword)
  const confirmMatches = newPassword && newPassword === confirmPassword
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
    const res = await resetPassword({ email, otp, newPassword, confirmPassword })
    setLoading(false)
    if (res.ok) {
      setStatus('Password updated successfully. Redirecting to login...')
      setTimeout(() => navigate(isAdmin ? '/login/admin' : '/login'), 1200)
    } else {
      setError(res.message || 'Failed to reset password')
    }
  }

  const title = isAdmin ? 'Set New Admin Password' : 'Set New Applicant Password'
  const subtitle = 'Choose a strong password you have not used before.'

  return (
    <section className="relative min-h-[calc(100vh-180px)] flex items-center justify-center px-4 py-10 overflow-hidden">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-24 -left-24 h-72 w-72 rounded-full bg-white/10 blur-3xl" />
        <div className="absolute -bottom-24 -right-24 h-80 w-80 rounded-full bg-white/10 blur-3xl" />
        <div
          className="absolute inset-0 opacity-[0.07]"
          style={{ backgroundImage: 'radial-gradient(circle at 1px 1px, #fff 1px, transparent 0)', backgroundSize: '24px 24px' }}
        />
      </div>

      <div className="w-full max-w-xl relative">
        <div className="rounded-2xl bg-gradient-to-br from-zinc-900/90 via-zinc-900/70 to-zinc-900/50 p-[1px] shadow-2xl">
          <div className="rounded-2xl bg-zinc-950/70 backdrop-blur-md p-6 sm:p-8">
            <h2 className="text-2xl font-semibold text-white">{title}</h2>
            <p className="mt-1 text-sm text-zinc-400">{subtitle}</p>

            {(!email || !otp) && (
              <p className="mt-6 text-sm text-red-400">
                We could not detect your verified OTP. Please{' '}
                <Link to={`/forgot-password/${variant}`} className="text-white font-medium underline">
                  restart the reset process
                </Link>
                .
              </p>
            )}

            {email && otp && (
              <form onSubmit={handleSubmit} className="mt-6 space-y-4">
                <p className="text-xs text-zinc-400">New password must meet all of the following:</p>
                <ul className="space-y-1.5">
                  {PASSWORD_RULES.map(({ id, label, test }) => {
                    const pass = test(newPassword)
                    return (
                      <li key={id} className="flex items-center gap-2 text-xs">
                        {pass ? <FiCheck className="w-3.5 h-3.5 text-green-400 flex-shrink-0" /> : <FiX className="w-3.5 h-3.5 text-zinc-500 flex-shrink-0" />}
                        <span className={pass ? 'text-zinc-300' : 'text-zinc-500'}>{label}</span>
                      </li>
                    )
                  })}
                </ul>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-400">New Password</label>
                  <PasswordInput
                    className="mt-1 rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-sm text-white placeholder:text-zinc-500 focus:border-white focus:outline-none"
                    placeholder="Meet all requirements above"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    minLength={8}
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-400">Confirm Password</label>
                  <PasswordInput
                    className="mt-1 rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-sm text-white placeholder:text-zinc-500 focus:border-white focus:outline-none"
                    placeholder="Confirm new password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    minLength={8}
                    required
                  />
                </div>

                {error && <p className="text-sm text-red-400">{error}</p>}
                {status && <p className="text-sm text-emerald-400">{status}</p>}

                <button
                  type="submit"
                  className="w-full rounded-lg bg-white px-4 py-2 text-sm font-semibold text-black transition hover:bg-zinc-100 disabled:opacity-60"
                  disabled={!canSubmit}
                >
                  {loading ? 'Updating...' : 'Reset Password'}
                </button>
              </form>
            )}

            <p className="mt-4 text-sm text-zinc-400">
              Need to change something?{' '}
              <Link to={`/forgot-password/${variant}/verify?email=${encodeURIComponent(email || '')}`} className="text-white font-medium hover:underline">
                Back to OTP verification
              </Link>
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}

