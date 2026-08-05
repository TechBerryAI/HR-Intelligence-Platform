/**
 * Validation-only harness: production ResumeUploadWithParsing + ApplyJobModal autofill path.
 * Enabled when VITE_VALIDATION_HARNESS=true. Exposes window.__RESUME_VALIDATION__.
 */
import React, { useCallback, useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { FiUser, FiMail, FiPhone, FiMapPin, FiLink, FiGlobe, FiBriefcase } from 'react-icons/fi'
import ResumeUploadWithParsing from '@/shared/components/ResumeUploadWithParsing.jsx'
import MonthYearPicker from '@/shared/components/MonthYearPicker.jsx'
import PremiumInput from '@/shared/components/PremiumInput.jsx'

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

/** Same AI-owned rules as ApplyJobModal.validate (excludes user-only notice fields). */
export function validateAiOwnedFields(form) {
  const errors = {}
  if (!form.fullName?.trim()) errors.fullName = 'Required'
  if (!form.email?.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) errors.email = 'Valid email required'
  if (!form.phone?.trim()) errors.phone = 'Required'
  if (!form.currentLocation?.trim()) errors.currentLocation = 'Required'
  if (!form.preferredLocation?.trim()) errors.preferredLocation = 'Required'
  if (!form.experienceLevel) errors.experienceLevel = 'Required'
  if (!form.resumeFile && !form.resumeFileName) errors.resume = 'Resume required'
  if (!form._parsedId) errors.resume = errors.resume || 'Please wait for resume AI parsing to finish'
  const eduOk = (form.education || []).some((e) => e.degree?.trim() && e.institution?.trim())
  if (!eduOk) errors.education = 'At least one education entry with degree and institution is required'
  return errors
}

function serializableForm(form) {
  const { resumeFile, ...rest } = form
  return {
    ...rest,
    resumeFile: resumeFile ? { name: resumeFile.name, size: resumeFile.size, type: resumeFile.type } : null,
  }
}

const HARNESS_ENABLED = String(import.meta.env.VITE_VALIDATION_HARNESS || '').toLowerCase() === 'true'

export default function ResumeAutofillHarness() {
  const [form, setForm] = useState(initialForm)
  const [errors, setErrors] = useState({})
  const [uploadKey, setUploadKey] = useState(0)
  const [status, setStatus] = useState('idle')
  const [parsePayload, setParsePayload] = useState(null)
  const [parseError, setParseError] = useState(null)
  const [startedAt, setStartedAt] = useState(null)
  const [finishedAt, setFinishedAt] = useState(null)
  const [stages, setStages] = useState([])

  const publish = useCallback((overrides = {}) => {
    if (!HARNESS_ENABLED) return null
    const nextErrors = overrides.errors ?? errors
    const nextForm = overrides.form ?? form
    const nextStatus = overrides.status ?? status
    const payload = {
      status: nextStatus,
      form: serializableForm(nextForm),
      parsePayload: overrides.parsePayload !== undefined ? overrides.parsePayload : parsePayload,
      parseError: overrides.parseError !== undefined ? overrides.parseError : parseError,
      errors: nextErrors,
      stages: overrides.stages ?? stages,
      startedAt: overrides.startedAt ?? startedAt,
      finishedAt: overrides.finishedAt ?? finishedAt,
      elapsedMs:
        (overrides.finishedAt ?? finishedAt) && (overrides.startedAt ?? startedAt)
          ? (overrides.finishedAt ?? finishedAt) - (overrides.startedAt ?? startedAt)
          : null,
      reset: () => {
        window.__RESUME_VALIDATION_RESET__?.()
      },
    }
    window.__RESUME_VALIDATION__ = payload
    return payload
  }, [errors, form, status, parsePayload, parseError, stages, startedAt, finishedAt])

  useEffect(() => {
    if (!HARNESS_ENABLED) return
    publish()
  }, [publish])

  useEffect(() => {
    if (!HARNESS_ENABLED) return
    window.__RESUME_VALIDATION_RESET__ = () => {
      setForm(initialForm())
      setErrors({})
      setStatus('idle')
      setParsePayload(null)
      setParseError(null)
      setStartedAt(null)
      setFinishedAt(null)
      setStages([])
      setUploadKey((k) => k + 1)
      window.__RESUME_VALIDATION__ = {
        status: 'idle',
        form: serializableForm(initialForm()),
        parsePayload: null,
        parseError: null,
        errors: {},
        stages: [],
        startedAt: null,
        finishedAt: null,
        elapsedMs: null,
      }
    }
    return () => {
      delete window.__RESUME_VALIDATION_RESET__
    }
  }, [])

  if (!HARNESS_ENABLED) {
    return <Navigate to="/" replace />
  }

  const setField = (key, value) => setForm((prev) => ({ ...prev, [key]: value }))

  const handleAutofill = (mapped) => {
    setForm((prev) => {
      const currentLocation = mapped.currentLocation ?? prev.currentLocation
      const preferredLocation =
        (mapped.preferredLocation && String(mapped.preferredLocation).trim())
          ? mapped.preferredLocation
          : (currentLocation || prev.preferredLocation)
      const next = {
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
      const nextErrors = validateAiOwnedFields(next)
      const doneAt = Date.now()
      setErrors(nextErrors)
      setStatus('complete')
      setFinishedAt(doneAt)
      queueMicrotask(() => {
        publish({
          form: next,
          errors: nextErrors,
          status: 'complete',
          finishedAt: doneAt,
        })
      })
      return next
    })
  }

  const updateList = (key, index, field, value) => {
    setForm((prev) => {
      const list = [...(prev[key] || [])]
      const next = { ...list[index], [field]: value }
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

  return (
    <div className="min-h-screen bg-slate-100 py-8 px-4">
      <div className="mx-auto max-w-3xl">
        <div className="mb-4 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Resume Autofill Validation Harness — production parse path only.
          Status: <strong data-testid="validation-status">{status}</strong>
        </div>

        <div
          id="autofill-form"
          className="rounded-2xl bg-white shadow-xl border border-slate-200 overflow-hidden"
        >
          <div className="border-b border-slate-200 px-5 py-4">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Validation apply form</p>
            <h1 className="text-xl font-semibold text-slate-900 flex items-center gap-2">
              <FiBriefcase className="text-slate-500" />
              Resume Intelligence E2E
            </h1>
          </div>

          <div className="px-5 py-5 space-y-6">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Resume (AI autofill)</label>
              <ResumeUploadWithParsing
                key={uploadKey}
                publicMode
                currentFileName={form.resumeFileName}
                onFileSelect={(file) => {
                  const t0 = Date.now()
                  setStartedAt(t0)
                  setFinishedAt(null)
                  setStatus('uploading')
                  setParseError(null)
                  setParsePayload(null)
                  setStages([])
                  setForm((p) => ({ ...p, resumeFile: file, resumeFileName: file.name }))
                  publish({ status: 'uploading', startedAt: t0, finishedAt: null, parseError: null, parsePayload: null })
                }}
                onParseComplete={(result, err) => {
                  if (err && !result) {
                    const doneAt = Date.now()
                    setParseError(err)
                    setStatus('error')
                    setFinishedAt(doneAt)
                    publish({ status: 'error', parseError: err, finishedAt: doneAt })
                    return
                  }
                  setParsePayload(result)
                  publish({ parsePayload: result, parseError: err || null })
                }}
                onRemove={() => {
                  setForm((p) => ({
                    ...p,
                    resumeFile: null,
                    resumeFileName: '',
                    _parsedId: null,
                    _publicUploaderId: null,
                  }))
                  setStatus('idle')
                  setParsePayload(null)
                  setParseError(null)
                }}
                onAutofill={handleAutofill}
              />
              {errors.resume && <p className="mt-1 text-sm text-red-600">{errors.resume}</p>}
              {parseError && <p className="mt-1 text-sm text-amber-700" data-testid="parse-error">{parseError}</p>}
            </div>

            <div className="grid sm:grid-cols-2 gap-4">
              <PremiumInput label="Full name" icon={FiUser} value={form.fullName} onChange={(e) => setField('fullName', e.target.value)} error={errors.fullName} />
              <PremiumInput label="Email" icon={FiMail} type="email" value={form.email} onChange={(e) => setField('email', e.target.value)} error={errors.email} />
              <PremiumInput label="Phone" icon={FiPhone} value={form.phone} onChange={(e) => setField('phone', e.target.value)} error={errors.phone} />
              <PremiumInput label="Current location" icon={FiMapPin} value={form.currentLocation} onChange={(e) => setField('currentLocation', e.target.value)} error={errors.currentLocation} />
              <PremiumInput label="Preferred location" icon={FiMapPin} value={form.preferredLocation} onChange={(e) => setField('preferredLocation', e.target.value)} error={errors.preferredLocation} />
              <PremiumInput label="LinkedIn URL" icon={FiLink} value={form.linkedinUrl} onChange={(e) => setField('linkedinUrl', e.target.value)} />
              <PremiumInput label="Portfolio" icon={FiGlobe} value={form.portfolioUrl} onChange={(e) => setField('portfolioUrl', e.target.value)} />
              <PremiumInput label="GitHub URL" icon={FiGlobe} value={form.githubUrl || ''} onChange={(e) => setField('githubUrl', e.target.value)} />
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Experience level</label>
                <select
                  className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm"
                  value={form.experienceLevel}
                  onChange={(e) => setField('experienceLevel', e.target.value)}
                  data-testid="experience-level"
                >
                  <option value="">Select</option>
                  <option value="fresher">Fresher</option>
                  <option value="experienced">Experienced</option>
                </select>
                {errors.experienceLevel && <p className="mt-1 text-sm text-red-600">{errors.experienceLevel}</p>}
              </div>
            </div>

            <PremiumInput label="Skills (comma-separated)" value={form.skills} onChange={(e) => setField('skills', e.target.value)} />
            <PremiumInput label="Professional summary" as="textarea" value={form.summary || ''} onChange={(e) => setField('summary', e.target.value)} className="min-h-[80px] resize-y" />

            <div>
              <h3 className="text-sm font-semibold text-slate-800 mb-2">Education</h3>
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
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-slate-800 mb-2">Experience</h3>
              <div className="space-y-3">
                {(form.experiences || []).map((exp, i) => (
                  <div key={i} className="rounded-xl border border-slate-200 p-3 grid sm:grid-cols-2 gap-3">
                    <PremiumInput label="Company" value={exp.company} onChange={(e) => updateList('experiences', i, 'company', e.target.value)} />
                    <PremiumInput label="Role" value={exp.role} onChange={(e) => updateList('experiences', i, 'role', e.target.value)} />
                    <PremiumInput label="Description" value={exp.description || ''} onChange={(e) => updateList('experiences', i, 'description', e.target.value)} className="sm:col-span-2" />
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-slate-800 mb-2">Certifications</h3>
              <div className="space-y-3">
                {(form.certifications || []).map((cert, i) => (
                  <div key={i} className="rounded-xl border border-slate-200 p-3 grid sm:grid-cols-2 gap-3">
                    <PremiumInput label="Name" value={cert.name} onChange={(e) => updateList('certifications', i, 'name', e.target.value)} />
                    <PremiumInput label="Issuer" value={cert.issuer} onChange={(e) => updateList('certifications', i, 'issuer', e.target.value)} />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
