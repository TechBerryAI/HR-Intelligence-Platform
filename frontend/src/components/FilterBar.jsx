import React from 'react'
import SearchBar from './SearchBar.jsx'
import { motion } from 'framer-motion'

export default function FilterBar({ onSearch, initial }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card border border-white/10 rounded-2xl p-4"
    >
      <SearchBar key={`${initial.keywords}|${initial.location}`} onSearch={onSearch} defaultQuery={initial} />
    </motion.div>
  )
}
