import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { NAV_LINKS } from '../constants/landingContent.js'

function scrollToHash(href) {
  const id = href.replace('#', '')
  const el = document.getElementById(id)
  if (el) el.scrollIntoView({ behavior: 'smooth' })
}

export default function LandingNav({ scrollProgress = 0, onGetStarted }) {
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const scrolled = scrollProgress > 0.02

  return (
    <motion.header
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
      className="fixed top-0 left-0 right-0 z-50 px-6 sm:px-10 lg:px-12"
    >
      <div
        className={`max-w-[1440px] mx-auto mt-6 sm:mt-8 flex items-center justify-between min-h-[68px] sm:min-h-[76px] rounded-2xl sm:rounded-full px-4 sm:px-6 transition-all duration-500 ${
          scrolled
            ? 'bg-[#0a1220]/75 backdrop-blur-2xl border border-white/10 shadow-[0_12px_48px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(255,255,255,0.07)]'
            : 'bg-white/[0.06] backdrop-blur-xl border border-white/[0.09] shadow-[0_8px_32px_rgba(0,0,0,0.3),inset_0_1px_0_rgba(255,255,255,0.06)]'
        }`}
      >
        <button
          type="button"
          onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
          className="flex items-center gap-3.5 sm:gap-4 shrink-0 group"
        >
          <div className="relative h-11 w-11 sm:h-12 sm:w-12">
            <div className="absolute inset-0 rounded-full bg-gradient-to-br from-sky-400/35 to-blue-600/25 blur-lg group-hover:blur-xl transition-all" />
            <div className="relative h-full w-full rounded-full bg-gradient-to-br from-sky-400 to-blue-600 flex items-center justify-center text-white font-display font-bold text-lg ring-1 ring-white/25 shadow-inner">
              H
            </div>
          </div>
          <div className="hidden sm:block text-left">
            <span className="block font-display font-semibold text-lg sm:text-xl text-white tracking-tight leading-none">
              HR Intelligence
            </span>
            <span className="block text-[11px] sm:text-xs text-white/45 tracking-[0.2em] uppercase mt-1 font-medium">
              Enterprise Platform
            </span>
          </div>
        </button>

        <nav className="hidden lg:flex items-center gap-1 absolute left-1/2 -translate-x-1/2">
          {NAV_LINKS.map((link) => (
            <button
              key={link.href}
              type="button"
              onClick={() => scrollToHash(link.href)}
              className="relative px-5 py-2.5 text-[13px] font-medium uppercase tracking-[0.12em] text-white/55 hover:text-white transition-colors duration-300 group"
            >
              {link.label}
              <span className="absolute bottom-1.5 left-1/2 -translate-x-1/2 w-0 h-px bg-gradient-to-r from-transparent via-sky-400 to-transparent group-hover:w-4/5 transition-all duration-300" />
            </button>
          ))}
        </nav>

        <div className="flex items-center gap-3 sm:gap-4">
          <button
            type="button"
            onClick={() => navigate('/login')}
            className="hidden sm:inline-flex px-5 py-2.5 text-[15px] font-medium text-white/75 hover:text-white transition-colors"
          >
            Sign in
          </button>
          {onGetStarted && (
            <button
              type="button"
              onClick={onGetStarted}
              className="hidden md:inline-flex items-center px-7 py-3 rounded-full text-[15px] font-semibold text-white bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 border border-sky-400/25 transition-all duration-300 shadow-[0_6px_28px_rgba(14,165,233,0.35)]"
            >
              Get Started
            </button>
          )}
          <button
            type="button"
            className="lg:hidden p-3 text-white/70 hover:text-white rounded-full hover:bg-white/5 transition-colors"
            onClick={() => setMenuOpen((o) => !o)}
            aria-label="Toggle menu"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeWidth={1.5}
                d={menuOpen ? 'M6 18L18 6M6 6l12 12' : 'M4 6h16M4 12h16M4 18h16'}
              />
            </svg>
          </button>
        </div>
      </div>

      {menuOpen && (
        <motion.div
          initial={{ opacity: 0, y: -8, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          className="lg:hidden mt-4 mx-1 rounded-2xl border border-white/10 bg-[#0a1220]/92 backdrop-blur-2xl p-4 space-y-1 shadow-[0_24px_64px_rgba(0,0,0,0.55)]"
        >
          {NAV_LINKS.map((link) => (
            <button
              key={link.href}
              type="button"
              onClick={() => {
                scrollToHash(link.href)
                setMenuOpen(false)
              }}
              className="block w-full text-left px-4 py-3.5 text-[15px] text-white/65 hover:text-white rounded-xl hover:bg-white/[0.05] transition-colors"
            >
              {link.label}
            </button>
          ))}
          <div className="pt-3 mt-3 border-t border-white/[0.08] flex gap-3">
            <button
              type="button"
              onClick={() => {
                navigate('/login')
                setMenuOpen(false)
              }}
              className="flex-1 px-4 py-3 text-[15px] text-white/75 font-medium rounded-xl border border-white/12 hover:bg-white/[0.04]"
            >
              Sign in
            </button>
            {onGetStarted && (
              <button
                type="button"
                onClick={() => {
                  onGetStarted()
                  setMenuOpen(false)
                }}
                className="flex-1 px-4 py-3 text-[15px] text-white font-semibold rounded-xl bg-gradient-to-r from-sky-500 to-blue-600"
              >
                Get Started
              </button>
            )}
          </div>
        </motion.div>
      )}
    </motion.header>
  )
}
