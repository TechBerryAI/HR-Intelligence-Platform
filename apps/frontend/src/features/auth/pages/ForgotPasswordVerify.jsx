import React, { useState } from 'react'
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useApp } from '@/core/context/AppContext.jsx'

export default function ForgotPasswordVerify() {
  const { variant } = useParams()
  const { verifyHrPasswordOtp } = useApp()
  const [searchParams] = useSearchParams()
  const email = (searchParams.get('email') || '').trim().toLowerCase()
  const [otp, setOtp] = useState('')
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
    if (!email) {
      setError('Missing email. Please restart the reset process.')
      return
    }
    setLoading(true)
    const res = await verifyHrPasswordOtp({ email, otp: otp.trim() })
    setLoading(false)
    if (res.ok) {
      setStatus('OTP verified. Redirecting to password reset...')
      navigate(
        `/forgot-password/admin/reset?email=${encodeURIComponent(email)}&otp=${encodeURIComponent(otp.trim())}`
      )
    } else {
      setError(res.message || 'OTP verification failed')
    }
  }

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
            <h2 className="text-2xl font-semibold text-white">Verify Admin OTP</h2>
            <p className="mt-1 text-sm text-zinc-400">Enter the OTP sent to your admin email.</p>

            {!email && (
              <p className="mt-6 text-sm text-red-400">
                We could not detect your email. Please{' '}
                <Link to="/forgot-password/admin" className="text-white font-medium underline">
                  restart the reset process
                </Link>
                .
              </p>
            )}

            {email && (
              <form onSubmit={handleSubmit} className="mt-6 space-y-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-400">Email</label>
                  <input
                    type="email"
                    value={email}
                    disabled
                    className="mt-1 w-full rounded-lg border border-zinc-800 bg-zinc-900/40 px-3 py-2 text-sm text-zinc-400"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-400">OTP</label>
                  <input
                    type="text"
                    className="mt-1 w-full rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-sm text-white placeholder:text-zinc-500 focus:border-white focus:outline-none"
                    placeholder="Enter 6-digit OTP"
                    value={otp}
                    onChange={(e) => setOtp(e.target.value)}
                    required
                  />
                </div>

                {error && <p className="text-sm text-red-400">{error}</p>}
                {status && <p className="text-sm text-emerald-400">{status}</p>}

                <button
                  type="submit"
                  className="w-full rounded-lg bg-white px-4 py-2 text-sm font-semibold text-black transition hover:bg-zinc-100 disabled:opacity-60"
                  disabled={loading || !otp}
                >
                  {loading ? 'Verifying...' : 'Verify OTP'}
                </button>
              </form>
            )}

            <p className="mt-4 text-sm text-zinc-400">
              Go back to{' '}
              <Link to="/forgot-password/admin" className="text-white font-medium hover:underline">
                request OTP
              </Link>{' '}
              or{' '}
              <Link to="/login/admin" className="text-white font-medium hover:underline">
                back to login
              </Link>
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}
