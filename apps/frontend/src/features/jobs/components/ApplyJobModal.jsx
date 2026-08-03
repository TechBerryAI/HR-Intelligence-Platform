import React, { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FiX, FiUser, FiMail, FiPhone, FiMapPin, FiBriefcase, FiLink, FiGlobe } from 'react-icons/fi'
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

function validate(form) {
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
  }
  if (!form.resumeFile && !form.resumeFileName) errors.resume = 'Resume required'
  if (!form._parsedId) errors.resume = errors.resume || 'Please wait for resume AI parsing to finish'
  const eduOk = (form.education || []).some((e) => e.degree?.trim() && e.institution?.trim())
  if (!eduOk) errors.education = 'At least one education entry with degree and institution is required'
  return errors
}

export default function ApplyJobModal({ open, job, onClose, onSuccess }) {
  const [form, setForm] = useState(initialForm)
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')

  useEffect(() => {
    if (open) {
      setForm(initialForm())
      setErrors({})
      setSubmitError('')
      setSubmitting(false)
    }
  }, [open, job?.id])

  useEffect(() => {
    if (!open) return
    const onEsc = (e) => { if (e.key === 'Escape' && !submitting) onClose?.() }
    window.addEventListener('keydown', onEsc)
    return () => window.removeEventListener('keydown', onEsc)
  }, [open, submitting, onClose])

  const setField = (key, value) => setForm((prev) => ({ ...prev, [key]: value }))

  const handleAutofill = (mapped) => {
    setForm((prev) => ({
      ...prev,
      fullName: mapped.fullName || prev.fullName,
      email: mapped.email || prev.email,
      phone: mapped.phone || prev.phone,
      linkedinUrl: mapped.linkedinUrl || prev.linkedinUrl,
      portfolioUrl: mapped.portfolioUrl || prev.portfolioUrl,
      githubUrl: mapped.githubUrl || prev.githubUrl,
      currentLocation: mapped.currentLocation || prev.currentLocation,
      preferredLocation: mapped.preferredLocation || mapped.currentLocation || prev.preferredLocation,
      experienceLevel: mapped.experienceLevel || prev.experienceLevel,
      skills: mapped.skills || (mapped._skills || []).join(', ') || prev.skills,
      summary: mapped.summary || mapped._summary || prev.summary,
      education: mapped.education?.length ? mapped.education : prev.education,
      experiences: mapped.experiences?.length ? mapped.experiences : prev.experiences,
      certifications: mapped.certifications?.length ? mapped.certifications : prev.certifications,
      resumeFile: mapped.resumeFile || prev.resumeFile,
      resumeFileName: mapped.resumeFileName || prev.resumeFileName,
      _parsedId: mapped._parsedId || prev._parsedId,
      _publicUploaderId: mapped._publicUploaderId || prev._publicUploaderId,
    }))
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
    const errs = validate(form)
    setErrors(errs)
    if (Object.keys(errs).length) return

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
      if (form.resumeFile) fd.append('resume', form.resumeFile)

      const res = await fetch(`${BASE_URL}/api/jobs/${encodeURIComponent(job.id)}/apply`, {
        method: 'POST',
        body: fd,
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        throw new Error(data.error || 'Failed to submit application')
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
            className="relative w-full max-w-3xl max-h-[92vh] flex flex-col overflow-hidden rounded-t-2xl sm:rounded-2xl bg-white shadow-xl"
          >
            <div className="shrink-0 flex items-start justify-between gap-4 border-b border-slate-200 bg-white px-5 py-4 z-20">
              <div className="min-w-0">
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Apply for</p>
                <h2 id="apply-job-title" className="text-xl font-semibold text-slate-900 flex items-center gap-2">
                  <FiBriefcase className="text-slate-500 shrink-0" />
                  <span className="truncate">{job.title}</span>
                </h2>
                <p className="text-sm text-slate-500 mt-0.5">{job.company} · {job.location}</p>
              </div>
              <button
                type="button"
                onClick={() => !submitting && onClose?.()}
                className="shrink-0 rounded-lg p-2 text-slate-500 hover:bg-slate-100"
                aria-label="Close apply form"
              >
                <FiX className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="flex-1 min-h-0 overflow-y-auto overscroll-contain px-5 py-5 space-y-6">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Resume (AI autofill)</label>
                <ResumeUploadWithParsing
                  publicMode
                  currentFileName={form.resumeFileName}
                  onFileSelect={(file) => setForm((p) => ({ ...p, resumeFile: file, resumeFileName: file.name }))}
                  onRemove={() => setForm((p) => ({
                    ...p,
                    resumeFile: null,
                    resumeFileName: '',
                    _parsedId: null,
                    _publicUploaderId: null,
                  }))}
                  onAutofill={handleAutofill}
                />
                {errors.resume && <p className="mt-1 text-sm text-red-600">{errors.resume}</p>}
              </div>

              <div className="grid sm:grid-cols-2 gap-4">
                <PremiumInput
                  label="Full name"
                  icon={FiUser}
                  value={form.fullName}
                  onChange={(e) => setField('fullName', e.target.value)}
                  error={errors.fullName}
                />
                <PremiumInput
                  label="Email"
                  icon={FiMail}
                  type="email"
                  value={form.email}
                  onChange={(e) => setField('email', e.target.value)}
                  error={errors.email}
                />
                <PremiumInput
                  label="Phone"
                  icon={FiPhone}
                  value={form.phone}
                  onChange={(e) => setField('phone', e.target.value)}
                  error={errors.phone}
                />
                <PremiumInput
                  label="Current location"
                  icon={FiMapPin}
                  value={form.currentLocation}
                  onChange={(e) => setField('currentLocation', e.target.value)}
                  error={errors.currentLocation}
                />
                <PremiumInput
                  label="Preferred location"
                  icon={FiMapPin}
                  value={form.preferredLocation}
                  onChange={(e) => setField('preferredLocation', e.target.value)}
                  error={errors.preferredLocation}
                />
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
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Experience level</label>
                  <select
                    className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm"
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
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Serving notice</label>
                    <select
                      className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm"
                      value={form.servingNotice}
                      onChange={(e) => setField('servingNotice', e.target.value)}
                    >
                      <option value="">Select</option>
                      <option value="yes">Yes</option>
                      <option value="no">No</option>
                    </select>
                    {errors.servingNotice && <p className="mt-1 text-sm text-red-600">{errors.servingNotice}</p>}
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Serving period</label>
                    <select
                      className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm"
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

              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold text-slate-800">Education</h3>
                  <button type="button" className="text-sm text-accent-blue" onClick={() => addListItem('education', emptyEducation)}>
                    + Add
                  </button>
                </div>
                {errors.education && <p className="mb-2 text-sm text-red-600">{errors.education}</p>}
                <div className="space-y-3">
                  {(form.education || []).map((edu, i) => (
                    <div key={i} className="rounded-xl border border-slate-200 p-3 grid sm:grid-cols-2 gap-3">
                      <PremiumInput label="Degree" value={edu.degree} onChange={(e) => updateList('education', i, 'degree', e.target.value)} />
                      <PremiumInput label="Institution" value={edu.institution} onChange={(e) => updateList('education', i, 'institution', e.target.value)} />
                      <PremiumInput label="CGPA" value={edu.cgpa} onChange={(e) => updateList('education', i, 'cgpa', e.target.value)} />
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">Start</label>
                        <MonthYearPicker value={edu.startMonth} onChange={(v) => updateList('education', i, 'startMonth', v)} />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">End</label>
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
                  <h3 className="text-sm font-semibold text-slate-800">Experience</h3>
                  <button type="button" className="text-sm text-accent-blue" onClick={() => addListItem('experiences', emptyExperience)}>
                    + Add
                  </button>
                </div>
                <div className="space-y-3">
                  {(form.experiences || []).map((exp, i) => (
                    <div key={i} className="rounded-xl border border-slate-200 p-3 grid sm:grid-cols-2 gap-3">
                      <PremiumInput label="Company" value={exp.company} onChange={(e) => updateList('experiences', i, 'company', e.target.value)} />
                      <PremiumInput label="Role" value={exp.role} onChange={(e) => updateList('experiences', i, 'role', e.target.value)} />
                      <label className="flex items-center gap-2 text-sm text-slate-600 sm:col-span-2">
                        <input
                          type="checkbox"
                          checked={!!exp.isCurrent}
                          onChange={(e) => updateList('experiences', i, 'isCurrent', e.target.checked)}
                        />
                        Currently working here
                      </label>
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">Start</label>
                        <MonthYearPicker value={exp.startMonth} onChange={(v) => updateList('experiences', i, 'startMonth', v)} />
                      </div>
                      {exp.isCurrent ? (
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">End</label>
                          <div className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-700">
                            Present
                          </div>
                        </div>
                      ) : (
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">End</label>
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
                  <h3 className="text-sm font-semibold text-slate-800">Certifications</h3>
                  <button type="button" className="text-sm text-accent-blue" onClick={() => addListItem('certifications', emptyCerts)}>
                    + Add
                  </button>
                </div>
                <div className="space-y-3">
                  {(form.certifications || []).map((cert, i) => (
                    <div key={i} className="rounded-xl border border-slate-200 p-3 grid sm:grid-cols-2 gap-3">
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
                <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {submitError}
                </div>
              )}

              <div className="flex flex-col-reverse sm:flex-row gap-3 sm:justify-end pb-2">
                <PremiumButton type="button" variant="secondary" onClick={() => !submitting && onClose?.()} disabled={submitting}>
                  Cancel
                </PremiumButton>
                <PremiumButton type="submit" disabled={submitting}>
                  {submitting ? 'Submitting…' : 'Submit application'}
                </PremiumButton>
              </div>
            </form>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
