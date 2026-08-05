import React, { useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useApp } from '@/core/context/AppContext.jsx'
import { motion } from 'framer-motion'
import {
  FiShield,
  FiArrowRight,
  FiArrowLeft,
  FiCheck,
  FiZap,
  FiTrendingUp,
  FiBarChart,
  FiTarget,
} from 'react-icons/fi'

const HERO_FEATURES = [
  { icon: FiZap, label: 'AI JD Parsing' },
  { icon: FiTarget, label: 'Intelligent Candidate Matching' },
  { icon: FiTrendingUp, label: 'Recruitment Insights' },
]

const CARD_FEATURES = [
  { icon: FiCheck, text: 'Post & Manage Jobs' },
  { icon: FiZap, text: 'AI JD Parsing' },
  { icon: FiBarChart, text: 'Review Candidates' },
  { icon: FiTrendingUp, text: 'Recruitment Insights' },
]

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
    <section className="auth-portal relative overflow-hidden">
      <div className="auth-portal-deco absolute inset-0 z-0" aria-hidden="true" />
      <div
        className="auth-portal-orb w-[28rem] h-[28rem] -top-24 -left-20 bg-[rgba(0,166,255,0.16)] z-0"
        aria-hidden="true"
      />
      <div
        className="auth-portal-orb w-[26rem] h-[26rem] bottom-[-4rem] right-[-2rem] bg-[rgba(121,87,255,0.14)] z-0"
        aria-hidden="true"
      />

      <div className="auth-portal-grid relative z-10">
        <aside className="auth-portal-hero">
          <motion.div
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: fromLanding ? 0.7 : 0.5, delay: fromLanding ? 0.12 : 0 }}
            className="auth-story-glass"
          >
            <p className="relative z-10 flex items-center gap-2.5 text-sm text-[var(--ei-text-secondary)] tracking-wide">
              <span className="inline-block h-2 w-2 rounded-full bg-sky-400 shadow-[0_0_10px_rgba(56,189,248,0.8)]" />
              next generation HR technology
            </p>
            <h1 className="relative z-10 mt-5 font-display text-[clamp(2rem,3.5vw,2.85rem)] font-semibold leading-[1.08] tracking-[-0.03em] text-[var(--ei-text-primary)]">
              Smarter Hiring.
              <br />
              Better Decisions.
              <br />
              <span className="text-[#0284c7] dark:text-[#5EC8FF] [text-shadow:none] dark:[text-shadow:0_0_24px_rgba(56,189,248,0.45)]">
                Powered by AI.
              </span>
            </h1>
            <p className="relative z-10 mt-5 max-w-[460px] text-base sm:text-lg font-light leading-relaxed text-[var(--ei-text-secondary)]">
              AI-powered recruitment intelligence designed to help modern HR teams hire faster
              and make better decisions.
            </p>

            <ul className="relative z-10 mt-7 space-y-3">
              {HERO_FEATURES.map(({ icon: Icon, label }) => (
                <li key={label} className="flex items-center gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] border border-[var(--ei-border-primary)] bg-[var(--ei-surface-hover)]">
                    <Icon className="h-4 w-4 text-sky-500" aria-hidden="true" />
                  </span>
                  <span className="text-sm font-medium text-[var(--ei-text-primary)]">{label}</span>
                </li>
              ))}
            </ul>

            <p className="relative z-10 mt-8 border-t border-[var(--ei-border-primary)] pt-5 text-xs font-medium tracking-wide text-[var(--ei-text-muted)]">
              Enterprise-grade HR technology
            </p>
          </motion.div>
        </aside>

        <div className="auth-portal-panel">
          <motion.div
            initial={{ opacity: 0, y: fromLanding ? 12 : 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: fromLanding ? 0.65 : 0.4, delay: fromLanding ? 0.18 : 0.05 }}
            className="w-full max-w-[460px]"
          >
            <div className="mb-5 lg:mb-6">
              <Link
                to="/"
                className="mb-4 inline-flex items-center gap-2 text-sm font-medium text-[var(--ei-text-muted)] transition-colors hover:text-[var(--ei-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/40 rounded-lg"
              >
                <FiArrowLeft className="h-4 w-4" aria-hidden="true" />
                Back to home
              </Link>
              <p className="mb-3 text-[11px] font-semibold tracking-[0.18em] uppercase text-[var(--ei-text-muted)] lg:hidden">
                HR Intelligence
              </p>
              <h2 className="font-display text-[clamp(1.75rem,3vw,2.15rem)] font-bold tracking-tight text-[var(--ei-text-primary)]">
                Welcome back
              </h2>
              <p className="mt-1.5 text-[14px] sm:text-[15px] text-[var(--ei-text-secondary)]">
                Sign in to your HR Intelligence account
              </p>
            </div>

            <div className="auth-glass-card">
              <div
                className="mb-5 flex h-14 w-14 items-center justify-center rounded-[14px] border border-sky-400/25 bg-gradient-to-br from-sky-500/20 to-blue-600/20 shadow-[0_0_24px_rgba(14,165,233,0.15)]"
              >
                <FiShield className="h-7 w-7 text-sky-500" aria-hidden="true" />
              </div>

              <h3 className="text-[20px] sm:text-[22px] font-semibold tracking-tight text-[var(--ei-text-primary)]">
                HR / Admin Access
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed text-[var(--ei-text-secondary)]">
                Manage job postings, review candidates and access recruitment insights.
              </p>

              <ul className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3">
                {CARD_FEATURES.map(({ icon: Icon, text }) => (
                  <li
                    key={text}
                    className="flex items-center gap-2 text-[13px] sm:text-sm text-[var(--ei-text-secondary)]"
                  >
                    <Icon className="h-3.5 w-3.5 shrink-0 text-sky-500" aria-hidden="true" />
                    {text}
                  </li>
                ))}
              </ul>

              <Link to="/login/admin" className="auth-cta mt-7">
                Admin Login
                <FiArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>

              <p className="mt-4 flex items-center justify-center gap-1.5 text-center text-xs text-[var(--ei-text-muted)]">
                <FiShield className="h-3 w-3 shrink-0" aria-hidden="true" />
                Secure enterprise authentication
              </p>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  )
}
