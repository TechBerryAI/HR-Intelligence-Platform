import React from 'react'
import { motion } from 'framer-motion'
import { FiZap, FiTarget, FiTrendingUp } from 'react-icons/fi'
import BrandMark from '@/shared/components/BrandMark.jsx'

const HERO_FEATURES = [
  { icon: FiZap, label: 'AI JD Parsing' },
  { icon: FiTarget, label: 'Intelligent Candidate Matching' },
  { icon: FiTrendingUp, label: 'Recruitment Insights' },
]

/**
 * Two-column auth layout: left = branding glass, right = form card.
 * Shared atmosphere — no hard partition. Hero hidden below 1100px.
 * Colors follow global Dark/Light via --ei-* tokens.
 */
export default function AuthPageLayout({ title, subtitle, children, illustration }) {
  return (
    <section className="auth-portal relative overflow-hidden">
      <div className="auth-portal-deco absolute inset-0 z-0" aria-hidden="true" />
      <div
        className="auth-portal-orb w-[28rem] h-[28rem] -top-24 -left-20 bg-[rgba(120,150,170,0.1)] z-0"
        aria-hidden="true"
      />
      <div
        className="auth-portal-orb w-[26rem] h-[26rem] bottom-[-4rem] right-[-2rem] bg-[rgba(90,110,130,0.08)] z-0"
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
            {illustration || <BrandMark size="lg" className="relative z-10 mb-5" />}
            <p className="relative z-10 flex items-center gap-2.5 text-sm text-[var(--ei-text-secondary)] tracking-wide">
              <span className="inline-block h-2 w-2 rounded-full bg-[var(--ei-accent-teal)]/90" />
              next generation HR technology
            </p>
            <h1 className="relative z-10 mt-5 font-display text-[clamp(1.85rem,3vw,2.5rem)] font-semibold leading-[1.1] tracking-[-0.03em] text-[var(--ei-text-primary)]">
              {title}
            </h1>
            {subtitle && (
              <p className="relative z-10 mt-4 max-w-[460px] text-base font-light leading-relaxed text-[var(--ei-text-secondary)]">
                {subtitle}
              </p>
            )}
            <ul className="relative z-10 mt-7 space-y-3">
              {HERO_FEATURES.map(({ icon: Icon, label }) => (
                <li key={label} className="flex items-center gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] border border-[var(--ei-border-primary)] bg-[var(--ei-surface-hover)]">
                    <Icon className="h-4 w-4 text-[var(--ei-accent-teal)]" aria-hidden="true" />
                  </span>
                  <span className="text-sm font-medium text-[var(--ei-text-primary)]">{label}</span>
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
