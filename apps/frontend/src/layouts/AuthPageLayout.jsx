import React from 'react'
import { motion } from 'framer-motion'
import { FiZap, FiTarget, FiTrendingUp } from 'react-icons/fi'

const HERO_FEATURES = [
  { icon: FiZap, label: 'AI JD Parsing' },
  { icon: FiTarget, label: 'Intelligent Candidate Matching' },
  { icon: FiTrendingUp, label: 'Recruitment Insights' },
]

/**
 * Two-column auth layout: left = branding glass, right = form card.
 * Shared atmosphere — no hard partition. Hero hidden below 1100px.
 */
export default function AuthPageLayout({ title, subtitle, children, illustration }) {
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
            transition={{ duration: 0.5 }}
            className="auth-story-glass"
          >
            {illustration || (
              <div className="relative z-10 mb-5 flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-sky-400 to-blue-600 font-display text-lg font-bold text-white ring-1 ring-white/25">
                H
              </div>
            )}
            <p className="relative z-10 flex items-center gap-2.5 text-sm text-white/75 tracking-wide">
              <span className="inline-block h-2 w-2 rounded-full bg-sky-400 shadow-[0_0_10px_rgba(56,189,248,0.8)]" />
              next generation HR technology
            </p>
            <h1 className="relative z-10 mt-5 font-display text-[clamp(1.85rem,3vw,2.5rem)] font-semibold leading-[1.1] tracking-[-0.03em] text-white landing-hero-glass-title">
              {title}
            </h1>
            {subtitle && (
              <p className="relative z-10 mt-4 max-w-[460px] text-base font-light leading-relaxed text-white/75 landing-hero-glass-body">
                {subtitle}
              </p>
            )}
            <ul className="relative z-10 mt-7 space-y-3">
              {HERO_FEATURES.map(({ icon: Icon, label }) => (
                <li key={label} className="flex items-center gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] border border-white/10 bg-white/[0.06]">
                    <Icon className="h-4 w-4 text-sky-400" aria-hidden="true" />
                  </span>
                  <span className="text-sm font-medium text-white/85">{label}</span>
                </li>
              ))}
            </ul>
          </motion.div>
        </aside>

        <div className="auth-portal-panel">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.08 }}
            className="w-full max-w-[460px]"
          >
            {children}
          </motion.div>
        </div>
      </div>
    </section>
  )
}
