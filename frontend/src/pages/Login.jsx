import React from 'react'
import { Link } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'
import { motion } from 'framer-motion'
import { FiUser, FiShield, FiArrowRight, FiCheck, FiZap, FiTrendingUp, FiBarChart } from 'react-icons/fi'

export default function Login() {
  useApp()

  return (
    <section className="relative min-h-[calc(100vh-64px)] flex items-center justify-center px-4 py-12 overflow-hidden bg-slate-50 dark:bg-slate-900">
      <div className="absolute inset-0 bg-gradient-to-br from-slate-100/80 to-slate-50/80 dark:from-slate-900 dark:to-slate-800 pointer-events-none" />
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-4xl mx-auto relative"
      >
        <div className="text-center mb-10">
          <h1 className="text-4xl sm:text-5xl font-bold text-slate-900 dark:text-white">
            Welcome Back
          </h1>
          <p className="mt-2 text-slate-600 dark:text-slate-400">
            Choose your account type to continue
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-6 max-w-3xl mx-auto">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 }}
            whileHover={{ y: -4 }}
            className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/80 shadow-card hover:shadow-card-hover p-8 transition-all duration-300"
          >
            <div className="w-14 h-14 rounded-xl bg-primary/10 dark:bg-accent-blue/20 flex items-center justify-center mb-5">
              <FiUser className="w-7 h-7 text-primary dark:text-accent-blue" />
            </div>
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white">For Applicants</h2>
            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
              Access applications, saved jobs, and alerts.
            </p>
            <ul className="mt-6 space-y-3">
              {[
                { icon: FiZap, text: 'Apply instantly' },
                { icon: FiCheck, text: 'AI resume parsing' },
                { icon: FiTrendingUp, text: 'Track status' },
                { icon: FiCheck, text: 'Save jobs' },
              ].map((item, i) => (
                <li key={i} className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                  <item.icon className="w-4 h-4 text-primary dark:text-accent-blue flex-shrink-0" />
                  {item.text}
                </li>
              ))}
            </ul>
            <Link
              to="/login/applicant"
              className="mt-8 flex items-center justify-center gap-2 w-full rounded-xl bg-primary dark:bg-accent-blue text-white font-semibold py-3 shadow-md hover:opacity-90 transition-opacity"
            >
              Applicant Login
              <FiArrowRight className="w-4 h-4" />
            </Link>
            <p className="mt-4 text-center text-xs text-slate-500 dark:text-slate-400">
              Don't have an account? <Link to="/signup/applicant" className="font-medium text-primary dark:text-accent-blue hover:underline">Sign up</Link>
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
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
        </div>
      </motion.div>
    </section>
  )
}
