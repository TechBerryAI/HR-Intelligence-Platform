import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  FiMapPin,
  FiClock,
  FiCheck,
  FiX,
  FiEye,
  FiAward,
  FiSlash,
  FiArrowRight,
  FiBriefcase,
} from 'react-icons/fi'
import { Badge, Button } from './ui/index.js'
import { extractRequiredSkillsFromDescription } from '@/shared/lib/jobDescription.js'
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

function stripMarkdown(text) {
  if (!text) return ''
  return String(text)
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/#{1,6}\s+/g, '')
    .replace(/\n+/g, ' ')
    .trim()
}

export default function JobCard({
  job,
  onApply,
  isApplied = false,
  applicationStatus = 'applied',
  isAdmin = false,
  isApplying = false,
  matchScore,
}) {
  const isDisabled = job.enabled === false
  const [showDescriptionModal, setShowDescriptionModal] = useState(false)
  const statusConfig = STATUS_BADGES[applicationStatus] || STATUS_BADGES.applied
  const StatusIcon = statusConfig.Icon

  const fromBlock = extractRequiredSkillsFromDescription(job.description || '')
  const rawFallback =
    job.skills ||
    (job.description &&
      job.description.match(
        /\b(React|JavaScript|Python|Node|AWS|SQL|TypeScript|Java|Go|Rust|ExaCC|ExaData|RAC|RMAN|Dataguard|OCI|ASM|Oracle)\b/gi
      )) ||
    []
  const rawSkills = fromBlock.length > 0 ? fromBlock : rawFallback
  const skills = [
    ...new Map(
      rawSkills.map((s) => {
        const key = (typeof s === 'string' ? s : String(s)).trim()
        return [key.toLowerCase(), key]
      })
    ).values(),
  ]

  const experienceLabel = (() => {
    if (job.experienceFrom != null || job.experienceTo != null) {
      return `${[job.experienceFrom, job.experienceTo].filter((v) => v != null && v !== '').join('–')} yrs`
    }
    if (job.experience) return String(job.experience)
    return ''
  })()

  const snippet = stripMarkdown(job.description || '')

  useEffect(() => {
    if (!showDescriptionModal) return
    const onEscape = (e) => {
      if (e.key === 'Escape') setShowDescriptionModal(false)
    }
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
      <motion.article
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        onClick={openModal}
        role="button"
        tabIndex={isDisabled ? -1 : 0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            openModal(e)
          }
        }}
        className={`group relative border-b border-slate-200/80 last:border-b-0 ${
          isDisabled ? 'opacity-50 pointer-events-none' : 'cursor-pointer'
        }`}
      >
        <div className="absolute inset-y-0 left-0 w-0.5 bg-transparent transition-colors group-hover:bg-slate-900" />
        <div className="flex flex-col gap-4 px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:gap-8 sm:px-7 sm:py-6 transition-colors group-hover:bg-slate-50/80">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
              <h3 className="text-[1.05rem] font-semibold tracking-tight text-slate-900 group-hover:text-slate-950">
                {job.title}
              </h3>
              {matchScore != null && (
                <Badge variant="blue" className="text-[11px]">
                  {matchScore}% match
                </Badge>
              )}
              {isApplied && (
                <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700">
                  <StatusIcon className="h-3 w-3" />
                  {statusConfig.label}
                </span>
              )}
            </div>

            <p className="mt-1 text-sm font-medium text-slate-600">{job.company}</p>

            <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[13px] text-slate-500">
              {job.location && (
                <span className="inline-flex items-center gap-1.5">
                  <FiMapPin className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                  {job.location}
                </span>
              )}
              {experienceLabel && (
                <span className="inline-flex items-center gap-1.5">
                  <FiBriefcase className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                  {experienceLabel}
                </span>
              )}
              {job.salary && <span className="text-slate-600">{job.salary}</span>}
              {job.postedOn && (
                <span className="inline-flex items-center gap-1.5">
                  <FiClock className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                  {formatDisplayDate(job.postedOn)}
                </span>
              )}
            </div>

            {snippet && (
              <p className="mt-2.5 max-w-3xl text-[13px] leading-relaxed text-slate-500 line-clamp-1">
                {snippet}
              </p>
            )}

            {skills.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {skills.slice(0, 6).map((skill, i) => (
                  <span
                    key={i}
                    className="rounded-md border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-600"
                  >
                    {skill}
                  </span>
                ))}
                {skills.length > 6 && (
                  <span className="px-1.5 py-0.5 text-[11px] font-medium text-slate-400">
                    +{skills.length - 6}
                  </span>
                )}
              </div>
            )}
          </div>

          <div
            className="flex shrink-0 items-center gap-2 sm:flex-col sm:items-stretch lg:flex-row lg:items-center"
            onClick={(e) => e.stopPropagation()}
          >
            {!isAdmin && (
              <button
                type="button"
                disabled={isDisabled || isApplied || isApplying}
                onClick={onApply}
                className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition ${
                  isApplied || isDisabled
                    ? 'cursor-not-allowed bg-slate-100 text-slate-400'
                    : 'bg-slate-900 text-white hover:bg-slate-800'
                }`}
              >
                {isApplying ? 'Applying…' : isApplied ? statusConfig.label : 'Apply'}
                {!isApplied && !isApplying && <FiArrowRight className="h-4 w-4" />}
              </button>
            )}
          </div>
        </div>
      </motion.article>

      <AnimatePresence>
        {showDescriptionModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm"
            onClick={() => setShowDescriptionModal(false)}
          >
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 12 }}
              transition={{ type: 'tween', duration: 0.2 }}
              className="relative flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex-shrink-0 border-b border-slate-200 px-6 pb-4 pt-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="text-xl font-semibold tracking-tight text-slate-900">{job.title}</h3>
                    <p className="mt-1 text-sm text-slate-500">{job.company}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowDescriptionModal(false)}
                    className="rounded-xl p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
                    aria-label="Close"
                  >
                    <FiX className="h-5 w-5" />
                  </button>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-4 text-sm text-slate-500">
                  {job.location && (
                    <span className="flex items-center gap-1.5">
                      <FiMapPin className="h-4 w-4" /> {job.location}
                    </span>
                  )}
                  {job.salary && <span>{job.salary}</span>}
                  {experienceLabel && (
                    <span className="flex items-center gap-1.5">
                      <FiBriefcase className="h-4 w-4" />
                      {experienceLabel}
                    </span>
                  )}
                  {job.postedOn && (
                    <span className="flex items-center gap-1.5">
                      <FiClock className="h-3.5 w-3.5" /> Posted {formatDisplayDate(job.postedOn)}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex-1 overflow-y-auto px-6 py-5">
                {skills.length > 0 && (
                  <div className="mb-4">
                    <h4 className="mb-2 text-sm font-semibold text-slate-700">Required skills</h4>
                    <div className="flex flex-wrap gap-1.5">
                      {skills.map((skill, i) => (
                        <span
                          key={i}
                          className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-600"
                        >
                          {skill}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                <JobDescriptionView description={job.description} textClassName="text-slate-600" />
              </div>
              {!isAdmin && (
                <div className="flex-shrink-0 border-t border-slate-200 px-6 py-4">
                  <Button
                    disabled={isDisabled || isApplied || isApplying}
                    onClick={() => {
                      setShowDescriptionModal(false)
                      onApply?.()
                    }}
                    className="w-full sm:w-auto"
                  >
                    {isApplying ? 'Applying…' : isApplied ? statusConfig.label : 'Apply for this role'}
                  </Button>
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
