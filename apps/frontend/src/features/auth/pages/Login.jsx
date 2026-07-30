import React, { useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useApp } from '@/core/context/AppContext.jsx'
import { motion } from 'framer-motion'
import { FiShield, FiArrowRight, FiCheck, FiZap, FiTrendingUp, FiBarChart } from 'react-icons/fi'

export default function Login() {
  useApp()
  const location = useLocation()
  const fromLanding = location.state?.fromLanding

  useEffect(() => {
    if (!fromLanding) return
    const overlay = document.createElement('div')
    overlay.className = 'fixed inset-0 z-[200] pointer-events-none'
    overlay.style.background =
      'radial-gradient(ellipse at center, rgba(34,211,238,0.95) 0%, rgba(59,130,246,0.9) 40%, rgba(2,6,23,1) 100%)'
    overlay.style.opacity = '1'
    document.body.appendChild(overlay)
    requestAnimationFrame(() => {
      overlay.style.transition = 'opacity 0.7s ease-out'
      overlay.style.opacity = '0'
    })
    const timer = setTimeout(() => overlay.remove(), 800)
    return () => {
      clearTimeout(timer)
      overlay.remove()
    }
  }, [fromLanding])

  return (
    <section className="relative min-h-screen flex items-center justify-center px-4 py-12 overflow-hidden bg-slate-50 dark:bg-slate-900">
      <div className="absolute inset-0 bg-gradient-to-br from-slate-100/80 to-slate-50/80 dark:from-slate-900 dark:to-slate-800 pointer-events-none" />
      <motion.div
        initial={{ opacity: 0, y: fromLanding ? 12 : 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: fromLanding ? 0.7 : 0.5, delay: fromLanding ? 0.15 : 0 }}
        className="w-full max-w-lg mx-auto relative"
      >
        <div className="text-center mb-10">
          <h1 className="text-4xl sm:text-5xl font-bold text-slate-900 dark:text-white">
            Welcome Back
          </h1>
          <p className="mt-2 text-slate-600 dark:text-slate-400">
            Sign in to your HR account
          </p>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          whileHover={{ y: -4 }}
          className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/80 shadow-card hover:shadow-card-hover p-8 transition-all duration-300"
        >
          <div className="w-14 h-14 rounded-xl bg-accent-blue/10 dark:bg-accent-blue/20 flex items-center justify-center mb-5">
            <FiShield className="w-7 h-7 text-accent-blue" />
          </div>
          <h2 className="text-xl font-semibold text-slate-900 dark:text-white">For HR / Admin</h2>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            Manage postings, review candidates, analytics.
          </p>
          <ul className="mt-6 space-y-3">
            {[
              { icon: FiCheck, text: 'Post & manage' },
              { icon: FiZap, text: 'AI JD parsing' },
              { icon: FiBarChart, text: 'Review apps' },
              { icon: FiTrendingUp, text: 'Insights' },
            ].map((item, i) => (
              <li key={i} className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                <item.icon className="w-4 h-4 text-accent-blue flex-shrink-0" />
                {item.text}
              </li>
            ))}
          </ul>
          <Link
            to="/login/admin"
            className="mt-8 flex items-center justify-center gap-2 w-full rounded-xl bg-accent-blue text-white font-semibold py-3 shadow-md hover:opacity-90 transition-opacity"
          >
            Admin Login
            <FiArrowRight className="w-4 h-4" />
          </Link>
        </motion.div>
      </motion.div>
    </section>
  )
}
