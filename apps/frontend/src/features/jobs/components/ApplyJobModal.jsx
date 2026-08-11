import React, { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FiX, FiUser, FiMail, FiPhone, FiMapPin, FiBriefcase, FiLink, FiGlobe, FiEye } from 'react-icons/fi'
import ResumeUploadWithParsing from '@/shared/components/ResumeUploadWithParsing.jsx'
import MonthYearPicker from '@/shared/components/MonthYearPicker.jsx'
import PremiumInput from '@/shared/components/PremiumInput.jsx'
import PremiumButton from '@/shared/components/PremiumButton.jsx'
import { BASE_URL } from '@/core/api/api.js'

const emptyEducation = () => [{ degree: '', institution: '', cgpa: '', startMonth: '', endMonth: '' }]
const emptyExperience = () => [{ company: '', role: '', startMonth: '', endMonth: '', isCurrent: false, description: '' }]
const emptyCerts = () => [{ name: '', issuer: '', validTill: '', validationUrl: '', status: '' }]

const initialForm = () => ({
  experienceLevel: '',
  servingNotice: '',
  noticePeriod: '',
  lastWorkingDay: '',
  fullName: '',
  email: '',
  phone: '',
  linkedinUrl: '',
  portfolioUrl: '',
  githubUrl: '',
  currentLocation: '',
  preferredLocation: '',
  skills: '',
  summary: '',
  resumeFile: null,
  resumeFileName: '',
  education: emptyEducation(),
  certifications: emptyCerts(),
  experiences: emptyExperience(),
  _parsedId: null,
  _publicUploaderId: null,
})

function validate(form, parseError = '') {
  const errors = {}
  if (!form.fullName?.trim()) errors.fullName = 'Required'
  if (!form.email?.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) errors.email = 'Valid email required'
  if (!form.phone?.trim()) errors.phone = 'Required'
  if (!form.currentLocation?.trim()) errors.currentLocation = 'Required'
  if (!form.preferredLocation?.trim()) errors.preferredLocation = 'Required'
  if (!form.experienceLevel) errors.experienceLevel = 'Required'
  if (form.experienceLevel === 'experienced') {
    if (!form.servingNotice) errors.servingNotice = 'Required'
    if (!form.noticePeriod?.trim()) errors.noticePeriod = 'Required'
    if (form.servingNotice === 'yes' && !form.lastWorkingDay) {
      errors.lastWorkingDay = 'Required'
    }
  }
  if (!form.resumeFile && !form.resumeFileName) {
    errors.resume = parseError || 'Resume required'
  } else if (!form._parsedId) {
    errors.resume = parseError || 'Please wait for resume AI parsing to finish'
  }
  const eduOk = (form.education || []).some((e) => e.degree?.trim() && e.institution?.trim())
  if (!eduOk) errors.education = 'At least one education entry with degree and institution is required'
  return errors
}

/** Top-to-bottom order of required fields in the apply form. */
const APPLY_FIELD_ORDER = [
  'resume',
  'fullName',
  'email',
  'phone',
  'currentLocation',
  'preferredLocation',
  'experienceLevel',
  'servingNotice',
  'noticePeriod',
  'lastWorkingDay',
  'education',
]

const APPLY_FIELD_LABELS = {
  resume: 'Resume',
  fullName: 'Full name',
  email: 'Email',
  phone: 'Phone',
  currentLocation: 'Current location',
  preferredLocation: 'Preferred location',
  experienceLevel: 'Experience level',
  servingNotice: 'Serving notice',
  noticePeriod: 'Serving period',
  lastWorkingDay: 'Last working date',
  education: 'Education',
}

function focusFirstApplyError(errs) {
  const firstKey = APPLY_FIELD_ORDER.find((key) => errs[key])
  if (!firstKey) return
  const el = document.querySelector(`[data-apply-field="${firstKey}"]`)
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  window.setTimeout(() => {
    const focusable = el.querySelector('input:not([type="hidden"]), select, textarea, button, [tabindex]:not([tabindex="-1"])')
    if (focusable && typeof focusable.focus === 'function') {
      focusable.focus({ preventScroll: true })
    }
  }, 280)
}

