import React from 'react'
import { Link } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'

export default function Login() {
	useApp() // keep provider in scope (not used directly here)

	const onAdminSubmit = (e) => {
		e.preventDefault()
		const res = loginHR(adminEmail, adminPassword)
		if (res.ok) {
			navigate('/dashboard')
		} else {
			setAdminError(res.message || 'Login failed')
		}
	}

	const onApplicantSubmit = (e) => {
		e.preventDefault()
		// Demo flow: send applicants to jobs page
		navigate('/jobs')
	}

	return (
		<section className="relative min-h-[calc(100vh-180px)] flex items-center justify-center px-4 py-10 overflow-hidden">
			{/* Decorative background graphics */}
				<div className="pointer-events-none absolute inset-0">
					<div className="absolute -top-24 -left-24 h-72 w-72 rounded-full bg-white/10 blur-3xl" />
					<div className="absolute -bottom-24 -right-24 h-80 w-80 rounded-full bg-white/10 blur-3xl" />
				<div className="absolute inset-0 opacity-[0.07]" style={{backgroundImage:'radial-gradient(circle at 1px 1px, #fff 1px, transparent 0)', backgroundSize:'24px 24px'}} />
			</div>

			<div className="w-full max-w-5xl relative">
				<div className="relative rounded-2xl bg-gradient-to-br from-zinc-900/90 via-zinc-900/70 to-zinc-900/50 p-[1px] shadow-2xl">
					<div className="rounded-2xl bg-zinc-950/70 backdrop-blur-md">
						<div className="flex flex-col md:flex-row">
						{/* Applicant Section */}
						<div className="flex-1 p-6 sm:p-8">
							<h2 className="text-xl sm:text-2xl font-semibold text-white">For Applicants?</h2>
							<p className="mt-1 text-sm text-zinc-400">Access applications, saved jobs, and alerts.</p>
							<Link to="/login/applicant" className="mt-5 inline-block w-full rounded-lg bg-white text-black hover:bg-zinc-100 active:bg-zinc-200 font-medium py-2.5 text-center transition-colors duration-200 shadow-sm hover:shadow">Continue to Applicant Login</Link>
						</div>

							{/* Divider */}
							<div className="hidden md:block w-px bg-zinc-800/70 my-8" />

							{/* Admin Section */}
						<div className="flex-1 p-6 sm:p-8">
							<h2 className="text-xl sm:text-2xl font-semibold text-white">For Admin?</h2>
							<p className="mt-1 text-sm text-zinc-400">Manage postings, applicants, and insights.</p>
							<Link to="/login/admin" className="mt-5 inline-block w-full rounded-lg bg-white text-black hover:bg-zinc-100 active:bg-zinc-200 font-medium py-2.5 text-center transition-colors duration-200 shadow-sm hover:shadow">Continue to Admin Login</Link>
						</div>
						</div>
					</div>
				</div>
			</div>
		</section>
	)
}


