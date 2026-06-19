import React from 'react'
import { motion } from 'framer-motion'
import { FiChevronRight } from 'react-icons/fi'
import { HERO_COPY } from '../constants/landingContent.js'

const TRUST_STATS = [
  { value: '94%', label: 'AI match accuracy' },
  { value: '1.2k+', label: 'Active roles' },
  { value: '99.9%', label: 'Uptime SLA' },
]

export default function LandingHero({ onGetStarted, onWatchDemo }) {
  return (
    <section className="relative z-10 min-h-screen pointer-events-none flex items-center">
      <div className="w-full max-w-[1440px] mx-auto px-6 sm:px-10 lg:px-12 py-28 sm:py-32">
        <motion.div
          initial={{ opacity: 0, y: 32, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.85, ease: [0.22, 1, 0.36, 1] }}
          className="pointer-events-auto landing-hero-glass-card w-full max-w-[500px] sm:max-w-[540px] lg:max-w-[580px] px-8 sm:px-10 lg:px-12 py-9 sm:py-10 lg:py-12"
        >
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.1 }}
            className="flex items-center gap-2.5 text-sm sm:text-[15px] text-white/75 font-normal tracking-wide mb-7 sm:mb-8"
          >
            <span className="inline-block w-2 h-2 rounded-full bg-sky-400 shadow-[0_0_10px_rgba(56,189,248,0.8)]" />
            next generation HR technology
          </motion.p>

          <motion.h1
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.75, delay: 0.18, ease: [0.22, 1, 0.36, 1] }}
            className="font-display text-[2.6rem] sm:text-5xl lg:text-[3.35rem] xl:text-[3.65rem] font-semibold text-white tracking-[-0.03em] leading-[1.08] landing-hero-glass-title"
          >
            The Future of
            <br />
            HR Technology
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.28 }}
            className="mt-6 sm:mt-7 text-lg sm:text-xl text-white/85 font-light leading-relaxed max-w-[460px] landing-hero-glass-body"
          >
            {HERO_COPY.subheadline}
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.38 }}
            className="mt-8 sm:mt-10 flex flex-col sm:flex-row items-stretch sm:items-center gap-3.5"
          >
            <button
              type="button"
              onClick={onGetStarted}
              className="group inline-flex items-center justify-center gap-1.5 px-8 py-3.5 sm:py-4 rounded-full bg-white text-slate-900 font-semibold text-base sm:text-[17px] shadow-[0_8px_32px_rgba(255,255,255,0.15)] hover:bg-white/95 hover:scale-[1.02] transition-all duration-300"
            >
              {HERO_COPY.primaryCta}
              <FiChevronRight className="w-5 h-5 group-hover:translate-x-0.5 transition-transform" />
            </button>

            <button
              type="button"
              onClick={onWatchDemo}
              className="inline-flex items-center justify-center px-8 py-3.5 sm:py-4 rounded-full font-medium text-base sm:text-[17px] text-white border border-white/35 bg-transparent hover:bg-white/10 hover:border-white/50 transition-all duration-300"
            >
              {HERO_COPY.secondaryCta}
            </button>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.8, delay: 0.52 }}
            className="mt-8 sm:mt-9 pt-6 border-t border-white/[0.08] flex flex-wrap gap-x-6 gap-y-2"
          >
            {TRUST_STATS.map((stat) => (
              <span key={stat.label} className="text-sm text-white/55">
                <span className="font-semibold text-white/90">{stat.value}</span>
                <span className="ml-1.5">{stat.label}</span>
              </span>
            ))}
          </motion.div>
        </motion.div>
      </div>
    </section>
  )
}
