import React, { useState } from 'react'
import { useApp } from '../context/AppContext.jsx'

export default function SignupApplicant() {
    const { signupApplicant, verifyApplicantOTP, resendApplicantOTP } = useApp()
    const [name, setName] = useState('')
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [otp, setOtp] = useState('')
    const [step, setStep] = useState(1) // 1 = signup form, 2 = OTP verification
    const [created, setCreated] = useState(false)
    const [error, setError] = useState('')
    const [submitting, setSubmitting] = useState(false)
    const [resending, setResending] = useState(false)
    const [phone, setPhone] = useState('')

    const onSubmit = async (e) => {
        e.preventDefault()
        setError('')
        setSubmitting(true)
        const res = await signupApplicant({ name, email, password, phone })
        if (res.ok) {
            setStep(2) // Move to OTP verification step
        } else {
            setError(res.message || 'Signup failed')
        }
        setSubmitting(false)
    }

    const onVerifyOTP = async (e) => {
        e.preventDefault()
        setError('')
        setSubmitting(true)
        try {
            const res = await verifyApplicantOTP({ email, otp })
            if (res.ok) {
                setCreated(true)
            } else {
                setError(res.message || 'OTP verification failed. Please try again.')
            }
        } catch (err) {
            console.error('OTP verification error:', err)
            setError(err?.message || 'Network error. Please check your connection and try again.')
        } finally {
            setSubmitting(false)
        }
    }

    return (
        <section className="relative min-h-[calc(100vh-180px)] flex items-center justify-center px-4 py-10 overflow-hidden">
            {/* Decorative background graphics */}
            <div className="pointer-events-none absolute inset-0">
                <div className="absolute -top-24 -left-24 h-72 w-72 rounded-full bg-white/10 blur-3xl" />
                <div className="absolute -bottom-24 -right-24 h-80 w-80 rounded-full bg-white/10 blur-3xl" />
                <div className="absolute inset-0 opacity-[0.07]" style={{ backgroundImage: 'radial-gradient(circle at 1px 1px, #fff 1px, transparent 0)', backgroundSize: '24px 24px' }} />
            </div>

            <div className="w-full max-w-xl relative">
                <div className="rounded-2xl bg-gradient-to-br from-zinc-900/90 via-zinc-900/70 to-zinc-900/50 p-[1px] shadow-2xl">
                    <div className="rounded-2xl bg-zinc-950/70 backdrop-blur-md p-6 sm:p-8">
                        <h2 className="text-2xl font-semibold text-white">
                            {step === 1 ? 'Sign Up as Applicant' : 'Verify Your Email'}
                        </h2>
                        <p className="mt-1 text-sm text-zinc-400">
                            {step === 1 
                                ? 'Create your applicant account to apply for jobs'
                                : `We sent a verification code to ${email}. Please enter it below.`}
                        </p>
                        {step === 1 ? (
                            <form onSubmit={onSubmit} className="mt-6">
                                {error && <div className="mb-3 text-sm text-red-400">{error}</div>}
                                <label className="block text-sm font-medium text-zinc-300">Full Name</label>
                                <input
                                    className="mt-1 w-full rounded-lg border border-zinc-800 bg-zinc-900 text-gray-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-600/70 focus:border-blue-600/70"
                                    placeholder="Your name"
                                    value={name}
                                    onChange={(e) => setName(e.target.value)}
                                    required
                                />
                                <label className="block text-sm font-medium text-zinc-300 mt-4">Email</label>
                                <div className="mt-1 relative">
                                    <span className="pointer-events-none absolute left-0 top-1/2 -translate-y-1/2 text-zinc-500">
                                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 6h16v12H4V6z" stroke="currentColor" strokeWidth="1.5" /><path d="M4 7l8 6 8-6" stroke="currentColor" strokeWidth="1.5" /></svg>
                                    </span>
                                    <input
                                        type="email"
                                        className="w-full bg-transparent border-0 border-b border-zinc-700 pl-7 pr-3 py-2.5 text-gray-100 placeholder:text-zinc-500 focus:outline-none focus:ring-0 focus:border-white"
                                        placeholder="you@example.com"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        required
                                    />
                                </div>
                                <label className="block text-sm font-medium text-zinc-300 mt-4">Password</label>
                                <div className="mt-1 relative">
                                    <span className="pointer-events-none absolute left-0 top-1/2 -translate-y-1/2 text-zinc-500">
                                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="5" y="11" width="14" height="9" rx="2" stroke="currentColor" strokeWidth="1.5" /><path d="M8 11V8a4 4 0 118 0v3" stroke="currentColor" strokeWidth="1.5" /></svg>
                                    </span>
                                    <input
                                        type="password"
                                        className="w-full bg-transparent border-0 border-b border-zinc-700 pl-7 pr-3 py-2.5 text-gray-100 placeholder:text-zinc-500 focus:outline-none focus:ring-0 focus:border-white"
                                        placeholder="••••••••"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        required
                                        minLength={6}
                                    />
                                </div>
                                <button
                                    type="submit"
                                    disabled={submitting}
                                    className={`mt-6 w-full ${submitting ? 'bg-zinc-300' : 'bg-white hover:bg-zinc-100'} text-black font-medium py-2.5 rounded-lg transition-colors shadow-sm hover:shadow`}
                                >
                                    {submitting ? 'Sending OTP...' : 'Send Verification Code'}
                                </button>
                            </form>
                        ) : (
                            <form onSubmit={onVerifyOTP} className="mt-6">
                                {error && (
                                    <div className="mb-4 p-3 rounded-lg bg-red-950/50 border border-red-600/40 text-red-200 text-sm">
                                        {error}
                                    </div>
                                )}
                                <label className="block text-sm font-medium text-zinc-300">Enter OTP</label>
                                <div className="mt-1 relative">
                                    <span className="pointer-events-none absolute left-0 top-1/2 -translate-y-1/2 text-zinc-500">
                                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                            <path d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" stroke="currentColor" strokeWidth="1.5"/>
                                        </svg>
                                    </span>
                                    <input
                                        type="text"
                                        inputMode="numeric"
                                        pattern="[0-9]*"
                                        maxLength={6}
                                        className="w-full bg-transparent border-0 border-b border-zinc-700 pl-7 pr-3 py-2.5 text-gray-100 placeholder:text-zinc-500 focus:outline-none focus:ring-0 focus:border-white text-center text-2xl tracking-widest font-mono"
                                        placeholder="000000"
                                        value={otp}
                                        onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                                        required
                                        autoFocus
                                    />
                                </div>
                                <p className="mt-2 text-xs text-zinc-500">Check your email for the 6-digit code</p>
                                <button
                                    type="submit"
                                    disabled={submitting || otp.length !== 6}
                                    className={`mt-6 w-full ${(submitting || otp.length !== 6) ? 'bg-zinc-300' : 'bg-white hover:bg-zinc-100'} text-black font-medium py-2.5 rounded-lg transition-colors shadow-sm hover:shadow`}
                                >
                                    {submitting ? 'Verifying...' : 'Verify & Create Account'}
                                </button>
                                <div className="mt-3 flex gap-2">
                                    <button
                                        type="button"
                                        onClick={async () => {
                                            setError('')
                                            setResending(true)
                                            try {
                                                const res = await resendApplicantOTP({ email, phone })
                                                if (res.ok) {
                                                    setError('')
                                                    alert('OTP resent successfully! Please check your email.')
                                                } else {
                                                    setError(res.message || 'Failed to resend OTP')
                                                }
                                            } catch (err) {
                                                setError(err?.message || 'Failed to resend OTP')
                                            } finally {
                                                setResending(false)
                                            }
                                        }}
                                        disabled={resending}
                                        className={`flex-1 text-sm ${resending ? 'text-zinc-500' : 'text-blue-400 hover:text-blue-300'} transition-colors underline`}
                                    >
                                        {resending ? 'Resending...' : 'Resend OTP'}
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => setStep(1)}
                                        className="flex-1 text-sm text-zinc-400 hover:text-white transition-colors"
                                    >
                                        ← Back to signup
                                    </button>
                                </div>
                                {created && (
                                    <div className="mt-3 text-sm text-green-400">Account created successfully! You can now log in.</div>
                                )}
                            </form>
                        )}
                    </div>
                </div>
            </div>
        </section>
    )
}


