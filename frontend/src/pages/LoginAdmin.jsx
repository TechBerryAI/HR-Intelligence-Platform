import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'

export default function LoginAdmin() {
	const { loginHR, loginSuperAdmin, auth, superAdminAuth } = useApp()
	const navigate = useNavigate()
	const [adminEmail, setAdminEmail] = useState('')
	const [adminPassword, setAdminPassword] = useState('')
	const [adminError, setAdminError] = useState('')

	// Redirect to dashboard if already logged in as HR; to super-admin if Head of HR
	useEffect(() => {
		if (auth.isLoggedIn && auth.role === 'HR') {
			navigate('/dashboard', { replace: true })
		}
		if (auth.isLoggedIn && auth.role === 'head_hr') {
			navigate('/super-admin', { replace: true })
		}
	}, [auth.isLoggedIn, auth.role, navigate])

	// Redirect to Super Admin if already logged in as Super Admin
	useEffect(() => {
		if (superAdminAuth?.isLoggedIn) {
			navigate('/super-admin', { replace: true })
		}
	}, [superAdminAuth?.isLoggedIn, navigate])

	const onAdminSubmit = async (e) => {
		e.preventDefault()
		setAdminError('')
		// If credentials are Super Admin, log in as Super Admin and open Super Admin page
		const superRes = await loginSuperAdmin(adminEmail.trim(), adminPassword)
		if (superRes?.ok) {
			navigate('/super-admin')
			return
		}
		const res = await loginHR(adminEmail, adminPassword)
		if (res.ok) {
			const role = res.user?.role || auth.role
			navigate(role === 'head_hr' ? '/super-admin' : '/dashboard')
		} else setAdminError(res.message || 'Login failed')
	}

	// Don't render login form if already logged in (redirect will happen)
	if (auth.isLoggedIn && (auth.role === 'HR' || auth.role === 'head_hr')) return null
	if (superAdminAuth?.isLoggedIn) return null

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
						<h2 className="text-2xl font-semibold text-white">Admin Login</h2>
						<p className="mt-1 text-sm text-zinc-400">HR/Admin access only</p>
						<form onSubmit={onAdminSubmit} className="mt-6">
							{adminError && <div className="mb-3 text-sm text-red-400">{adminError}</div>}
							<label className="block text-sm font-medium text-zinc-300">Email</label>
							<div className="mt-1 relative">
								<span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500">
									<svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 6h16v12H4V6z" stroke="currentColor" strokeWidth="1.5"/><path d="M4 7l8 6 8-6" stroke="currentColor" strokeWidth="1.5"/></svg>
								</span>
								<input
									type="email"
									className="w-full bg-transparent border-0 border-b border-zinc-700 pl-10 pr-3 py-2.5 text-gray-100 placeholder:text-zinc-500 focus:outline-none focus:ring-0 focus:border-white"
									placeholder="hr@company.com"
									value={adminEmail}
									onChange={(e) => setAdminEmail(e.target.value)}
									required
								/>
							</div>
							<label className="block text-sm font-medium text-zinc-300 mt-4">Password</label>
							<div className="mt-1 relative">
								<span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500">
									<svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="5" y="11" width="14" height="9" rx="2" stroke="currentColor" strokeWidth="1.5"/><path d="M8 11V8a4 4 0 118 0v3" stroke="currentColor" strokeWidth="1.5"/></svg>
								</span>
								<input
									type="password"
									className="w-full bg-transparent border-0 border-b border-zinc-700 pl-10 pr-3 py-2.5 text-gray-100 placeholder:text-zinc-500 focus:outline-none focus:ring-0 focus:border-white"
									placeholder="••••••••"
									value={adminPassword}
									onChange={(e) => setAdminPassword(e.target.value)}
									required
								/>
							</div>
							<button
								type="submit"
								className="mt-6 w-full rounded-lg bg-white text-black hover:bg-zinc-100 active:bg-zinc-200 font-medium py-2.5 transition-colors duration-200 shadow-sm hover:shadow"
							>
								Login
							</button>
							<div className="mt-3 text-sm">
								<Link to="/forgot-password/admin" className="text-zinc-400 hover:text-zinc-200 transition-colors">Forgot Password?</Link>
							</div>
							{/* Admin login should be backed by backend; demo credentials removed. */}
						</form>
					</div>
				</div>
			</div>
		</section>
	)
}


