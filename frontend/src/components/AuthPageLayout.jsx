import React from 'react'
import { motion } from 'framer-motion'

/**
 * Two-column auth layout: left = branding/illustration, right = form card.
 * On small screens stacks to single column with branding on top.
 */
export default function AuthPageLayout({ title, subtitle, children, illustration }) {
  return (
    <section className="min-h-[calc(100vh-64px)] flex flex-col lg:flex-row">
      {/* Left: Branding */}
      <div className="lg:w-1/2 flex items-center justify-center p-8 lg:p-12 bg-gradient-to-br from-slate-50 to-slate-100 dark:from-primary dark:to-secondary border-b lg:border-b-0 lg:border-r border-slate-200 dark:border-slate-700">
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5 }}
          className="max-w-md text-center lg:text-left"
        >
          {illustration || (
            <div className="w-20 h-20 mx-auto lg:mx-0 rounded-2xl bg-primary flex items-center justify-center text-white font-bold text-3xl shadow-lg mb-6">
              J
            </div>
          )}
          <h1 className="text-2xl lg:text-3xl font-bold text-slate-900 dark:text-white">
            {title}
          </h1>
          {subtitle && (
            <p className="mt-2 text-slate-600 dark:text-slate-400">
              {subtitle}
            </p>
          )}
        </motion.div>
      </div>

      {/* Right: Form */}
      <div className="lg:w-1/2 flex items-center justify-center p-6 sm:p-8 lg:p-12 bg-white dark:bg-slate-900">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          className="w-full max-w-md"
        >
          {children}
        </motion.div>
      </div>
    </section>
  )
}
