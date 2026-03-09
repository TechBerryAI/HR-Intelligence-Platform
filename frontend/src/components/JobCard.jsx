import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FiMapPin, FiClock, FiCheck, FiBookmark, FiX } from 'react-icons/fi'

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
  const [showDescriptionModal, setShowDescriptionModal] = useState(false)

  useEffect(() => {
    if (!showDescriptionModal) return
    const onEscape = (e) => { if (e.key === 'Escape') setShowDescriptionModal(false) }
    window.addEventListener('keydown', onEscape)
    return () => window.removeEventListener('keydown', onEscape)
  }, [showDescriptionModal])

  const openModal = (e) => {
    if (isDisabled) return
    if (e.target.closest('button')) return // don't open when clicking Apply / Bookmark
    setShowDescriptionModal(true)
  }

  return (
    <>
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={!isDisabled ? { y: -4, transition: { duration: 0.2 } } : {}}
      onClick={openModal}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openModal(e) } }}
      className={`group glass-card rounded-2xl p-6 border transition-all duration-300 cursor-pointer ${
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
        
        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
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

    <AnimatePresence>
      {showDescriptionModal && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
          onClick={() => setShowDescriptionModal(false)}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ type: 'tween', duration: 0.2 }}
            className="relative w-full max-w-2xl max-h-[85vh] flex flex-col rounded-2xl border border-white/10 bg-zinc-900/95 shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex-shrink-0 px-6 pt-6 pb-4 border-b border-white/10">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-xl font-bold text-white">{job.title}</h3>
                  <p className="text-sm text-zinc-400 mt-1">{job.company}</p>
                </div>
                <button
                  type="button"
                  onClick={() => setShowDescriptionModal(false)}
                  className="p-2 rounded-xl text-zinc-400 hover:text-white hover:bg-white/10 transition-colors"
                  aria-label="Close"
                >
                  <FiX className="w-5 h-5" />
                </button>
              </div>
              <div className="flex flex-wrap items-center gap-4 mt-3 text-sm text-zinc-400">
                {job.location && (
                  <span className="flex items-center gap-1.5">
                    <FiMapPin className="w-4 h-4" />
                    {job.location}
                  </span>
                )}
                {job.salary && <span>{job.salary}</span>}
                {(job.experienceFrom || job.experienceTo) && (
                  <span className="flex items-center gap-1.5">
                    <FiClock className="w-4 h-4" />
                    {job.experienceFrom ?? ''}{(job.experienceFrom || job.experienceTo) ? '-' : ''}{job.experienceTo ?? ''} yrs
                  </span>
                )}
                {job.postedOn && (
                  <span className="flex items-center gap-1.5">
                    <FiClock className="w-3 h-3" />
                    Posted on {formatDisplayDate(job.postedOn)}
                  </span>
                )}
              </div>
            </div>
            <div className="flex-1 overflow-y-auto px-6 py-5">
              <h4 className="text-sm font-semibold text-zinc-300 mb-2">Full description</h4>
              <div className="text-sm text-zinc-300 whitespace-pre-wrap leading-relaxed">
                {job.description || 'No description provided.'}
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
    </>
  )
}
