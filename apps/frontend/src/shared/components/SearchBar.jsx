import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { FiSearch, FiMapPin } from 'react-icons/fi'

export default function SearchBar({ onSearch, large = false, defaultQuery = {}, className = '', theme = 'default' }) {
  const [keywords, setKeywords] = useState(defaultQuery.keywords || '')
  const [location, setLocation] = useState(defaultQuery.location || '')
  const [isFocused, setIsFocused] = useState(false)
  const enterprise = theme === 'enterprise'

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
          flex flex-col sm:flex-row gap-0 rounded-2xl overflow-hidden transition-all duration-200
          ${large ? 'p-2 sm:p-2' : 'p-1.5 sm:p-1.5'}
          ${
            enterprise
              ? `bg-white/[0.04] border border-white/[0.08] ${isFocused ? 'ring-2 ring-[#3AA9FF]/30 border-[#3AA9FF]/40' : ''}`
              : `bg-white dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 shadow-card ${isFocused ? 'ring-2 ring-accent-blue/30 border-accent-blue/50' : ''}`
          }
        `}
      >
        <div className="flex-1 flex items-center gap-3 px-4 py-3 sm:py-3">
          <FiSearch className={`w-5 h-5 flex-shrink-0 ${enterprise ? 'text-[#8796A5]' : 'text-slate-400 dark:text-slate-500'}`} />
          <input
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            className={`w-full outline-none bg-transparent text-sm sm:text-base ${
              enterprise
                ? 'text-[#F5F7FA] placeholder:text-[#738394]'
                : 'placeholder:text-slate-400 dark:placeholder:text-slate-500 text-slate-900 dark:text-white'
            }`}
            placeholder="Title, skills, or company"
          />
        </div>
        <div className={`w-px hidden sm:block self-stretch ${enterprise ? 'bg-white/10' : 'bg-slate-200 dark:bg-slate-600'}`} />
        <div className="flex-1 flex items-center gap-3 px-4 py-3 sm:py-3">
          <FiMapPin className={`w-5 h-5 flex-shrink-0 ${enterprise ? 'text-[#8796A5]' : 'text-slate-400 dark:text-slate-500'}`} />
          <input
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            className={`w-full outline-none bg-transparent text-sm sm:text-base ${
              enterprise
                ? 'text-[#F5F7FA] placeholder:text-[#738394]'
                : 'placeholder:text-slate-400 dark:placeholder:text-slate-500 text-slate-900 dark:text-white'
            }`}
            placeholder="Location"
          />
        </div>
        <motion.button
          type="submit"
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className={`sm:ml-2 m-2 sm:m-0 sm:mr-2 sm:my-2 font-semibold px-6 py-3 rounded-xl transition-all ${
            enterprise
              ? 'bg-[var(--ei-btn-primary-from)] text-[var(--ei-btn-primary-text)] shadow-[0_8px_20px_var(--ei-btn-primary-shadow)] hover:brightness-105'
              : 'bg-primary text-white shadow-md hover:opacity-90'
          }`}
        >
          Search
        </motion.button>
      </motion.div>
    </motion.form>
  )
}
