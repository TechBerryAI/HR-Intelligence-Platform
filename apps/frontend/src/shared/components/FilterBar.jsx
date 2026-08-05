import React from 'react'
import SearchBar from './SearchBar.jsx'
import { motion } from 'framer-motion'

export default function FilterBar({ onSearch, initial, theme = 'default' }) {
  const enterprise = theme === 'enterprise'
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className={
        enterprise
          ? 'rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4 shadow-[0_8px_32px_rgba(0,0,0,0.2)]'
          : 'rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 shadow-card p-4'
      }
    >
      <SearchBar
        theme={theme}
        key={`${initial?.keywords ?? ''}|${initial?.location ?? ''}`}
        onSearch={onSearch}
        defaultQuery={initial || {}}
      />
    </motion.div>
  )
}
