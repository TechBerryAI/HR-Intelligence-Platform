import React from 'react'
import { Link } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'
import { motion } from 'framer-motion'
import { FiUser, FiShield, FiArrowRight, FiCheck, FiZap, FiTrendingUp, FiBarChart } from 'react-icons/fi'

export default function Login() {
	useApp() // keep provider in scope

	return (
		<section className="relative min-h-[calc(100vh-180px)] flex items-center justify-center px-4 py-10 overflow-hidden">
			{/* Enhanced Animated background */}
			<div className="pointer-events-none absolute inset-0">
				<motion.div
					animate={{
						scale: [1, 1.3, 1],
						opacity: [0.2, 0.4, 0.2],
						x: [0, 50, 0],
						y: [0, 30, 0],
					}}
					transition={{ duration: 15, repeat: Infinity, ease: "easeInOut" }}
					className="absolute top-20 left-20 h-96 w-96 rounded-full bg-purple-500/30 blur-3xl"
				/>
				<motion.div
					animate={{
						scale: [1.3, 1, 1.3],
						opacity: [0.2, 0.4, 0.2],
						x: [0, -50, 0],
						y: [0, -30, 0],
					}}
					transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
					className="absolute bottom-20 right-20 h-96 w-96 rounded-full bg-blue-500/30 blur-3xl"
				/>
				<motion.div
					animate={{
						scale: [1, 1.2, 1],
						opacity: [0.15, 0.3, 0.15],
					}}
					transition={{ duration: 12, repeat: Infinity }}
					className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-[500px] w-[500px] rounded-full bg-pink-500/20 blur-3xl"
				/>
				<div className="absolute inset-0 opacity-[0.07]" style={{backgroundImage:'radial-gradient(circle at 1px 1px, #fff 1px, transparent 0)', backgroundSize:'24px 24px'}} />
			</div>

			{/* Floating decorative elements */}
			<motion.div
				animate={{
					y: [0, -20, 0],
					rotate: [0, 10, 0],
				}}
				transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
				className="absolute top-32 left-10 w-20 h-20 bg-gradient-to-r from-purple-500/10 to-pink-500/10 rounded-2xl backdrop-blur-sm border border-white/5 hidden lg:block"
			/>
			<motion.div
				animate={{
					y: [0, 20, 0],
					rotate: [0, -10, 0],
				}}
				transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
				className="absolute bottom-32 right-10 w-16 h-16 bg-gradient-to-r from-blue-500/10 to-cyan-500/10 rounded-full backdrop-blur-sm border border-white/5 hidden lg:block"
			/>

			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.6 }}
				className="w-full max-w-4xl mx-auto relative"
			>
				{/* Header */}
				<motion.div
					initial={{ opacity: 0, scale: 0.95 }}
					animate={{ opacity: 1, scale: 1 }}
					transition={{ duration: 0.5, delay: 0.2 }}
					className="text-center mb-10"
				>
					<motion.h1
						className="text-5xl sm:text-6xl font-bold mb-3"
						animate={{
							backgroundPosition: ['0% 50%', '100% 50%', '0% 50%'],
						}}
						transition={{ duration: 5, repeat: Infinity, ease: "linear" }}
						style={{
							backgroundImage: 'linear-gradient(90deg, #fff, #a855f7, #3b82f6, #fff)',
							backgroundSize: '200% auto',
							WebkitBackgroundClip: 'text',
							WebkitTextFillColor: 'transparent',
							backgroundClip: 'text',
						}}
					>
						Welcome Back
					</motion.h1>
					<motion.p
						initial={{ opacity: 0 }}
						animate={{ opacity: 1 }}
						transition={{ delay: 0.4 }}
						className="text-lg text-zinc-400"
					>
						Choose your account type to continue
					</motion.p>
				</motion.div>

				{/* Main Card - Always Side by Side */}
				<motion.div
					initial={{ opacity: 0, y: 30 }}
					animate={{ opacity: 1, y: 0 }}
					transition={{ duration: 0.7, delay: 0.3 }}
					className="glass-card rounded-3xl p-[2px] shadow-premium border border-white/10 hover:border-white/20 transition-all duration-500"
				>
					<div className="rounded-3xl bg-gradient-to-br from-zinc-900/95 via-zinc-900/90 to-zinc-900/85 backdrop-blur-xl overflow-hidden">
						{/* FORCE side by side layout - NO responsive breakpoints */}
						<div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 0 }}>
							{/* Applicant Section */}
							<motion.div
								initial={{ opacity: 0, x: -30 }}
								animate={{ opacity: 1, x: 0 }}
								transition={{ duration: 0.6, delay: 0.4 }}
								whileHover={{ scale: 1.01 }}
								className="p-8 relative group overflow-hidden"
							>
								{/* Animated background overlay */}
								<motion.div
									className="absolute inset-0 bg-gradient-to-br from-purple-600/10 via-purple-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500"
									animate={{
										backgroundPosition: ['0% 0%', '100% 100%'],
									}}
									transition={{ duration: 3, repeat: Infinity, repeatType: "reverse" }}
								/>
								
								{/* Floating particles effect */}
								<motion.div
									animate={{
										y: [0, -10, 0],
										opacity: [0.3, 0.6, 0.3],
									}}
									transition={{ duration: 4, repeat: Infinity }}
									className="absolute top-10 right-10 w-2 h-2 bg-purple-400 rounded-full blur-sm"
								/>
								<motion.div
									animate={{
										y: [0, -15, 0],
										opacity: [0.2, 0.5, 0.2],
									}}
									transition={{ duration: 5, repeat: Infinity, delay: 1 }}
									className="absolute bottom-20 left-10 w-1.5 h-1.5 bg-purple-300 rounded-full blur-sm"
								/>
								
								<div className="relative flex flex-col items-center text-center">
									{/* Icon with enhanced animation - Compact */}
									<motion.div
										whileHover={{ 
											scale: 1.15, 
											rotate: [0, -5, 5, -5, 0],
										}}
										whileTap={{ scale: 0.95 }}
										transition={{ 
											rotate: { duration: 0.5 },
											scale: { duration: 0.2 }
										}}
										className="w-20 h-20 bg-gradient-to-br from-purple-600 to-purple-500 rounded-3xl flex items-center justify-center mb-5 shadow-glow relative group/icon cursor-pointer"
									>
										<motion.div
											className="absolute inset-0 rounded-3xl bg-gradient-to-br from-purple-400 to-purple-600 opacity-0 group-hover/icon:opacity-100 blur-xl transition-opacity"
											animate={{ scale: [1, 1.2, 1] }}
											transition={{ duration: 2, repeat: Infinity }}
										/>
										<FiUser className="w-9 h-9 text-white relative z-10" />
									</motion.div>

									<motion.h2
										initial={{ opacity: 0, y: 10 }}
										animate={{ opacity: 1, y: 0 }}
										transition={{ delay: 0.5 }}
										className="text-2xl font-bold text-white mb-3"
									>
										For Applicants
									</motion.h2>
									<motion.p
										initial={{ opacity: 0 }}
										animate={{ opacity: 1 }}
										transition={{ delay: 0.6 }}
										className="text-zinc-400 mb-6 text-sm leading-relaxed max-w-xs"
									>
										Access applications, saved jobs, and alerts.
									</motion.p>

									<ul className="space-y-3 mb-8 w-full max-w-xs">
										{[
											{ icon: FiZap, text: 'Apply instantly', color: 'purple' },
											{ icon: FiCheck, text: 'AI resume parsing', color: 'purple' },
											{ icon: FiTrendingUp, text: 'Track status', color: 'purple' },
											{ icon: FiCheck, text: 'Save jobs', color: 'purple' }
										].map((feature, index) => (
											<motion.li
												key={index}
												initial={{ opacity: 0, y: 10 }}
												animate={{ opacity: 1, y: 0 }}
												transition={{ delay: 0.7 + index * 0.1 }}
												whileHover={{ scale: 1.05 }}
												className="flex items-center justify-center gap-2 text-sm text-zinc-300 group/item cursor-default"
											>
												<motion.div
													whileHover={{ rotate: 360, scale: 1.2 }}
													transition={{ duration: 0.5 }}
													className="flex-shrink-0 w-5 h-5 bg-purple-500/20 rounded-lg flex items-center justify-center group-hover/item:bg-purple-500/30 transition-colors"
												>
													<feature.icon className="w-3 h-3 text-purple-400" />
												</motion.div>
												<span className="group-hover/item:text-white transition-colors">{feature.text}</span>
											</motion.li>
										))}
									</ul>

									<Link to="/login/applicant" className="w-full max-w-xs">
										<motion.button
											whileHover={{ scale: 1.03, y: -2 }}
											whileTap={{ scale: 0.97 }}
											className="w-full bg-gradient-to-r from-purple-600 via-purple-500 to-purple-600 hover:from-purple-500 hover:via-purple-400 hover:to-purple-500 text-white font-semibold py-3.5 text-sm rounded-xl transition-all shadow-glow flex items-center justify-center gap-2 group/btn relative overflow-hidden"
										>
											<motion.div
												className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent"
												animate={{ x: ['-100%', '200%'] }}
												transition={{ duration: 2, repeat: Infinity, repeatDelay: 1 }}
											/>
											<span className="relative z-10">Applicant Login</span>
											<FiArrowRight className="w-4 h-4 relative z-10 group-hover/btn:translate-x-1 transition-transform" />
										</motion.button>
									</Link>

									<motion.p
										initial={{ opacity: 0 }}
										animate={{ opacity: 1 }}
										transition={{ delay: 0.9 }}
										className="mt-4 text-center text-xs text-zinc-500"
									>
										Don't have an account?{' '}
										<Link to="/signup/applicant" className="text-purple-400 hover:text-purple-300 font-medium transition-colors">
											Sign up
										</Link>
									</motion.p>
								</div>
							</motion.div>

							{/* Animated Divider */}
							<div className="relative" style={{ width: '1px', height: 'auto' }}>
								<motion.div
									className="absolute inset-0 bg-gradient-to-b from-transparent via-white/20 to-transparent"
									animate={{
										opacity: [0.3, 0.6, 0.3],
										scaleY: [0.8, 1, 0.8],
									}}
									transition={{ duration: 3, repeat: Infinity }}
								/>
							</div>

							{/* Admin Section */}
							<motion.div
								initial={{ opacity: 0, x: 30 }}
								animate={{ opacity: 1, x: 0 }}
								transition={{ duration: 0.6, delay: 0.5 }}
								whileHover={{ scale: 1.01 }}
								className="p-8 relative group overflow-hidden"
							>
								{/* Animated background overlay */}
								<motion.div
									className="absolute inset-0 bg-gradient-to-br from-blue-600/10 via-blue-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500"
									animate={{
										backgroundPosition: ['0% 0%', '100% 100%'],
									}}
									transition={{ duration: 3, repeat: Infinity, repeatType: "reverse" }}
								/>
								
								{/* Floating particles effect */}
								<motion.div
									animate={{
										y: [0, -10, 0],
										opacity: [0.3, 0.6, 0.3],
									}}
									transition={{ duration: 4, repeat: Infinity, delay: 0.5 }}
									className="absolute top-10 left-10 w-2 h-2 bg-blue-400 rounded-full blur-sm"
								/>
								<motion.div
									animate={{
										y: [0, -15, 0],
										opacity: [0.2, 0.5, 0.2],
									}}
									transition={{ duration: 5, repeat: Infinity, delay: 1.5 }}
									className="absolute bottom-20 right-10 w-1.5 h-1.5 bg-blue-300 rounded-full blur-sm"
								/>
								
								<div className="relative flex flex-col items-center text-center">
									{/* Icon with enhanced animation - Compact */}
									<motion.div
										whileHover={{ 
											scale: 1.15, 
											rotate: [0, 5, -5, 5, 0],
										}}
										whileTap={{ scale: 0.95 }}
										transition={{ 
											rotate: { duration: 0.5 },
											scale: { duration: 0.2 }
										}}
										className="w-20 h-20 bg-gradient-to-br from-blue-600 to-blue-500 rounded-3xl flex items-center justify-center mb-5 shadow-glow relative group/icon cursor-pointer"
									>
										<motion.div
											className="absolute inset-0 rounded-3xl bg-gradient-to-br from-blue-400 to-blue-600 opacity-0 group-hover/icon:opacity-100 blur-xl transition-opacity"
											animate={{ scale: [1, 1.2, 1] }}
											transition={{ duration: 2, repeat: Infinity }}
										/>
										<FiShield className="w-9 h-9 text-white relative z-10" />
									</motion.div>

									<motion.h2
										initial={{ opacity: 0, y: 10 }}
										animate={{ opacity: 1, y: 0 }}
										transition={{ delay: 0.6 }}
										className="text-2xl font-bold text-white mb-3"
									>
										For HR/Admin
									</motion.h2>
									<motion.p
										initial={{ opacity: 0 }}
										animate={{ opacity: 1 }}
										transition={{ delay: 0.7 }}
										className="text-zinc-400 mb-6 text-sm leading-relaxed max-w-xs"
									>
										Manage postings, review candidates, analytics.
									</motion.p>

									<ul className="space-y-3 mb-8 w-full max-w-xs">
										{[
											{ icon: FiCheck, text: 'Post & manage', color: 'blue' },
											{ icon: FiZap, text: 'AI JD parsing', color: 'blue' },
											{ icon: FiBarChart, text: 'Review apps', color: 'blue' },
											{ icon: FiTrendingUp, text: 'Insights', color: 'blue' }
										].map((feature, index) => (
											<motion.li
												key={index}
												initial={{ opacity: 0, y: 10 }}
												animate={{ opacity: 1, y: 0 }}
												transition={{ delay: 0.8 + index * 0.1 }}
												whileHover={{ scale: 1.05 }}
												className="flex items-center justify-center gap-2 text-sm text-zinc-300 group/item cursor-default"
											>
												<motion.div
													whileHover={{ rotate: 360, scale: 1.2 }}
													transition={{ duration: 0.5 }}
													className="flex-shrink-0 w-5 h-5 bg-blue-500/20 rounded-lg flex items-center justify-center group-hover/item:bg-blue-500/30 transition-colors"
												>
													<feature.icon className="w-3 h-3 text-blue-400" />
												</motion.div>
												<span className="group-hover/item:text-white transition-colors">{feature.text}</span>
											</motion.li>
										))}
									</ul>

									<Link to="/login/admin" className="w-full max-w-xs">
										<motion.button
											whileHover={{ scale: 1.03, y: -2 }}
											whileTap={{ scale: 0.97 }}
											className="w-full bg-gradient-to-r from-blue-600 via-blue-500 to-blue-600 hover:from-blue-500 hover:via-blue-400 hover:to-blue-500 text-white font-semibold py-3.5 text-sm rounded-xl transition-all shadow-glow flex items-center justify-center gap-2 group/btn relative overflow-hidden"
										>
											<motion.div
												className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent"
												animate={{ x: ['-100%', '200%'] }}
												transition={{ duration: 2, repeat: Infinity, repeatDelay: 1 }}
											/>
											<span className="relative z-10">Admin Login</span>
											<FiArrowRight className="w-4 h-4 relative z-10 group-hover/btn:translate-x-1 transition-transform" />
										</motion.button>
									</Link>
								</div>
							</motion.div>
						</div>
					</div>
				</motion.div>
			</motion.div>
		</section>
	)
}
