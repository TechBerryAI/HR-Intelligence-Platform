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
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <motion.div
        className={`flex flex-col sm:flex-row gap-3 sm:gap-0 glass-card rounded-2xl shadow-premium border-2 transition-all duration-300 ${
          isFocused ? 'border-purple-500/50' : 'border-white/10'
        } ${large ? 'p-3' : 'p-2'} overflow-hidden`}
        whileHover={{ scale: 1.01 }}
      >
        <div className="flex-1 flex items-center gap-3 px-4 py-3 relative">
          <FiSearch className="w-5 h-5 text-zinc-400" />
          <input
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            className="w-full outline-none placeholder:text-zinc-400 text-gray-100 bg-transparent"
            placeholder="Title, skills, or company"
          />
        </div>
        <div className="w-px bg-zinc-700 hidden sm:block" />
        <div className="flex-1 flex items-center gap-3 px-4 py-3">
          <FiMapPin className="w-5 h-5 text-zinc-400" />
          <input
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            className="w-full outline-none placeholder:text-zinc-400 text-gray-100 bg-transparent"
            placeholder="Location"
          />
        </div>
        <motion.button
          type="submit"
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="sm:ml-2 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white font-semibold px-8 py-3 rounded-xl transition-all shadow-glow"
        >
          Search
        </motion.button>
      </motion.div>
    </motion.form>
  )
}
