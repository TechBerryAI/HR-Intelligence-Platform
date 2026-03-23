import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FiMapPin, FiClock, FiCheck, FiBookmark, FiX, FiEye, FiAward, FiSlash, FiBriefcase } from 'react-icons/fi'
import { Badge, Card, CardContent, Button } from './ui/index.js'
import { extractRequiredSkillsFromDescription } from '@/lib/jobDescription.js'
import JobDescriptionView from './JobDescriptionView.jsx'

const formatDisplayDate = (dateString) => {
  if (!dateString) return ''
  try {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
  } catch {
    return dateString
  }
}

const STATUS_BADGES = {
  applied: { label: 'Applied', Icon: FiCheck, variant: 'success' },
  reviewed: { label: 'Reviewed', Icon: FiEye, variant: 'warning' },
  shortlisted: { label: 'Shortlisted', Icon: FiAward, variant: 'accent' },
  rejected: { label: 'Rejected', Icon: FiSlash, variant: 'danger' },
}

export default function JobCard({ job, onApply, isApplied = false, applicationStatus = 'applied', isSaved = false, onToggleSave, isAdmin = false, isApplying = false, matchScore }) {
  const isDisabled = job.enabled === false
  const [showDescriptionModal, setShowDescriptionModal] = useState(false)
  const statusConfig = STATUS_BADGES[applicationStatus] || STATUS_BADGES.applied
  const StatusIcon = statusConfig.Icon

  // Required skills: prefer **Required Skills:** block from description (Grok format), else job.skills, else regex
  const fromBlock = extractRequiredSkillsFromDescription(job.description || '')
  const rawFallback = job.skills || (job.description && job.description.match(/\b(React|JavaScript|Python|Node|AWS|SQL|TypeScript|Java|Go|Rust|ExaCC|ExaData|RAC|RMAN|Dataguard|OCI|ASM|Oracle)\b/gi)) || []
  const rawSkills = fromBlock.length > 0 ? fromBlock : rawFallback
  const skills = [...new Map(rawSkills.map((s) => {
    const key = (typeof s === 'string' ? s : String(s)).trim()
    const normalized = key.toLowerCase()
    return [normalized, key]
  })).values()]

  useEffect(() => {
    if (!showDescriptionModal) return
    const onEscape = (e) => { if (e.key === 'Escape') setShowDescriptionModal(false) }
    window.addEventListener('keydown', onEscape)
    return () => window.removeEventListener('keydown', onEscape)
  }, [showDescriptionModal])

  const openModal = (e) => {
    if (isDisabled) return
    if (e.target.closest('button')) return
    setShowDescriptionModal(true)
  }

  return (
    <>
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        whileHover={!isDisabled ? { y: -2, transition: { duration: 0.2 } } : {}}
        onClick={openModal}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openModal(e) } }}
        className={isDisabled ? 'opacity-60 pointer-events-none' : 'cursor-pointer'}
      >
        <Card className={`p-6 transition shadow-sm hover:shadow-md ${isDisabled ? '' : 'hover:border-slate-300'}`}>
          <CardContent className="p-0 space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center text-slate-500">
                    <FiBriefcase className="w-6 h-6" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className={`text-lg font-semibold truncate ${isDisabled ? 'text-slate-400' : 'text-slate-900'}`}>
                        {job.title}
                      </h3>
                      {matchScore != null && <Badge variant="blue">{matchScore}% match</Badge>}
                      {isApplied && (
                        <Badge variant={statusConfig.variant} className="inline-flex items-center gap-1">
                          <StatusIcon className="w-3 h-3" /> {statusConfig.label}
                        </Badge>
                      )}
                      {!isApplied && isSaved && (
                        <Badge variant="blue" className="inline-flex items-center gap-1">
                          <FiBookmark className="w-3 h-3 fill-current" /> Saved
                        </Badge>
                      )}
                    </div>
                    <p className={`text-sm mt-0.5 ${isDisabled ? 'text-slate-400' : 'text-slate-500'}`}>
                      {job.company}
                    </p>
                  </div>
                </div>

                <div className={`flex flex-wrap items-center gap-4 mt-3 text-sm ${isDisabled ? 'text-slate-400' : 'text-slate-500'}`}>
              <span className="flex items-center gap-1.5">
                <FiMapPin className="w-4 h-4 flex-shrink-0" />
                {job.location}
              </span>
              {job.salary && <span>{job.salary}</span>}
              {(job.experienceFrom != null || job.experienceTo != null) && (
                <span className="flex items-center gap-1.5">
                  <FiClock className="w-4 h-4 flex-shrink-0" />
                  {[job.experienceFrom, job.experienceTo].filter(Boolean).join('–')} yrs
                </span>
              )}
            </div>

            {job.postedOn && (
              <div className={`mt-2 text-xs ${isDisabled ? 'text-slate-400' : 'text-slate-500'}`}>
                <span className="flex items-center gap-1.5">
                  <FiClock className="w-3 h-3" />
                  Posted {formatDisplayDate(job.postedOn)}
                </span>
              </div>
            )}

            {skills.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {skills.slice(0, 8).map((skill, i) => (
                  <Badge key={i} variant="secondary" className="text-xs font-medium">
                    {skill}
                  </Badge>
                ))}
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
            {!isAdmin && (
              <Button
                disabled={isDisabled || isApplied}
                onClick={onApply}
                size="sm"
                className={isDisabled || isApplied ? 'opacity-60 cursor-not-allowed' : ''}
              >
                {isApplying ? 'Applying…' : isApplied ? statusConfig.label : 'Apply Now'}
              </Button>
            )}
            {!isAdmin && onToggleSave && !isApplied && (
              <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={onToggleSave}
                className={isSaved ? 'border-blue-200 bg-blue-50 text-blue-600' : ''}
                title={isSaved ? 'Unsave job' : 'Save job'}
              >
                <FiBookmark className={`w-4 h-4 ${isSaved ? 'fill-current' : ''}`} />
              </Button>
            )}
          </div>
        </div>

        {job.description && (
          <p className={`mt-4 text-sm line-clamp-2 ${isDisabled ? 'text-slate-400' : 'text-slate-600'}`}>
            {job.description}
          </p>
        )}
          </CardContent>
        </Card>
      </motion.div>

      <AnimatePresence>
        {showDescriptionModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm"
            onClick={() => setShowDescriptionModal(false)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              transition={{ type: 'tween', duration: 0.2 }}
              className="relative w-full max-w-2xl max-h-[85vh] flex flex-col rounded-2xl bg-white border border-slate-200 shadow-lg overflow-hidden"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex-shrink-0 px-6 pt-6 pb-4 border-b border-slate-200">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="text-xl font-semibold text-slate-900">{job.title}</h3>
                    <p className="text-sm text-slate-500 mt-1">{job.company}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowDescriptionModal(false)}
                    className="p-2 rounded-xl text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
                    aria-label="Close"
                  >
                    <FiX className="w-5 h-5" />
                  </button>
                </div>
                <div className="flex flex-wrap items-center gap-4 mt-3 text-sm text-slate-500">
                  {job.location && (
                    <span className="flex items-center gap-1.5">
                      <FiMapPin className="w-4 h-4" /> {job.location}
                    </span>
                  )}
                  {job.salary && <span>{job.salary}</span>}
                  {(job.experienceFrom != null || job.experienceTo != null) && (
                    <span className="flex items-center gap-1.5">
                      <FiClock className="w-4 h-4" />
                      {[job.experienceFrom, job.experienceTo].filter(Boolean).join('–')} yrs
                    </span>
                  )}
                  {job.postedOn && (
                    <span className="flex items-center gap-1.5">
                      <FiClock className="w-3 h-3" /> Posted {formatDisplayDate(job.postedOn)}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex-1 overflow-y-auto px-6 py-5">
                {skills.length > 0 && (
                  <div className="mb-4">
                    <h4 className="text-sm font-semibold text-slate-700 mb-2">Required skills</h4>
                    <div className="flex flex-wrap gap-1.5">
                      {skills.map((skill, i) => (
                        <Badge key={i} variant="secondary" className="text-xs font-medium">
                          {skill}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
                <JobDescriptionView description={job.description} textClassName="text-slate-600" />
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
