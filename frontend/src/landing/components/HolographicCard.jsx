import React from 'react'
import { motion } from 'framer-motion'

export default function HolographicCard({ label, value, className = '', delay = 0, inline = false }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16, scale: 0.92 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.6, delay, ease: [0.22, 1, 0.36, 1] }}
      whileHover={{ scale: 1.04, y: -4 }}
      className={`${inline ? 'relative shrink-0' : 'absolute'} z-20 px-3 py-2 sm:px-4 sm:py-2.5 rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl shadow-[0_8px_32px_rgba(0,0,0,0.3)] ring-1 ring-inset ring-white/10 animate-hologram pointer-events-auto ${className}`}
    >
      <p className="text-[10px] sm:text-xs uppercase tracking-wider text-slate-400 font-medium">{label}</p>
      <p className="text-base sm:text-lg font-bold text-cyan-300 tabular-nums">{value}</p>
    </motion.div>
  )
}
