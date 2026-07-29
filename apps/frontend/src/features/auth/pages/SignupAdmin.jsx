import React, { useState } from 'react'
import PasswordInput from '@/shared/components/PasswordInput.jsx'
import { useApp } from '@/core/context/AppContext.jsx'
import { useNavigate, Link } from 'react-router-dom'
import AuthPageLayout from '@/layouts/AuthPageLayout.jsx'

export default function SignupAdmin() {
    const { signupHR, verifyHROTP, resendHROTP } = useApp()
    const navigate = useNavigate()
    const [fullName, setFullName] = useState('')
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [company, setCompany] = useState('')
    const [otp, setOtp] = useState('')
    const [step, setStep] = useState(1) // 1 = signup form, 2 = OTP verification
    const [created, setCreated] = useState(false)
    const [error, setError] = useState('')
    const [submitting, setSubmitting] = useState(false)
    const [resending, setResending] = useState(false)

    const onSubmit = async (e) => {
        e.preventDefault()
        setError('')
        setSubmitting(true)
        const res = await signupHR({ fullName, email, password, company })
        if (res.ok) {
            setStep(2) // Move to OTP verification step
        } else {
            setError(res.message || 'Registration failed')
        }
        setSubmitting(false)
    }

    const onVerifyOTP = async (e) => {
        e.preventDefault()
        setError('')
        setSubmitting(true)
        const res = await verifyHROTP({ email, otp })
        if (res.ok) {
            setCreated(true)
            // Redirect to dashboard after successful verification (user is already logged in)
            setTimeout(() => {
                navigate('/dashboard')
            }, 2000)
        } else {
            setError(res.message || 'OTP verification failed')
        }
        setSubmitting(false)
    }

    return (
        <AuthPageLayout
            title={step === 1 ? 'Create HR account' : 'Verify your email'}
            subtitle={step === 1 ? 'Manage job postings and candidates.' : `We sent a code to ${email}. Enter it below.`}
        >
            <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 shadow-premium p-6 sm:p-8">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
                    {step === 1 ? 'Sign Up as Admin' : 'Verify Your Email'}
                </h2>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                    {step === 1 ? 'Create an HR/Admin account to manage jobs' : `We sent a verification code to ${email}. Please enter it below.`}
                </p>
                {step === 1 ? (
                    <form onSubmit={onSubmit} className="mt-6 space-y-4">
                        {error && <div className="rounded-xl bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 px-4 py-3 text-sm text-red-700 dark:text-red-300">{error}</div>}
                        <div>
                            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">Full Name (Admin)</label>
                            <input className="input-premium" placeholder="Your name" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">Company</label>
                            <input className="input-premium" placeholder="Company name" value={company} onChange={(e) => setCompany(e.target.value)} required />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">Work Email</label>
                            <input type="email" className="input-premium" placeholder="hr@company.com" value={email} onChange={(e) => setEmail(e.target.value)} required />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">Password</label>
                            <PasswordInput className="input-premium" placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} />
                        </div>
                        <button type="submit" disabled={submitting} className="w-full rounded-xl bg-emerald-600 text-white font-semibold py-3 shadow-md hover:bg-emerald-500 transition-colors disabled:opacity-70">
                            {submitting ? 'Sending OTP...' : 'Send Verification Code'}
                        </button>
                        <p className="text-center text-sm text-slate-500 dark:text-slate-400">
                            <Link to="/login" className="text-primary dark:text-accent-blue hover:underline">← Back to login</Link>
                        </p>
                    </form>
                ) : (
                    <form onSubmit={onVerifyOTP} className="mt-6 space-y-4">
                        {error && <div className="rounded-xl bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 px-4 py-3 text-sm text-red-700 dark:text-red-300">{error}</div>}
                        <div>
                            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">Enter OTP</label>
                            <input type="text" inputMode="numeric" pattern="[0-9]*" maxLength={6} className="input-premium text-center text-2xl tracking-widest font-mono" placeholder="000000" value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))} required autoFocus />
                        </div>
                        <p className="text-xs text-slate-500 dark:text-slate-400">Check your email for the 6-digit code</p>
                        <button type="submit" disabled={submitting || otp.length !== 6} className="w-full rounded-xl bg-emerald-600 text-white font-semibold py-3 shadow-md hover:bg-emerald-500 transition-colors disabled:opacity-70">
                            {submitting ? 'Verifying...' : 'Verify & Create Account'}
                        </button>
                        <div className="flex gap-2">
                            <button type="button" onClick={async () => { setError(''); setResending(true); try { const res = await resendHROTP({ email }); if (res.ok) { setError(''); alert('OTP resent successfully! Please check your email.'); } else { setError(res.message || 'Failed to resend OTP'); } } catch (err) { setError(err?.message || 'Failed to resend OTP'); } finally { setResending(false); } }} disabled={resending} className="flex-1 text-sm text-accent-blue hover:underline disabled:opacity-50">
                                {resending ? 'Resending...' : 'Resend OTP'}
                            </button>
                            <button type="button" onClick={() => setStep(1)} className="flex-1 text-sm text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300">
                                ← Back to signup
                            </button>
                        </div>
                        {created && <div className="mt-3 text-sm text-emerald-600 dark:text-emerald-400">Account created successfully! Redirecting to dashboard...</div>}
                    </form>
                )}
            </div>
        </AuthPageLayout>
    )
}


