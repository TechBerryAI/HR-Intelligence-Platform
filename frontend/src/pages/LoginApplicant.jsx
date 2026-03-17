import React, { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'
import PasswordInput from '../components/PasswordInput.jsx'

export default function LoginApplicant() {
	const navigate = useNavigate()
	const location = useLocation()
	const { loginApplicant } = useApp()
	const [applicantId, setApplicantId] = useState('')
	const [applicantPassword, setApplicantPassword] = useState('')
  const [error, setError] = useState('')

	const onApplicantSubmit = async (e) => {
		e.preventDefault()
		setError('')
		const res = await loginApplicant(applicantId, applicantPassword)
		if (res.ok) {
			const sp = new URLSearchParams(location.search)
			const redirectTo = sp.get('redirect') || '/jobs'
			const applyFor = sp.get('applyFor')
			// Force profile completion flow first
			const profileUrl = new URLSearchParams({ redirect: applyFor ? `${redirectTo}${redirectTo.includes('?') ? '&' : '?'}applyFor=${applyFor}` : redirectTo }).toString()
			navigate(`/profile/applicant?${profileUrl}`)
		} else {
			setError(res.message || 'Login failed')
		}
	}

	return (
		<section className="relative min-h-[calc(100vh-180px)] flex items-center justify-center px-4 py-10 overflow-hidden">
			<div className="pointer-events-none absolute inset-0">
				<div className="absolute -top-24 -left-24 h-72 w-72 rounded-full bg-white/10 blur-3xl" />
				<div className="absolute -bottom-24 -right-24 h-80 w-80 rounded-full bg-white/10 blur-3xl" />
				<div className="absolute inset-0 opacity-[0.07]" style={{backgroundImage:'radial-gradient(circle at 1px 1px, #fff 1px, transparent 0)', backgroundSize:'24px 24px'}} />
			</div>

			<div className="w-full max-w-xl relative">
				<div className="rounded-2xl bg-gradient-to-br from-zinc-900/90 via-zinc-900/70 to-zinc-900/50 p-[1px] shadow-2xl">
					<div className="rounded-2xl bg-zinc-950/70 backdrop-blur-md p-6 sm:p-8">
						<h2 className="text-2xl font-semibold text-white">Applicant Login</h2>
						<p className="mt-1 text-sm text-zinc-400">Sign in to apply and track applications</p>
						<form onSubmit={onApplicantSubmit} className="mt-6">
							{error && <div className="mb-3 text-sm text-red-400">{error}</div>}
							<label className="block text-sm font-medium text-zinc-300">Email or Username</label>
							<div className="mt-1 relative">
								<span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500">
									<svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 6h16v12H4V6z" stroke="currentColor" strokeWidth="1.5"/><path d="M4 7l8 6 8-6" stroke="currentColor" strokeWidth="1.5"/></svg>
								</span>
								<input
									type="text"
									className="w-full bg-transparent border-0 border-b border-zinc-700 pl-10 pr-3 py-2.5 text-gray-100 placeholder:text-zinc-500 focus:outline-none focus:ring-0 focus:border-white"
									placeholder="you@example.com"
									value={applicantId}
									onChange={(e) => setApplicantId(e.target.value)}
									required
								/>
							</div>
							<label className="block text-sm font-medium text-zinc-300 mt-4">Password</label>
							<div className="mt-1 relative">
								<span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500 z-10">
									<svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="5" y="11" width="14" height="9" rx="2" stroke="currentColor" strokeWidth="1.5"/><path d="M8 11V8a4 4 0 118 0v3" stroke="currentColor" strokeWidth="1.5"/></svg>
								</span>
								<PasswordInput
									className="bg-transparent border-0 border-b border-zinc-700 pl-10 py-2.5 text-gray-100 placeholder:text-zinc-500 focus:outline-none focus:ring-0 focus:border-white"
									placeholder="••••••••"
									value={applicantPassword}
									onChange={(e) => setApplicantPassword(e.target.value)}
									required
								/>
							</div>
							<button
								type="submit"
								className="mt-6 w-full rounded-lg bg-white text-black hover:bg-zinc-100 active:bg-zinc-200 font-medium py-2.5 transition-colors duration-200 shadow-sm hover:shadow"
							>
								Login
							</button>
							<div className="mt-3 flex items-center justify-between text-sm">
								<Link to="/forgot-password/applicant" className="text-zinc-400 hover:text-zinc-200 transition-colors">Forgot Password?</Link>
								<a href="/signup/applicant" className="text-white font-medium hover:underline">Don't have an account? Sign up</a>
							</div>
						</form>
					</div>
				</div>
			</div>
		</section>
	)
}


