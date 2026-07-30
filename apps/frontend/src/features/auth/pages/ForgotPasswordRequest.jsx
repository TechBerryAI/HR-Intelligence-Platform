import React, { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useApp } from '@/core/context/AppContext.jsx'

export default function ForgotPasswordRequest() {
  const { variant = 'applicant' } = useParams()
  const isAdmin = variant === 'admin'
  const { requestApplicantPasswordReset, requestHrPasswordReset } = useApp()
  const requestReset = isAdmin ? requestHrPasswordReset : requestApplicantPasswordReset

  const [email, setEmail] = useState('')
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (event) => {
    event.preventDefault()
    setStatus('')
    setError('')
    setLoading(true)
    const res = await requestReset(email.trim().toLowerCase())
    setLoading(false)
    if (res.ok) {
      setStatus('OTP sent to your email. Please proceed to verification.')
      navigate(`/forgot-password/${variant}/verify?email=${encodeURIComponent(email.trim().toLowerCase())}`)
    } else {
      setError(res.message || 'Failed to send OTP')
    }
  }

  const title = isAdmin ? 'Admin Password Reset' : 'Applicant Password Reset'
  const subtitle = isAdmin
    ? 'Enter the admin email to receive an OTP for reset.'
    : 'Enter your email to receive an OTP for reset.'
  const loginPath = isAdmin ? '/login/admin' : '/login'

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

            <form onSubmit={handleSubmit} className="mt-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-400">Email</label>
                <input
                  type="email"
                  className="mt-1 w-full rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-sm text-white placeholder:text-zinc-500 focus:border-white focus:outline-none"
                  placeholder={isAdmin ? 'hr@company.com' : 'you@example.com'}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>

              {error && <p className="text-sm text-red-400">{error}</p>}
              {status && <p className="text-sm text-emerald-400">{status}</p>}

              <button
                type="submit"
                className="w-full rounded-lg bg-white px-4 py-2 text-sm font-semibold text-black transition hover:bg-zinc-100 disabled:opacity-60"
                disabled={loading || !email}
              >
                {loading ? 'Sending OTP...' : 'Send OTP'}
              </button>
            </form>

            <p className="mt-4 text-sm text-zinc-400">
              Remembered your password?{' '}
              <Link to={loginPath} className="text-white font-medium hover:underline">
                Back to login
              </Link>
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}

