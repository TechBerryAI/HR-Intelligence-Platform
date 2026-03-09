import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'

export default function LoginSuperAdmin() {
  const { loginSuperAdmin, superAdminAuth } = useApp()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (superAdminAuth?.isLoggedIn) {
      navigate('/super-admin', { replace: true })
    }
  }, [superAdminAuth?.isLoggedIn, navigate])

  if (superAdminAuth?.isLoggedIn) return null

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    const res = await loginSuperAdmin(email, password)
    setLoading(false)
    if (res.ok) {
      navigate('/super-admin')
    } else {
      setError(res.message || 'Invalid credentials')
    }
  }

  return (
    <section className="relative min-h-[calc(100vh-180px)] flex items-center justify-center px-4 py-10 overflow-hidden">
      {/* Background accents */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-24 -left-24 h-72 w-72 rounded-full bg-white/10 blur-3xl" />
        <div className="absolute -bottom-24 -right-24 h-80 w-80 rounded-full bg-white/10 blur-3xl" />
        <div
          className="absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage: 'radial-gradient(circle at 1px 1px, #fff 1px, transparent 0)',
            backgroundSize: '24px 24px',
          }}
        />
      </div>

      <div className="w-full max-w-xl relative">
        {/* Badge */}
        <div className="flex justify-center mb-6">
          <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/10 border border-white/20 text-zinc-300 text-xs font-semibold tracking-widest uppercase">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            System Control
          </span>
        </div>

        <div className="rounded-2xl bg-gradient-to-br from-zinc-900/90 via-zinc-900/70 to-zinc-900/50 p-[1px] shadow-2xl">
          <div className="rounded-2xl bg-zinc-950/70 backdrop-blur-md p-6 sm:p-8">
            {/* Header */}
            <div className="flex items-center gap-3 mb-1">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 text-white grid place-items-center shadow-lg">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                </svg>
              </div>
              <div>
                <h2 className="text-2xl font-semibold text-white">Super Admin</h2>
                <p className="text-xs text-zinc-400 font-medium tracking-wide">RESTRICTED ACCESS</p>
              </div>
            </div>
            <p className="mt-1 mb-6 text-sm text-zinc-400">
              Full system privileges. This portal is not for HR or applicants.
            </p>

            <form onSubmit={onSubmit}>
              {error && (
                <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-500/10 border border-red-500/20 px-3 py-2.5 text-sm text-red-400">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  {error}
                </div>
              )}

              <label className="block text-sm font-medium text-zinc-300">Email</label>
              <div className="mt-1 relative">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M4 6h16v12H4V6z" /><path d="M4 7l8 6 8-6" />
                  </svg>
                </span>
                <input
                  type="email"
                  className="w-full bg-transparent border-0 border-b border-zinc-700 focus:border-white pl-10 pr-3 py-2.5 text-gray-100 placeholder:text-zinc-500 focus:outline-none focus:ring-0 transition-colors"
                  placeholder="superadmin@portal.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="username"
                />
              </div>

              <label className="block text-sm font-medium text-zinc-300 mt-4">Password</label>
              <div className="mt-1 relative">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 118 0v3" />
                  </svg>
                </span>
                <input
                  type={showPassword ? 'text' : 'password'}
                  className="w-full bg-transparent border-0 border-b border-zinc-700 focus:border-white pl-10 pr-10 py-2.5 text-gray-100 placeholder:text-zinc-500 focus:outline-none focus:ring-0 transition-colors"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 transition-colors"
                  tabIndex={-1}
                >
                  {showPassword ? (
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24" />
                      <line x1="1" y1="1" x2="23" y2="23" />
                    </svg>
                  ) : (
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="mt-6 w-full rounded-lg bg-white text-black hover:bg-zinc-100 active:bg-zinc-200 font-medium py-2.5 transition-colors duration-200 shadow-sm hover:shadow disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
                    </svg>
                    Verifying…
                  </>
                ) : (
                  'Access System'
                )}
              </button>
            </form>

            <p className="mt-5 text-center text-xs text-zinc-600">
              Looking for{' '}
              <a href="/login/admin" className="text-zinc-400 hover:text-zinc-200 underline underline-offset-2">
                Admin login
              </a>{' '}
              or{' '}
              <a href="/login/applicant" className="text-zinc-400 hover:text-zinc-200 underline underline-offset-2">
                Applicant login
              </a>
              ?
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}
