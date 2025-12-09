import React from 'react'
import { motion } from 'framer-motion'
import { FiMapPin, FiDollarSign, FiClock, FiCheck, FiBookmark } from 'react-icons/fi'

// Helper function to format date for display
const formatDisplayDate = (dateString) => {
  if (!dateString) return ''
  try {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
  } catch {
    return dateString
  }
}

export default function JobCard({ job, onApply, isApplied = false, isSaved = false, onToggleSave, isAdmin = false }) {
  const isDisabled = job.enabled === false
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={!isDisabled ? { y: -4, transition: { duration: 0.2 } } : {}}
      className={`group glass-card rounded-2xl p-6 border transition-all duration-300 ${
        isDisabled
          ? 'border-zinc-800 opacity-50 pointer-events-none'
          : 'border-white/10 hover:border-purple-500/30 hover:shadow-premium'
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <h3 className={`text-xl font-bold transition ${isDisabled ? 'text-zinc-500' : 'text-white'}`}>
              {job.title}
            </h3>
            {isApplied && (
              <motion.span
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="inline-flex items-center gap-1.5 text-xs px-3 py-1 rounded-full bg-green-500/20 text-green-300 border border-green-500/30"
              >
                <FiCheck className="w-3 h-3" />
                Applied
              </motion.span>
            )}
            {!isApplied && isSaved && (
              <motion.span
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="inline-flex items-center gap-1.5 text-xs px-3 py-1 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30"
              >
                <FiBookmark className="w-3 h-3" />
                Saved
              </motion.span>
            )}
          </div>
          
          <p className={`text-sm mb-3 ${isDisabled ? 'text-zinc-500' : 'text-zinc-400'}`}>
            {job.company}
          </p>
          
          <div className={`flex flex-wrap items-center gap-4 text-sm ${isDisabled ? 'text-zinc-600' : 'text-zinc-400'}`}>
            <div className="flex items-center gap-1.5">
              <FiMapPin className="w-4 h-4" />
              <span>{job.location}</span>
            </div>
            {job.salary && (
              <div className="flex items-center gap-1.5">
                <FiDollarSign className="w-4 h-4" />
                <span>{job.salary}</span>
              </div>
            )}
            {(job.experienceFrom || job.experienceTo) && (
              <div className="flex items-center gap-1.5">
                <FiClock className="w-4 h-4" />
                <span>
                  {job.experienceFrom ?? ''}{(job.experienceFrom || job.experienceTo) ? '-' : ''}{job.experienceTo ?? ''} yrs
                </span>
              </div>
            )}
          </div>
          
          {job.postedOn && (
            <div className={`mt-3 text-xs ${isDisabled ? 'text-zinc-600' : 'text-zinc-500'}`}>
              <div className="flex items-center gap-1.5">
                <FiClock className="w-3 h-3" />
                <span>Posted on {formatDisplayDate(job.postedOn)}</span>
              </div>
            </div>
          )}
        </div>
        
        <div className="flex items-center gap-2">
          {!isAdmin && (
            <motion.button
              disabled={isDisabled || isApplied}
              onClick={onApply}
              whileHover={!isDisabled && !isApplied ? { scale: 1.05 } : {}}
              whileTap={!isDisabled && !isApplied ? { scale: 0.95 } : {}}
              className={`text-sm font-semibold px-5 py-2.5 rounded-xl transition-all duration-300 ${
                isDisabled || isApplied 
                  ? 'bg-zinc-700 text-zinc-500 cursor-not-allowed' 
                  : 'bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white shadow-glow'
              }`}
            >
              {isApplied ? 'Applied' : 'Apply Now'}
            </motion.button>
          )}
          {!isAdmin && onToggleSave && !isApplied && (
            <motion.button
              type="button"
              onClick={onToggleSave}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className={`p-2.5 rounded-xl border-2 transition-all duration-300 ${
                isSaved 
                  ? 'border-green-500/50 text-green-400 bg-green-500/10' 
                  : 'border-zinc-700 text-zinc-400 hover:border-purple-500/50 hover:text-purple-400 bg-white/5'
              }`}
              title={isSaved ? 'Unsave job' : 'Save job'}
            >
              <FiBookmark className={`w-4 h-4 ${isSaved ? 'fill-current' : ''}`} />
            </motion.button>
          )}
          {!isAdmin && onToggleSave && isApplied && (
            <button
              type="button"
              disabled
              className="p-2.5 rounded-xl border-2 border-zinc-800 text-zinc-600 cursor-not-allowed"
              title="Already applied"
            >
              <FiBookmark className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
      
      {job.description && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.1 }}
          className={`mt-4 text-sm line-clamp-2 ${isDisabled ? 'text-zinc-600' : 'text-zinc-300'}`}
        >
          {job.description}
        </motion.p>
      )}
    </motion.div>
  )
}
