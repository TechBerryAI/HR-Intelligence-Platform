import React, { Suspense } from 'react'
import SearchBar from './SearchBar.jsx'
import { motion } from 'framer-motion'

const HeroVisual = React.lazy(() => import('./hero/HeroVisual.jsx'))
import { FiCpu, FiZap, FiLayers } from 'react-icons/fi'

export default function Hero({ onSearch }) {
  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-slate-50 to-white dark:from-slate-900 dark:to-slate-800 border-b border-slate-200 dark:border-slate-700">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(59,130,246,0.08),transparent)] dark:bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(59,130,246,0.12),transparent)] pointer-events-none" />
      <div className="absolute top-20 right-0 w-96 h-96 bg-accent-blue/5 rounded-full blur-3xl pointer-events-none" />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16 lg:py-20">
        <div className="grid lg:grid-cols-2 gap-10 lg:gap-12 items-center">
          {/* Left: copy + search */}
          <div className="text-center lg:text-left order-2 lg:order-1">
            <motion.div
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, ease: 'easeOut' }}
            >
              <p className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider bg-accent-blue/10 text-accent-blue dark:bg-accent-blue/20 dark:text-accent-blue-light border border-accent-blue/20 mb-4">
                HRMS · AI Workforce Platform
              </p>
              <h1 className="text-4xl sm:text-5xl lg:text-5xl xl:text-6xl font-bold tracking-tight text-slate-900 dark:text-white leading-[1.1]">
                Find Your Dream Job
                <br />
                <span className="text-primary dark:text-accent-blue-light">Today</span>
              </h1>
            </motion.div>

            <motion.p
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.15 }}
              className="mt-6 text-lg sm:text-xl text-slate-600 dark:text-slate-400 max-w-xl mx-auto lg:mx-0 leading-relaxed"
            >
              Explore opportunities from top companies.{' '}
              <span className="font-semibold text-primary dark:text-accent-blue">AI-powered matching</span> helps you find the perfect role.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.3 }}
              className="mt-8 flex flex-wrap items-center justify-center lg:justify-start gap-3"
            >
              {[
                { Icon: FiCpu, text: 'AI Resume Parsing' },
                { Icon: FiZap, text: 'Instant Apply' },
                { Icon: FiLayers, text: 'Smart Matching' },
              ].map((feature, index) => {
                const Icon = feature.Icon
                return (
                  <motion.span
                    key={index}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.4 + index * 0.08 }}
                    whileHover={{ scale: 1.03, y: -2 }}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-card text-slate-600 dark:text-slate-300 text-sm font-medium"
                  >
                    <Icon className="w-4 h-4 text-accent-blue flex-shrink-0" aria-hidden />
                    {feature.text}
                  </motion.span>
                )
              })}
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.5 }}
              className="mt-10 max-w-xl mx-auto lg:mx-0"
            >
              <SearchBar onSearch={onSearch} large />
            </motion.div>
          </div>

          {/* Right: 3D visual */}
          <motion.div
            initial={{ opacity: 0, scale: 0.92 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, delay: 0.2, ease: 'easeOut' }}
            className="order-1 lg:order-2"
          >
            <Suspense
              fallback={
                <div
                  className="w-full aspect-[900/580] min-h-[220px] sm:min-h-[320px] rounded-2xl sm:rounded-3xl bg-slate-900/90 border border-slate-700/40 animate-pulse"
                  aria-hidden
                />
              }
            >
              <HeroVisual />
            </Suspense>
          </motion.div>
        </div>
      </div>
    </section>
  )
}
