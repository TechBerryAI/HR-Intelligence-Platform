import React from 'react'
import SearchBar from './SearchBar.jsx'
import { motion } from 'framer-motion'

export default function FilterBar({ onSearch, initial }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 shadow-card p-4"
    >
      <SearchBar key={`${initial?.keywords ?? ''}|${initial?.location ?? ''}`} onSearch={onSearch} defaultQuery={initial || {}} />
    </motion.div>
  )
}