export default function ApplyJobModal({ open, job, onClose, onSuccess, companySlug }) {
  const [form, setForm] = useState(initialForm)
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const [parseError, setParseError] = useState('')
  const [showPreview, setShowPreview] = useState(false)

  useEffect(() => {
    if (open) {
      setForm(initialForm())
      setErrors({})
      setSubmitError('')
      setParseError('')
      setSubmitting(false)
      setShowPreview(false)
    }
  }, [open, job?.id])

  useEffect(() => {
    if (!open) return
    const onEsc = (e) => {
      if (e.key !== 'Escape' || submitting) return
      if (showPreview) {
        setShowPreview(false)
        return
      }
      onClose?.()
    }
    window.addEventListener('keydown', onEsc)
    return () => window.removeEventListener('keydown', onEsc)
  }, [open, submitting, showPreview, onClose])

  const setField = (key, value) => setForm((prev) => ({ ...prev, [key]: value }))

  const handleAutofill = (mapped) => {
    // Form DTO 1:1 assignment. Preferred location defaults to current only when
    // the DTO left preferred empty (apply form requires both; not invention).
    setForm((prev) => {
      const currentLocation = mapped.currentLocation ?? prev.currentLocation
      const preferredLocation =
        (mapped.preferredLocation && String(mapped.preferredLocation).trim())
          ? mapped.preferredLocation
          : (currentLocation || prev.preferredLocation)
      return {
        ...prev,
        fullName: mapped.fullName ?? prev.fullName,
        email: mapped.email ?? prev.email,
        phone: mapped.phone ?? prev.phone,
        linkedinUrl: mapped.linkedinUrl ?? prev.linkedinUrl,
        portfolioUrl: mapped.portfolioUrl ?? prev.portfolioUrl,
        githubUrl: mapped.githubUrl ?? prev.githubUrl,
        currentLocation,
        preferredLocation,
        experienceLevel: mapped.experienceLevel ?? prev.experienceLevel,
        skills: mapped.skills ?? prev.skills,
        summary: mapped.summary ?? prev.summary,
        education: mapped.education?.length ? mapped.education : prev.education,
        experiences: mapped.experiences?.length ? mapped.experiences : prev.experiences,
        certifications: mapped.certifications?.length ? mapped.certifications : prev.certifications,
        resumeFile: mapped.resumeFile || prev.resumeFile,
        resumeFileName: mapped.resumeFileName || prev.resumeFileName,
        _parsedId: mapped._parsedId || prev._parsedId,
        _publicUploaderId: mapped._publicUploaderId || prev._publicUploaderId,
      }
    })
    setErrors((prev) => {
      const next = { ...prev }
      delete next.resume
      return next
    })
  }

  const updateList = (key, index, field, value) => {
    setForm((prev) => {
      const list = [...(prev[key] || [])]
      const next = { ...list[index], [field]: value }
      // Currently working: keep Start, set End to current month, hide End picker
      if (key === 'experiences' && field === 'isCurrent') {
        if (value) {
          const now = new Date()
          const yyyy = now.getFullYear()
          const mm = String(now.getMonth() + 1).padStart(2, '0')
          next.endMonth = `${yyyy}-${mm}`
        } else {
          next.endMonth = ''
        }
      }
      list[index] = next
      return { ...prev, [key]: list }
    })
  }

  const addListItem = (key, emptyFn) => {
    setForm((prev) => ({ ...prev, [key]: [...(prev[key] || []), ...emptyFn()] }))
  }

  const removeListItem = (key, index, emptyFn) => {
    setForm((prev) => {
      const list = (prev[key] || []).filter((_, i) => i !== index)
      return { ...prev, [key]: list.length ? list : emptyFn() }
    })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitError('')
    const errs = validate(form, parseError)
    setErrors(errs)
    if (Object.keys(errs).length) {
      const missing = APPLY_FIELD_ORDER.filter((k) => errs[k]).map((k) => APPLY_FIELD_LABELS[k] || k)
      setSubmitError(
        missing.length
          ? `Please complete required fields: ${missing.join(', ')}.`
          : 'Please complete all required fields.'
      )
      requestAnimationFrame(() => focusFirstApplyError(errs))
      return
    }

    setSubmitting(true)
    try {
      const fd = new FormData()
      fd.append('fullName', form.fullName.trim())
      fd.append('email', form.email.trim())
      fd.append('phone', form.phone.trim())
      fd.append('linkedinUrl', form.linkedinUrl || '')
      fd.append('portfolioUrl', form.portfolioUrl || '')
      fd.append('githubUrl', form.githubUrl || '')
      fd.append('currentLocation', form.currentLocation.trim())
      fd.append('preferredLocation', form.preferredLocation.trim())
      fd.append('experienceLevel', form.experienceLevel)
      fd.append('skills', form.skills || '')
      fd.append('summary', form.summary || '')
      fd.append('servingNotice', form.servingNotice || '')
      fd.append('noticePeriod', form.noticePeriod || '')
      fd.append('lastWorkingDay', form.lastWorkingDay || '')
      fd.append('education', JSON.stringify(form.education || []))
      fd.append('experiences', JSON.stringify(form.experiences || []))
      fd.append('certifications', JSON.stringify(form.certifications || []))
      if (form._parsedId) fd.append('parsedId', form._parsedId)
      if (form._publicUploaderId) fd.append('publicUploaderId', form._publicUploaderId)
      // Resume was already stored during AI parse — re-uploading the PDF only slows submit.
      if (!form._parsedId && form.resumeFile) fd.append('resume', form.resumeFile)

      const applyQs = companySlug
        ? `?company=${encodeURIComponent(companySlug)}`
        : ''
      // Submit is deterministic ATS only — keep a hard client timeout so the UI never hangs.
      const applyTimeoutMs = Number(import.meta.env?.VITE_API_TIMEOUT_MS) || 30000
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), applyTimeoutMs)
      let res
      try {
        res = await fetch(
          `${BASE_URL}/api/jobs/${encodeURIComponent(job.id || job.jdid)}/apply${applyQs}`,
          {
            method: 'POST',
            body: fd,
            signal: controller.signal,
          },
        )
      } catch (fetchErr) {
        if (fetchErr?.name === 'AbortError') {
          throw new Error('Submit timed out. Please try again — parsing is already done; submit should be quick.')
        }
        throw fetchErr
      } finally {
        clearTimeout(timeoutId)
      }
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        const raw = String(data.error || '')
        if (/already applied/i.test(raw)) {
          throw new Error('Applicant already applied')
        }
        throw new Error(raw || 'Failed to submit application')
      }
      onSuccess?.(data)
      onClose?.()
    } catch (err) {
      setSubmitError(err.message || 'Failed to submit application')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AnimatePresence>
      {open && job && (
        <motion.div
          className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center p-0 sm:p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <button
            type="button"
            aria-label="Close"
            className="absolute inset-0 bg-slate-900/50"
            onClick={() => !submitting && onClose?.()}
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="apply-job-title"
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 40, opacity: 0 }}
            className="apply-modal relative w-full max-w-3xl max-h-[92vh] flex flex-col overflow-hidden rounded-t-2xl sm:rounded-2xl border border-[var(--ei-border-primary)] bg-[var(--ei-bg-secondary)] shadow-xl"
          >
            <div className="shrink-0 flex items-start justify-between gap-4 border-b border-[var(--ei-border-primary)] bg-[var(--ei-bg-secondary)] px-5 py-4 z-20">
              <div className="min-w-0">
                <p className="text-xs font-medium uppercase tracking-wide text-[var(--ei-text-muted)]">Apply for</p>
                <h2 id="apply-job-title" className="text-xl font-semibold text-[var(--ei-text-primary)] flex items-center gap-2">
                  <FiBriefcase className="text-[var(--ei-text-muted)] shrink-0" />
                  <span className="truncate text-[var(--ei-text-primary)]">{job.title}</span>
                </h2>
                <p className="text-sm text-[var(--ei-text-muted)] mt-0.5">{job.company} · {job.location}</p>
              </div>
              <button
                type="button"
                onClick={() => !submitting && onClose?.()}
                className="shrink-0 rounded-lg p-2 text-[var(--ei-text-muted)] hover:bg-[var(--ei-surface-hover)] hover:text-[var(--ei-text-primary)]"
                aria-label="Close apply form"
              >
                <FiX className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="flex-1 min-h-0 overflow-y-auto overscroll-contain px-5 py-5 space-y-6">
              <div data-apply-field="resume">
                <label className="block text-sm font-medium text-[var(--ei-text-label)] mb-2">
                  Resume (AI autofill) <span className="text-[#FF6B81]">*</span>
                </label>
                <ResumeUploadWithParsing
                  publicMode
                  currentFileName={form.resumeFileName}
                  onFileSelect={(file) => {
                    setParseError('')
                    setForm((p) => ({ ...p, resumeFile: file, resumeFileName: file.name, _parsedId: null }))
                  }}
                  onRemove={() => setForm((p) => ({
                    ...p,
                    resumeFile: null,
                    resumeFileName: '',
                    _parsedId: null,
                    _publicUploaderId: null,
                  }))}
                  onParseError={(message) => setParseError(message || '')}
                  onAutofill={handleAutofill}
                />
                {errors.resume && !parseError && <p className="mt-1 text-sm text-red-600">{errors.resume}</p>}
              </div>

              <div className="grid sm:grid-cols-2 gap-4">
                <div data-apply-field="fullName">
                  <PremiumInput
                    label="Full name"
                    icon={FiUser}
                    value={form.fullName}
                    onChange={(e) => setField('fullName', e.target.value)}
                    error={errors.fullName}
                    required
                  />
                </div>
                <div data-apply-field="email">
                  <PremiumInput
                    label="Email"
                    icon={FiMail}
                    type="email"
                    value={form.email}
                    onChange={(e) => setField('email', e.target.value)}
                    error={errors.email}
                    required
                  />
                </div>
                <div data-apply-field="phone">
                  <PremiumInput
                    label="Phone"
                    icon={FiPhone}
                    value={form.phone}
                    onChange={(e) => setField('phone', e.target.value)}
                    error={errors.phone}
                    required
                  />
                </div>
                <div data-apply-field="currentLocation">
                  <PremiumInput
                    label="Current location"
                    icon={FiMapPin}
                    value={form.currentLocation}
                    onChange={(e) => setField('currentLocation', e.target.value)}
                    error={errors.currentLocation}
                    required
                  />
                </div>
                <div data-apply-field="preferredLocation">
                  <PremiumInput
                    label="Preferred location"
                    icon={FiMapPin}
                    value={form.preferredLocation}
                    onChange={(e) => setField('preferredLocation', e.target.value)}
                    error={errors.preferredLocation}
                    required
                  />
                </div>
                <PremiumInput
                  label="LinkedIn URL"
                  icon={FiLink}
                  value={form.linkedinUrl}
                  onChange={(e) => setField('linkedinUrl', e.target.value)}
                />
                <PremiumInput
                  label="Portfolio"
                  icon={FiGlobe}
                  value={form.portfolioUrl}
                  onChange={(e) => setField('portfolioUrl', e.target.value)}
                />
                <PremiumInput
                  label="GitHub URL"
                  icon={FiGlobe}
                  value={form.githubUrl || ''}
                  onChange={(e) => setField('githubUrl', e.target.value)}
                />
                <div data-apply-field="experienceLevel">
                  <label className="block text-sm font-medium text-[var(--ei-text-label)] mb-1">
                    Experience level <span className="text-[#FF6B81]">*</span>
                  </label>
                  <select
                    className={`premium-input w-full text-sm ${errors.experienceLevel ? 'border-red-500' : ''}`}
                    value={form.experienceLevel}
                    onChange={(e) => setField('experienceLevel', e.target.value)}
                  >
                    <option value="">Select</option>
                    <option value="fresher">Fresher</option>
                    <option value="experienced">Experienced</option>
                  </select>
                  {errors.experienceLevel && <p className="mt-1 text-sm text-red-600">{errors.experienceLevel}</p>}
                </div>
              </div>

              {form.experienceLevel === 'experienced' && (
                <div className="grid sm:grid-cols-2 gap-4">
                  <div data-apply-field="servingNotice">
                    <label className="block text-sm font-medium text-[var(--ei-text-label)] mb-1">
                      Serving notice <span className="text-[#FF6B81]">*</span>
                    </label>
                    <select
                      className={`premium-input w-full text-sm ${errors.servingNotice ? 'border-red-500' : ''}`}
                      value={form.servingNotice}
                      onChange={(e) => {
                        const v = e.target.value
                        setForm((prev) => ({
                          ...prev,
                          servingNotice: v,
                          lastWorkingDay: v === 'yes' ? prev.lastWorkingDay : '',
                        }))
                      }}
                    >
                      <option value="">Select</option>
                      <option value="yes">Yes</option>
                      <option value="no">No</option>
                    </select>
                    {errors.servingNotice && <p className="mt-1 text-sm text-red-600">{errors.servingNotice}</p>}
                  </div>
                  <div data-apply-field="noticePeriod">
                    <label className="block text-sm font-medium text-[var(--ei-text-label)] mb-1">
                      Serving period <span className="text-[#FF6B81]">*</span>
                    </label>
                    <select
                      className={`premium-input w-full text-sm ${errors.noticePeriod ? 'border-red-500' : ''}`}
                      value={form.noticePeriod}
                      onChange={(e) => setField('noticePeriod', e.target.value)}
                    >
                      <option value="">Select</option>
                      <option value="<30 days">&lt;30 days</option>
                      <option value="<60 days">&lt;60 days</option>
                      <option value="<90 days">&lt;90 days</option>
                    </select>
                    {errors.noticePeriod && <p className="mt-1 text-sm text-red-600">{errors.noticePeriod}</p>}
                  </div>
                  {form.servingNotice === 'yes' && (
                    <div className="sm:col-span-2" data-apply-field="lastWorkingDay">
                      <label className="block text-sm font-medium text-[var(--ei-text-label)] mb-1">
                        Last working date <span className="text-[#FF6B81]">*</span>
                      </label>
                      <input
                        type="date"
                        className={`premium-input w-full text-sm text-[var(--ei-text-primary)] ${errors.lastWorkingDay ? 'border-red-500' : ''}`}
                        value={form.lastWorkingDay || ''}
                        onChange={(e) => setField('lastWorkingDay', e.target.value)}
                      />
                      {errors.lastWorkingDay && <p className="mt-1 text-sm text-red-600">{errors.lastWorkingDay}</p>}
                    </div>
                  )}
                </div>
              )}

              <PremiumInput
                label="Skills (comma-separated)"
                value={form.skills}
                onChange={(e) => setField('skills', e.target.value)}
                placeholder="Python, React, SQL"
              />

              <PremiumInput
                label="Professional summary"
                as="textarea"
                value={form.summary || ''}
                onChange={(e) => setField('summary', e.target.value)}
                placeholder="Short professional summary from resume"
                className="min-h-[80px] resize-y"
              />

              <div data-apply-field="education">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold text-[var(--ei-text-primary)]">
                    Education <span className="text-[#FF6B81]">*</span>
                  </h3>
                  <button type="button" className="text-sm text-accent-blue" onClick={() => addListItem('education', emptyEducation)}>
                    + Add
                  </button>
                </div>
                {errors.education && <p className="mb-2 text-sm text-red-600">{errors.education}</p>}
                <div className="space-y-3">
                  {(form.education || []).map((edu, i) => (
                    <div key={i} className="rounded-xl border border-[var(--ei-border-primary)] p-3 grid sm:grid-cols-2 gap-3">
                      <PremiumInput label="Degree" value={edu.degree} onChange={(e) => updateList('education', i, 'degree', e.target.value)} />
                      <PremiumInput label="Institution" value={edu.institution} onChange={(e) => updateList('education', i, 'institution', e.target.value)} />
                      <PremiumInput label="CGPA" value={edu.cgpa} onChange={(e) => updateList('education', i, 'cgpa', e.target.value)} />
                      <div>
                        <label className="block text-sm font-medium text-[var(--ei-text-label)] mb-1">Start</label>
                        <MonthYearPicker value={edu.startMonth} onChange={(v) => updateList('education', i, 'startMonth', v)} />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-[var(--ei-text-label)] mb-1">End</label>
                        <MonthYearPicker value={edu.endMonth} onChange={(v) => updateList('education', i, 'endMonth', v)} />
                      </div>
                      {(form.education || []).length > 1 && (
                        <button type="button" className="text-sm text-red-600 sm:col-span-2 text-left" onClick={() => removeListItem('education', i, emptyEducation)}>
                          Remove
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold text-[var(--ei-text-primary)]">Experience</h3>
                  <button type="button" className="text-sm text-accent-blue" onClick={() => addListItem('experiences', emptyExperience)}>
                    + Add
                  </button>
                </div>
                <div className="space-y-3">
                  {(form.experiences || []).map((exp, i) => (
                    <div key={i} className="rounded-xl border border-[var(--ei-border-primary)] p-3 grid sm:grid-cols-2 gap-3">
                      <PremiumInput label="Company" value={exp.company} onChange={(e) => updateList('experiences', i, 'company', e.target.value)} />
                      <PremiumInput label="Role" value={exp.role} onChange={(e) => updateList('experiences', i, 'role', e.target.value)} />
                      <label className="flex items-center gap-2 text-sm text-[var(--ei-text-secondary)] sm:col-span-2">
                        <input
                          type="checkbox"
                          checked={!!exp.isCurrent}
                          onChange={(e) => updateList('experiences', i, 'isCurrent', e.target.checked)}
                        />
                        Currently working here
                      </label>
                      <div>
                        <label className="block text-sm font-medium text-[var(--ei-text-label)] mb-1">Start</label>
                        <MonthYearPicker value={exp.startMonth} onChange={(v) => updateList('experiences', i, 'startMonth', v)} />
                      </div>
                      {exp.isCurrent ? (
                        <div>
                          <label className="block text-sm font-medium text-[var(--ei-text-label)] mb-1">End</label>
                          <div className="w-full rounded-xl border border-[var(--ei-border-primary)] bg-[var(--ei-surface-input)] px-3 py-2.5 text-sm text-[var(--ei-text-secondary)]">
                            Present
                          </div>
                        </div>
                      ) : (
                        <div>
                          <label className="block text-sm font-medium text-[var(--ei-text-label)] mb-1">End</label>
                          <MonthYearPicker value={exp.endMonth} onChange={(v) => updateList('experiences', i, 'endMonth', v)} />
                        </div>
                      )}
                      <div className="sm:col-span-2">
                        <PremiumInput
                          label="Description"
                          value={exp.description || ''}
                          onChange={(e) => updateList('experiences', i, 'description', e.target.value)}
                        />
                      </div>
                      {(form.experiences || []).length > 1 && (
                        <button type="button" className="text-sm text-red-600 sm:col-span-2 text-left" onClick={() => removeListItem('experiences', i, emptyExperience)}>
                          Remove
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold text-[var(--ei-text-primary)]">Certifications</h3>
                  <button type="button" className="text-sm text-accent-blue" onClick={() => addListItem('certifications', emptyCerts)}>
                    + Add
                  </button>
                </div>
                <div className="space-y-3">
                  {(form.certifications || []).map((cert, i) => (
                    <div key={i} className="rounded-xl border border-[var(--ei-border-primary)] p-3 grid sm:grid-cols-2 gap-3">
                      <PremiumInput label="Name" value={cert.name} onChange={(e) => updateList('certifications', i, 'name', e.target.value)} />
                      <PremiumInput label="Issuer" value={cert.issuer} onChange={(e) => updateList('certifications', i, 'issuer', e.target.value)} />
                      <PremiumInput label="Valid till" value={cert.validTill} onChange={(e) => updateList('certifications', i, 'validTill', e.target.value)} />
                      <PremiumInput label="Validation URL" value={cert.validationUrl} onChange={(e) => updateList('certifications', i, 'validationUrl', e.target.value)} />
                      {(form.certifications || []).length > 1 && (
                        <button type="button" className="text-sm text-red-600 sm:col-span-2 text-left" onClick={() => removeListItem('certifications', i, emptyCerts)}>
                          Remove
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {submitError && (
                <div className="rounded-xl border border-[var(--ei-tone-danger-border)] bg-[var(--ei-tone-danger-bg)] px-4 py-3 text-sm text-[var(--ei-tone-danger)]">
                  {submitError}
                </div>
              )}

              <div className="flex flex-col-reverse sm:flex-row gap-3 sm:justify-end pb-2">
                <PremiumButton type="button" variant="secondary" onClick={() => !submitting && onClose?.()} disabled={submitting}>
                  Cancel
                </PremiumButton>
                <PremiumButton
                  type="button"
                  variant="primary"
                  icon={FiEye}
                  onClick={() => setShowPreview(true)}
                  disabled={submitting}
                >
                  Preview
                </PremiumButton>
                <PremiumButton type="submit" disabled={submitting}>
                  {submitting ? 'Submitting…' : 'Submit application'}
                </PremiumButton>
              </div>
            </form>
          </motion.div>
        </motion.div>
      )}

      {showPreview && open && job && (
        <motion.div
          key="apply-preview"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[110] flex items-center justify-center p-4"
        >
          <div
            className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm"
            onClick={() => setShowPreview(false)}
          />
          <motion.div
            initial={{ scale: 0.96, opacity: 0, y: 10 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.96, opacity: 0, y: 10 }}
            className="apply-modal relative flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-[var(--ei-border-primary)] bg-[var(--ei-bg-secondary)] shadow-xl"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="apply-preview-title"
          >
            <div className="flex-shrink-0 border-b border-[var(--ei-border-primary)] px-6 pb-4 pt-5">
              <div className="mb-3 flex items-center justify-between gap-3">
                <span className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--ei-tone-info-bg)] px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-[var(--ei-tone-info)] border border-[var(--ei-tone-info-border)]">
                  <FiEye className="h-3.5 w-3.5" />
                  Application preview
                </span>
                <button
                  type="button"
                  onClick={() => setShowPreview(false)}
                  className="rounded-xl p-2 text-[var(--ei-text-muted)] transition-colors hover:bg-[var(--ei-surface-hover)] hover:text-[var(--ei-text-primary)]"
                  aria-label="Close preview"
                >
                  <FiX className="h-5 w-5" />
                </button>
              </div>
              <h3 id="apply-preview-title" className="text-xl font-semibold tracking-tight text-[var(--ei-text-primary)]">
                {form.fullName.trim() || 'Applicant'}
              </h3>
              <p className="mt-1 text-sm text-[var(--ei-text-muted)]">
                Applying for {job.title} · {job.company}
                {job.location ? ` · ${job.location}` : ''}
              </p>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5 text-sm">
              <PreviewSection title="Contact">
                <PreviewRow label="Full name" value={form.fullName} />
                <PreviewRow label="Email" value={form.email} />
                <PreviewRow label="Phone" value={form.phone} />
                <PreviewRow label="Current location" value={form.currentLocation} />
                <PreviewRow label="Preferred location" value={form.preferredLocation} />
                <PreviewRow label="LinkedIn URL" value={form.linkedinUrl} />
                <PreviewRow label="Portfolio" value={form.portfolioUrl} />
                <PreviewRow label="GitHub URL" value={form.githubUrl} />
              </PreviewSection>

              <PreviewSection title="Application details">
                <PreviewRow
                  label="Experience level"
                  value={
                    form.experienceLevel === 'fresher'
                      ? 'Fresher'
                      : form.experienceLevel === 'experienced'
                        ? 'Experienced'
                        : form.experienceLevel
                  }
                />
                <PreviewRow
                  label="Serving notice"
                  value={
                    form.servingNotice === 'yes'
                      ? 'Yes'
                      : form.servingNotice === 'no'
                        ? 'No'
                        : form.servingNotice
                  }
                />
                <PreviewRow label="Serving period" value={form.noticePeriod} />
                <PreviewRow label="Last working date" value={form.lastWorkingDay} />
                <PreviewRow
                  label="Resume"
                  value={form.resumeFileName || form.resumeFile?.name || ''}
                />
              </PreviewSection>

              <PreviewSection title="Professional summary">
                {(form.summary || '').trim() ? (
                  <p className="text-[var(--ei-text-label)] whitespace-pre-wrap">{form.summary.trim()}</p>
                ) : (
                  <p className="text-[var(--ei-text-muted)]">Not provided</p>
                )}
              </PreviewSection>

              <PreviewSection title="Skills">
                {(form.skills || '').trim() ? (
                  <div className="flex flex-wrap gap-1.5">
                    {form.skills.split(',').map((s) => s.trim()).filter(Boolean).map((skill) => (
                      <span
                        key={skill}
                        className="rounded-md border border-[var(--ei-border-primary)] bg-[var(--ei-surface-hover)] px-2 py-0.5 text-xs font-medium text-[var(--ei-text-primary)]"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-[var(--ei-text-muted)]">Not provided</p>
                )}
              </PreviewSection>

              <PreviewSection title="Education">
                {(() => {
                  const rows = (form.education || []).filter((e) =>
                    [e.degree, e.institution, e.cgpa, e.startMonth, e.endMonth].some((v) => String(v || '').trim())
                  )
                  if (!rows.length) return <p className="text-[var(--ei-text-muted)]">Not provided</p>
                  return (
                    <ul className="space-y-3">
                      {rows.map((edu, i) => (
                        <li key={i} className="rounded-lg border border-[var(--ei-border-primary)] bg-[var(--ei-surface-input)] px-3 py-2.5 space-y-1">
                          <PreviewRow label="Degree" value={edu.degree} />
                          <PreviewRow label="Institution" value={edu.institution} />
                          <PreviewRow label="CGPA" value={edu.cgpa} />
                          <PreviewRow label="Start" value={edu.startMonth} />
                          <PreviewRow label="End" value={edu.endMonth} />
                        </li>
                      ))}
                    </ul>
                  )
                })()}
              </PreviewSection>

              <PreviewSection title="Work experience">
                {(() => {
                  const rows = (form.experiences || []).filter((e) =>
                    [e.company, e.role, e.startMonth, e.endMonth, e.description].some((v) => String(v || '').trim())
                    || e.isCurrent
                  )
                  if (!rows.length) return <p className="text-[var(--ei-text-muted)]">Not provided</p>
                  return (
                    <ul className="space-y-3">
                      {rows.map((exp, i) => (
                        <li key={i} className="rounded-lg border border-[var(--ei-border-primary)] bg-[var(--ei-surface-input)] px-3 py-2.5 space-y-1">
                          <PreviewRow label="Company" value={exp.company} />
                          <PreviewRow label="Role" value={exp.role} />
                          <PreviewRow
                            label="Currently working"
                            value={exp.isCurrent ? 'Yes' : (exp.company || exp.role ? 'No' : '')}
                          />
                          <PreviewRow label="Start" value={exp.startMonth} />
                          <PreviewRow
                            label="End"
                            value={exp.isCurrent ? 'Present' : exp.endMonth}
                          />
                          {exp.description?.trim() ? (
                            <div className="pt-1">
                              <p className="text-[var(--ei-text-muted)] mb-0.5">Description</p>
                              <p className="text-[var(--ei-text-label)] whitespace-pre-wrap">{exp.description.trim()}</p>
                            </div>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  )
                })()}
              </PreviewSection>

              <PreviewSection title="Certifications">
                {(() => {
                  const rows = (form.certifications || []).filter((c) =>
                    [c.name, c.issuer, c.validTill, c.validationUrl, c.status].some((v) => String(v || '').trim())
                  )
                  if (!rows.length) return <p className="text-[var(--ei-text-muted)]">Not provided</p>
                  return (
                    <ul className="space-y-3">
                      {rows.map((cert, i) => (
                        <li key={i} className="rounded-lg border border-[var(--ei-border-primary)] bg-[var(--ei-surface-input)] px-3 py-2.5 space-y-1">
                          <PreviewRow label="Name" value={cert.name} />
                          <PreviewRow label="Issuer" value={cert.issuer} />
                          <PreviewRow label="Valid till" value={cert.validTill} />
                          <PreviewRow label="Validation URL" value={cert.validationUrl} />
                          <PreviewRow label="Status" value={cert.status} />
                        </li>
                      ))}
                    </ul>
                  )
                })()}
              </PreviewSection>
            </div>

            <div className="flex-shrink-0 border-t border-[var(--ei-border-primary)] px-6 py-4 flex flex-col sm:flex-row gap-3 sm:justify-end">
              <PremiumButton
                type="button"
                variant="secondary"
                onClick={() => setShowPreview(false)}
                className="sm:min-w-[120px]"
              >
                Close
              </PremiumButton>
              <PremiumButton
                type="button"
                variant="primary"
                disabled={submitting}
                onClick={() => {
                  setShowPreview(false)
                  const formEl = document.querySelector('.apply-modal form')
                  formEl?.requestSubmit()
                }}
                className="sm:min-w-[160px]"
              >
                {submitting ? 'Submitting…' : 'Submit application'}
              </PremiumButton>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function PreviewSection({ title, children }) {
  return (
    <div>
      <h4 className="mb-2 text-sm font-semibold text-[var(--ei-text-label)]">{title}</h4>
      {children}
    </div>
  )
}

function PreviewRow({ label, value }) {
  const text = (value || '').toString().trim()
  if (!text) return null
  return (
    <div className="flex flex-col sm:flex-row sm:gap-3 py-0.5">
      <span className="sm:w-40 shrink-0 text-[var(--ei-text-muted)]">{label}</span>
      <span className="text-[var(--ei-text-primary)] break-all">{text}</span>
    </div>
  )
}
