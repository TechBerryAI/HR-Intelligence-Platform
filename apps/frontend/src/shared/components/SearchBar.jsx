import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { FiSearch, FiMapPin } from 'react-icons/fi'

export default function SearchBar({ onSearch, large = false, defaultQuery = {}, className = '' }) {
  const [keywords, setKeywords] = useState(defaultQuery.keywords || '')
  const [location, setLocation] = useState(defaultQuery.location || '')
  const [isFocused, setIsFocused] = useState(false)

  const submit = (e) => {
    e.preventDefault()
    onSearch?.({ keywords: keywords.trim(), location: location.trim() })
  }

  return (
    <motion.form
      onSubmit={submit}
      className={`w-full ${className}`}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <motion.div
        className={`
          flex flex-col sm:flex-row gap-0 rounded-2xl bg-white dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 shadow-card overflow-hidden
          transition-all duration-200 ${isFocused ? 'ring-2 ring-accent-blue/30 border-accent-blue/50' : ''}
          ${large ? 'p-2 sm:p-2' : 'p-1.5 sm:p-1.5'}
        `}
        whileHover={{ boxShadow: '0 10px 40px -10px rgba(0,0,0,0.1)' }}
      >
        <div className="flex-1 flex items-center gap-3 px-4 py-3 sm:py-3">
          <FiSearch className="w-5 h-5 text-slate-400 dark:text-slate-500 flex-shrink-0" />
          <input
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            className="w-full outline-none placeholder:text-slate-400 dark:placeholder:text-slate-500 text-slate-900 dark:text-white bg-transparent text-sm sm:text-base"
            placeholder="Title, skills, or company"
          />
        </div>
        <div className="w-px bg-slate-200 dark:bg-slate-600 hidden sm:block self-stretch" />
        <div className="flex-1 flex items-center gap-3 px-4 py-3 sm:py-3">
          <FiMapPin className="w-5 h-5 text-slate-400 dark:text-slate-500 flex-shrink-0" />
          <input
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            className="w-full outline-none placeholder:text-slate-400 dark:placeholder:text-slate-500 text-slate-900 dark:text-white bg-transparent text-sm sm:text-base"
            placeholder="Location"
          />
        </div>
        <motion.button
          type="submit"
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className="sm:ml-2 m-2 sm:m-0 sm:mr-2 sm:my-2 bg-primary dark:bg-accent-blue text-white font-semibold px-6 py-3 rounded-xl transition-all shadow-md hover:opacity-90"
        >
          Search
        </motion.button>
      </motion.div>
    </motion.form>
  )
}
