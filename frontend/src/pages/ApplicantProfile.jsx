import React, { useMemo, useRef, useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'
import { useToast } from '../components/Toast.jsx'
import MonthYearPicker from '../components/MonthYearPicker.jsx'
import ResumeUploadWithParsing from '../components/ResumeUploadWithParsing.jsx'
import PremiumInput from '../components/PremiumInput.jsx'
import PremiumButton from '../components/PremiumButton.jsx'
import { BASE_URL } from '../utils/api'
import { motion, AnimatePresence } from 'framer-motion'
import { FiUser, FiMail, FiPhone, FiMapPin, FiLinkedin, FiGlobe, FiSave, FiCheck, FiAlertCircle } from 'react-icons/fi'

const DRAFT_STORAGE_KEY = 'applicantProfileDraft'

function getDraftFromStorage() {
	try {
		const raw = typeof window !== 'undefined' && window.sessionStorage.getItem(DRAFT_STORAGE_KEY)
		return raw ? JSON.parse(raw) : null
	} catch {
		return null
	}
}

function saveDraftToStorage(formData) {
	try {
		if (typeof window === 'undefined') return
		const toStore = { ...formData }
		delete toStore.resumeFile
		window.sessionStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(toStore))
	} catch {
		// ignore
	}
}

function clearDraftFromStorage() {
	try {
		if (typeof window !== 'undefined') window.sessionStorage.removeItem(DRAFT_STORAGE_KEY)
	} catch {
		// ignore
	}
}

export default function ApplicantProfile() {
	const { applicantProfile, applicantAuth, saveApplicantProfile, markApplicantProfileCompleted, applyToJobAsApplicant, fetchApplicantData, applicantSavedJobs, toggleSaveJob, getToken } = useApp()
	const navigate = useNavigate()
	const location = useLocation()
	const toast = useToast()
  const firstErrorRef = useRef(null)
  const fileInputRef = useRef(null)
  const validationSummaryRef = useRef(null)
  const currentResumeFileRef = useRef(null)
  const lastAutoSavedResumeRef = useRef(null)

	const strField = (v) => (v == null || v === '') ? '' : String(v).trim()
	const [form, setForm] = useState({
		experienceLevel: applicantProfile.experienceLevel || '',
		servingNotice: applicantProfile.servingNotice || '',
		noticePeriod: applicantProfile.noticePeriod || '',
		lastWorkingDay: applicantProfile.lastWorkingDay || '',
		fullName: strField(applicantProfile.fullName),
		email: strField(applicantProfile.email),
		phone: strField(applicantProfile.phone),
		linkedinUrl: strField(applicantProfile.linkedinUrl),
		portfolioUrl: strField(applicantProfile.portfolioUrl),
		currentLocation: strField(applicantProfile.currentLocation),
		preferredLocation: strField(applicantProfile.preferredLocation),
		resumeFile: null,
		resumeFileName: applicantProfile.resumeFileName || '',
		education: applicantProfile.education && applicantProfile.education.length ? applicantProfile.education : [{ degree: '', institution: '', cgpa: '', startMonth: '', endMonth: '' }],
		certifications: applicantProfile.certifications && applicantProfile.certifications.length ? applicantProfile.certifications : [{ name: '', issuer: '', validTill: '', validationUrl: '', status: '' }],
		experiences: applicantProfile.experiences && applicantProfile.experiences.length ? applicantProfile.experiences : [{ company: '', role: '', startMonth: '', endMonth: '', isCurrent: false }],
	})
	const [saved, setSaved] = useState('')
	const [errors, setErrors] = useState({})
	const [autofilledFields, setAutofilledFields] = useState({})
	const [formInitialized, setFormInitialized] = useState(false)
	
	// Fetch profile from server when page mounts (ensures fresh data after login/navigation)
	useEffect(() => {
		if (applicantAuth.isLoggedIn && fetchApplicantData) {
			fetchApplicantData()
		}
	}, [applicantAuth.isLoggedIn])
	
	// Helper to build form from applicantProfile (handles backend cert format: certification -> name)
	const buildFormFromProfile = (profile, prevForm = {}) => {
		const toStr = (v) => (v == null || v === '') ? '' : String(v).trim()
		const normCerts = (arr) => {
			if (!Array.isArray(arr) || arr.length === 0) return prevForm.certifications?.length ? prevForm.certifications : [{ name: '', issuer: '', validTill: '', validationUrl: '', status: '' }]
			return arr.map(c => ({
				name: toStr(c.name ?? c.certification),
				issuer: toStr(c.issuer),
				validTill: toStr(c.validTill ?? c.endMonth),
				validationUrl: toStr(c.validationUrl),
				status: toStr(c.status),
			}))
		}
		return {
			experienceLevel: profile?.experienceLevel || prevForm.experienceLevel || '',
			servingNotice: profile?.servingNotice || prevForm.servingNotice || '',
			noticePeriod: profile?.noticePeriod || prevForm.noticePeriod || '',
			lastWorkingDay: profile?.lastWorkingDay || prevForm.lastWorkingDay || '',
			fullName: toStr(profile?.fullName) || prevForm.fullName || '',
			email: toStr(profile?.email) || prevForm.email || '',
			phone: toStr(profile?.phone) || prevForm.phone || '',
			linkedinUrl: toStr(profile?.linkedinUrl) || prevForm.linkedinUrl || '',
			portfolioUrl: toStr(profile?.portfolioUrl) || prevForm.portfolioUrl || '',
			currentLocation: toStr(profile?.currentLocation) || prevForm.currentLocation || '',
			preferredLocation: toStr(profile?.preferredLocation) || prevForm.preferredLocation || '',
			resumeFile: null,
			resumeFileName: profile?.resumeFileName || prevForm.resumeFileName || '',
			education: (profile?.education && Array.isArray(profile.education) && profile.education.length > 0)
				? profile.education
				: (prevForm.education?.length ? prevForm.education : [{ degree: '', institution: '', cgpa: '', startMonth: '', endMonth: '' }]),
			certifications: normCerts(profile?.certifications),
			experiences: (profile?.experiences && Array.isArray(profile.experiences) && profile.experiences.length > 0)
				? profile.experiences
				: (prevForm.experiences?.length ? prevForm.experiences : [{ company: '', role: '', startMonth: '', endMonth: '', isCurrent: false }]),
		}
	}

	// Load profile data into form when component mounts; restore draft if no saved profile
	useEffect(() => {
		if (!formInitialized) {
			setForm(prevForm => {
				const hasUserInput = prevForm.fullName || prevForm.email ||
					prevForm.experiences?.some(ex => ex.company || ex.role) ||
					prevForm.education?.some(ed => ed.degree || ed.institution)
				if (hasUserInput && !applicantProfile?.fullName && !applicantProfile?.email) return prevForm

				const toStr = (v) => (v == null || v === '') ? '' : String(v).trim()
				const hasSavedProfile = toStr(applicantProfile?.fullName) || toStr(applicantProfile?.email)

				// If no saved profile, try restoring from sessionStorage draft (avoids losing data on remount/navigation)
				if (!hasSavedProfile) {
					const draft = getDraftFromStorage()
					if (draft && (toStr(draft.fullName) || toStr(draft.phone) || (Array.isArray(draft.education) && draft.education.some(ed => toStr(ed?.degree) || toStr(ed?.institution))))) {
						return {
							...draft,
							resumeFile: null,
							education: Array.isArray(draft.education) && draft.education.length > 0 ? draft.education : [{ degree: '', institution: '', cgpa: '', startMonth: '', endMonth: '' }],
							certifications: Array.isArray(draft.certifications) && draft.certifications.length > 0 ? draft.certifications : [{ name: '', issuer: '', validTill: '', validationUrl: '', status: '' }],
							experiences: Array.isArray(draft.experiences) && draft.experiences.length > 0 ? draft.experiences : [{ company: '', role: '', startMonth: '', endMonth: '', isCurrent: false }],
						}
					}
				}

				return buildFormFromProfile(applicantProfile, prevForm)
			})
			setFormInitialized(true)
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [])

	// Persist form as draft to sessionStorage so data survives remounts (e.g. Strict Mode, navigate away and back)
	useEffect(() => {
		if (!formInitialized) return
		const hasContent = strField(form.fullName) || strField(form.phone) || strField(form.email) ||
			form.education?.some(ed => strField(ed.degree) || strField(ed.institution)) ||
			form.experiences?.some(ex => strField(ex.company) || strField(ex.role))
		if (!hasContent) return
		const t = setTimeout(() => saveDraftToStorage(form), 600)
		return () => clearTimeout(t)
	}, [form, formInitialized])

	// Re-sync form when profile is loaded/updated (e.g. from server after fetch) so we never show empty when profile has data
	useEffect(() => {
		const profileHasData =
			(applicantProfile?.fullName && applicantProfile.fullName.trim()) ||
			(applicantProfile?.resumeFileName && applicantProfile.resumeFileName.trim()) ||
			(Array.isArray(applicantProfile?.education) && applicantProfile.education.length > 0) ||
			(Array.isArray(applicantProfile?.experiences) && applicantProfile.experiences.length > 0)
		if (!profileHasData) return
		setForm(prevForm => {
			const formEmpty =
				!prevForm.fullName &&
				!prevForm.resumeFileName &&
				!(Array.isArray(prevForm.education) && prevForm.education.some((ed) => (ed?.degree || '').trim() || (ed?.institution || '').trim())) &&
				!(Array.isArray(prevForm.experiences) && prevForm.experiences.some((ex) => (ex?.company || '').trim() || (ex?.role || '').trim()))
			if (!formEmpty) return prevForm
			return buildFormFromProfile(applicantProfile, prevForm)
		})
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [applicantProfile?.fullName, applicantProfile?.resumeFileName, applicantProfile?.education, applicantProfile?.experiences, applicantProfile?.certifications])
	
	useEffect(() => {
		if (applicantProfile?.resumeFileName && !form.resumeFile) {
			updateField('resumeFileName', applicantProfile.resumeFileName)
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [applicantProfile?.resumeFileName])

	// Keep ref in sync so "View resume" always sees the current file (avoids stale closure)
	useEffect(() => {
		currentResumeFileRef.current = form.resumeFile instanceof File ? form.resumeFile : null
	}, [form.resumeFile])

	// Auto-save new resume to server when user uploads (so refresh shows the new resume)
	useEffect(() => {
		const file = form.resumeFile instanceof File ? form.resumeFile : null
		if (!applicantAuth.isLoggedIn || !(file instanceof File)) {
			if (!file) lastAutoSavedResumeRef.current = null
			return
		}
		const key = `${file.name}-${file.size}`
		if (lastAutoSavedResumeRef.current === key) return
		lastAutoSavedResumeRef.current = key
		saveApplicantProfile({ ...form, resumeFile: file })
			.catch(() => { lastAutoSavedResumeRef.current = null })
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [form.resumeFile])

	const validate = (f) => {
		const e = {}
		const s = (v) => (v == null ? '' : String(v)).trim()
		if (!s(f.fullName)) e.fullName = 'Full name is required'
		if (!s(f.email)) e.email = 'Email is required'
		if (!s(f.phone)) e.phone = 'Phone is required'
		if (!s(f.currentLocation)) e.currentLocation = 'Current location is required'
		if (!s(f.preferredLocation)) e.preferredLocation = 'Preferred location is required'
		if (!f.resumeFileName) e.resumeFileName = 'Resume is required'
		
		const hasEducation = Array.isArray(f.education) && f.education.some(ed => s(ed.degree) && s(ed.institution))
		if (!hasEducation) {
			e.education = 'At least one education entry with Degree and Institution is required'
		} else {
			const deg = (ed) => s(ed.degree).toLowerCase()
			const has10th = f.education.some(ed =>
				deg(ed).includes('10') ||
				deg(ed).includes('tenth') ||
				deg(ed).includes('ssc') ||
				deg(ed).includes('secondary')
			)
			const has12thOrDiploma = f.education.some(ed =>
				deg(ed).includes('12') ||
				deg(ed).includes('twelfth') ||
				deg(ed).includes('hsc') ||
				deg(ed).includes('senior secondary') ||
				deg(ed).includes('diploma') ||
				deg(ed).includes('intermediate')
			)
			
			if (!has10th) {
				e.education = 'Please add your 10th standard education details'
			} else if (!has12thOrDiploma) {
				e.education = 'Please add your 12th standard or Diploma education details'
			}
		}
		
		if (!f.experienceLevel) e.experienceLevel = 'Select fresher or experienced'
		if (f.experienceLevel === 'experienced') {
			if (!f.servingNotice) e.servingNotice = 'Please select an option'
			if (!f.noticePeriod) e.noticePeriod = 'Notice period is required'
			if (f.servingNotice === 'yes' && !f.lastWorkingDay) {
				e.lastWorkingDay = 'Last working day is required when serving notice'
			} else if (f.noticePeriod === 'Immediate' && !f.lastWorkingDay) {
				e.lastWorkingDay = 'Joining date is required for immediate joiners'
			}
		}
		return e
	}

	const isComplete = useMemo(() => Object.keys(validate(form)).length === 0, [form])

	const updateField = (key, val) => setForm((f) => ({ ...f, [key]: val }))
	const updateListItem = (listKey, idx, key, val) => {
		setForm((f) => {
			const next = f[listKey].slice()
			next[idx] = { ...next[idx], [key]: val }
			return { ...f, [listKey]: next }
		})
	}

	const addListItem = (listKey) => setForm((f) => ({
		...f,
		[listKey]: [
			...f[listKey],
			listKey === 'education'
				? { degree: '', institution: '', cgpa: '', startMonth: '', endMonth: '' }
			: listKey === 'certifications'
				? { name: '', issuer: '', validTill: '', validationUrl: '', status: '' }
				: { company: '', role: '', startMonth: '', endMonth: '', isCurrent: false },
		],
	}))
	const removeListItem = (listKey, idx) => setForm((f) => ({ ...f, [listKey]: f[listKey].filter((_, i) => i !== idx) }))

	const handleResumeAutofill = (parsedData) => {
		// Track which fields were autofilled
		const autofilled = {};
		if (parsedData.fullName) autofilled.fullName = true;
		if (parsedData.email) autofilled.email = true;
		if (parsedData.phone) autofilled.phone = true;
		if (parsedData.experienceLevel) autofilled.experienceLevel = true;
		if (parsedData.linkedinUrl) autofilled.linkedinUrl = true;
		if (parsedData.portfolioUrl) autofilled.portfolioUrl = true;
		if (parsedData.currentLocation) autofilled.currentLocation = true;
		if (parsedData.preferredLocation) autofilled.preferredLocation = true;
		setAutofilledFields(autofilled);

		const toStr = (v) => (v == null || v === '') ? '' : String(v).trim();
		const defaultEducation = [{ degree: '', institution: '', cgpa: '', startMonth: '', endMonth: '' }];
		const defaultCertifications = [{ name: '', issuer: '', validTill: '', validationUrl: '', status: '' }];
		const defaultExperiences = [{ company: '', role: '', startMonth: '', endMonth: '', isCurrent: false }];

		// Replace form with new parsed resume data (new resume fully replaces previous parsed data)
		setForm((prevForm) => ({
			...prevForm,
			fullName: toStr(parsedData.fullName),
			email: toStr(parsedData.email),
			phone: toStr(parsedData.phone),
			linkedinUrl: toStr(parsedData.linkedinUrl),
			portfolioUrl: toStr(parsedData.portfolioUrl),
			currentLocation: toStr(parsedData.currentLocation),
			preferredLocation: toStr(parsedData.preferredLocation),
			experienceLevel: parsedData.experienceLevel || '',
			education: Array.isArray(parsedData.education) && parsedData.education.length > 0 ? parsedData.education : defaultEducation,
			experiences: Array.isArray(parsedData.experiences) && parsedData.experiences.length > 0 ? parsedData.experiences : defaultExperiences,
			certifications: Array.isArray(parsedData.certifications) && parsedData.certifications.length > 0 ? parsedData.certifications : defaultCertifications,
			resumeFile: parsedData.resumeFile ?? prevForm.resumeFile,
			resumeFileName: parsedData.resumeFileName || prevForm.resumeFileName,
			// Keep form-only fields (not from resume)
			servingNotice: prevForm.servingNotice,
			noticePeriod: prevForm.noticePeriod,
			lastWorkingDay: prevForm.lastWorkingDay,
		}));

		setErrors({});

		setTimeout(() => setAutofilledFields({}), 3000);
		
		window.scrollTo({ top: 0, behavior: 'smooth' });
	}

	const onSave = async (e) => {
		e.preventDefault()
		e.stopPropagation()
		
		console.log('DEBUG: onSave called, form data:', {
			fullName: form.fullName,
			email: form.email,
			experiencesCount: form.experiences?.length || 0,
			educationCount: form.education?.length || 0,
			hasResumeFile: !!form.resumeFile,
			resumeFileName: form.resumeFileName
		})
		
		try {
			// Use ref so we never lose the current resume file when saving (same as View resume)
			const profileToSave = { ...form, resumeFile: form.resumeFile ?? currentResumeFileRef.current }
			const result = await saveApplicantProfile(profileToSave)
			console.log('DEBUG: saveApplicantProfile result:', result)
			
			if (result.ok) {
				clearDraftFromStorage()
				if (result.warning) {
					// Show warning but still indicate success
					setSaved('Profile saved locally')
					toast.push(result.warning, { type: 'warning', duration: 6000 })
				} else {
					setSaved('Profile saved')
					toast.push('Profile saved successfully! You can come back and complete it later.', { type: 'success', duration: 5000 })
				}
				setTimeout(() => setSaved(''), 3000)
				
				if (fileInputRef.current) {
					fileInputRef.current.value = ''
				}
				
				if (form.resumeFile) {
					updateField('resumeFile', null)
				}
				if (result.updatedProfile && result.updatedProfile.resumeFileName) {
					updateField('resumeFileName', result.updatedProfile.resumeFileName)
				} else if (form.resumeFileName) {
					// Keep existing filename
				}
			} else {
				console.error('DEBUG: Save failed, result:', result)
				toast.push('Failed to save profile. Your data has been saved locally as backup.', { type: 'error', duration: 5000 })
			}
		} catch (error) {
			console.error('DEBUG: Save error caught:', error)
			console.error('DEBUG: Error details:', {
				message: error?.message,
				stack: error?.stack,
				error: error
			})
			// Even if there's an error, data should be saved locally
			setSaved('Profile saved locally')
			toast.push('An error occurred while saving to server. Your data has been saved locally and will sync when you log in.', { type: 'warning', duration: 6000 })
			setTimeout(() => setSaved(''), 3000)
		}
	}

	const onComplete = async (e) => {
		e.preventDefault()
		const eMap = validate(form)
		setErrors(eMap)
		if (Object.keys(eMap).length > 0) {
			// Scroll to validation summary so user sees which fields are missing
			setTimeout(() => {
				validationSummaryRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
			}, 50)
			return
		}
		const profileToSave = { ...form, resumeFile: form.resumeFile ?? currentResumeFileRef.current }
		const saveResult = await saveApplicantProfile(profileToSave)
		clearDraftFromStorage()
		
		if (fileInputRef.current) {
			fileInputRef.current.value = ''
		}
		
		if (form.resumeFile || currentResumeFileRef.current) {
			updateField('resumeFile', null)
		}
		if (saveResult.updatedProfile && saveResult.updatedProfile.resumeFileName) {
			updateField('resumeFileName', saveResult.updatedProfile.resumeFileName)
		} else if (form.resumeFileName) {
		}
		
    await markApplicantProfileCompleted(form)
		
		const sp = new URLSearchParams(location.search)
		let redirectTo = sp.get('redirect') || '/jobs'
		let applyForJobId = sp.get('applyFor')
		
		if (!applyForJobId && redirectTo) {
			try {
				const redirectUrl = new URL(redirectTo, window.location.origin)
				applyForJobId = redirectUrl.searchParams.get('applyFor')
				redirectUrl.searchParams.delete('applyFor')
				redirectTo = redirectUrl.pathname + redirectUrl.search
			} catch (err) {
				const redirectParams = new URLSearchParams(redirectTo.split('?')[1] || '')
				applyForJobId = redirectParams.get('applyFor') || applyForJobId
				redirectTo = redirectTo.split('?')[0] || '/jobs'
			}
		}
		
		if (applyForJobId) {
			const applyResult = await applyToJobAsApplicant(applyForJobId)
			if (applyResult.ok) {
				if (applicantSavedJobs[applyForJobId] || applicantSavedJobs[String(applyForJobId)]) {
					toggleSaveJob(applyForJobId)
				}
				if (fetchApplicantData) {
					await fetchApplicantData()
				}
			}
		}
		
		navigate(redirectTo)
	}

	return (
		<section className="relative min-h-[calc(100vh-180px)] flex items-center justify-center px-4 py-10 overflow-visible">
			{/* Animated background */}
			<div className="pointer-events-none absolute inset-0">
				<motion.div 
					animate={{
						scale: [1, 1.2, 1],
						opacity: [0.3, 0.5, 0.3],
					}}
					transition={{ duration: 8, repeat: Infinity }}
					className="absolute -top-24 -left-24 h-72 w-72 rounded-full bg-purple-500/20 blur-3xl" 
				/>
				<motion.div 
					animate={{
						scale: [1.2, 1, 1.2],
						opacity: [0.3, 0.5, 0.3],
					}}
					transition={{ duration: 10, repeat: Infinity }}
					className="absolute -bottom-24 -right-24 h-80 w-80 rounded-full bg-blue-500/20 blur-3xl" 
				/>
				<div className="absolute inset-0 opacity-[0.07]" style={{backgroundImage:'radial-gradient(circle at 1px 1px, #fff 1px, transparent 0)', backgroundSize:'24px 24px'}} />
			</div>

			<motion.div 
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.6 }}
				className="w-full max-w-3xl relative"
			>
				<div className="glass-card rounded-3xl p-[1px] shadow-premium border border-white/10">
					<div className="rounded-3xl bg-gradient-to-br from-zinc-900/95 via-zinc-900/90 to-zinc-900/85 backdrop-blur-xl p-6 sm:p-8">
						<motion.div
							initial={{ opacity: 0, y: -10 }}
							animate={{ opacity: 1, y: 0 }}
							transition={{ delay: 0.2 }}
						>
							<h2 className="text-3xl font-bold bg-gradient-to-r from-white to-zinc-400 bg-clip-text text-transparent">
								Complete Your Profile
							</h2>
							<p className="mt-2 text-sm text-zinc-400">We'll use this info when you apply to jobs</p>
						</motion.div>

						<form onSubmit={onSave} noValidate className="mt-8 space-y-8">
							{saved && (
								<motion.div
									initial={{ opacity: 0, scale: 0.95 }}
									animate={{ opacity: 1, scale: 1 }}
									className="glass-card border-2 border-green-500/30 bg-green-500/10 px-5 py-4 rounded-xl flex items-center gap-3"
								>
									<FiCheck className="w-5 h-5 text-green-400" />
									<span className="text-sm font-medium text-green-300">{saved}</span>
								</motion.div>
							)}

							{/* Validation summary: list missing/invalid fields when Save & Complete is clicked */}
							{Object.keys(errors).length > 0 && (
								<motion.div
									ref={validationSummaryRef}
									initial={{ opacity: 0, y: -10 }}
									animate={{ opacity: 1, y: 0 }}
									className="glass-card border-2 border-amber-500/40 bg-amber-500/10 px-5 py-4 rounded-xl"
								>
									<p className="text-sm font-semibold text-amber-200 mb-2 flex items-center gap-2">
										<FiAlertCircle className="w-4 h-4 shrink-0" />
										Please fill the following required fields:
									</p>
									<ul className="list-disc list-inside space-y-1 text-sm text-amber-200/90">
										{Object.entries(errors).map(([key, message]) => (
											<li key={key}>{message}</li>
										))}
									</ul>
								</motion.div>
							)}

							{/* Resume Upload */}
							<motion.div
								initial={{ opacity: 0, y: 20 }}
								animate={{ opacity: 1, y: 0 }}
								transition={{ delay: 0.3 }}
							>
								<label className="block text-sm font-medium text-zinc-300 mb-3">
									Resume Upload with AI Parsing <span className="text-red-400">*</span>
								</label>
								<ResumeUploadWithParsing
									onAutofill={handleResumeAutofill}
									onFileSelect={(file) => {
										updateField('resumeFile', file);
										updateField('resumeFileName', file.name);
										if (errors.resumeFileName) setErrors((er)=>({ ...er, resumeFileName: undefined }));
									}}
									currentFileName={form.resumeFileName}
									onRemove={() => {
										updateField('resumeFile', null);
										updateField('resumeFileName', '');
										if (errors.resumeFileName) setErrors((er)=>({ ...er, resumeFileName: undefined }));
									}}
									onOpenResume={applicantAuth.isLoggedIn ? async () => {
										// Use ref so we always get the latest file (avoids stale closure after upload)
										const file = currentResumeFileRef.current;
										if (file instanceof File) {
											const url = URL.createObjectURL(file);
											window.open(url, '_blank');
											setTimeout(() => URL.revokeObjectURL(url), 60000);
											return;
										}
										const token = getToken?.();
										if (!token) return;
										try {
											const res = await fetch(`${BASE_URL}/api/candidate/resume?t=${Date.now()}`, {
												headers: { Authorization: `Bearer ${token}` },
											});
											if (!res.ok) throw new Error('Failed to load resume');
											const blob = await res.blob();
											const url = URL.createObjectURL(blob);
											window.open(url, '_blank');
											setTimeout(() => URL.revokeObjectURL(url), 60000);
										} catch (e) {
											toast.push('Could not open resume. Try again or download after saving.', { type: 'error' });
										}
									} : undefined}
								/>
								{errors.resumeFileName && (
									<motion.div
										initial={{ opacity: 0, y: -5 }}
										animate={{ opacity: 1, y: 0 }}
										className="mt-2 flex items-center gap-2 text-xs text-red-400"
									>
										<FiAlertCircle className="w-3 h-3" />
										{errors.resumeFileName}
									</motion.div>
								)}
							</motion.div>

							{/* Personal Information */}
							<motion.div
								initial={{ opacity: 0, y: 20 }}
								animate={{ opacity: 1, y: 0 }}
								transition={{ delay: 0.4 }}
								className="grid sm:grid-cols-2 gap-6"
							>
								<PremiumInput
									ref={errors.fullName ? firstErrorRef : undefined}
									label="Full Name"
									icon={FiUser}
									required
									value={form.fullName}
									onChange={(e) => { 
										updateField('fullName', e.target.value); 
										if (errors.fullName) setErrors((er)=>({ ...er, fullName: undefined })) 
									}}
									error={errors.fullName}
									isAutofilled={autofilledFields.fullName}
								/>
								<PremiumInput
									label="Email"
									icon={FiMail}
									type="email"
									required
									value={form.email}
									onChange={(e) => { 
										updateField('email', e.target.value); 
										if (errors.email) setErrors((er)=>({ ...er, email: undefined })) 
									}}
									error={errors.email}
									isAutofilled={autofilledFields.email}
								/>
								<PremiumInput
									label="Phone"
									icon={FiPhone}
									required
									value={form.phone}
									onChange={(e) => { 
										updateField('phone', e.target.value); 
										if (errors.phone) setErrors((er)=>({ ...er, phone: undefined })) 
									}}
									error={errors.phone}
									isAutofilled={autofilledFields.phone}
								/>
							</motion.div>

							{/* Experience Details */}
							<motion.div
								initial={{ opacity: 0, y: 20 }}
								animate={{ opacity: 1, y: 0 }}
								transition={{ delay: 0.5 }}
								className="glass-card border border-white/10 rounded-2xl p-6 bg-white/5"
							>
								<h3 className="text-lg font-semibold text-white mb-2">Experience Details</h3>
								<p className="text-sm text-zinc-400 mb-6">Tell us about your current experience and availability.</p>

								<div className="space-y-6">
									<div>
										<label className="block text-sm font-medium text-zinc-300 mb-3">
											Are you a fresher or experienced? <span className="text-red-400">*</span>
										</label>
										<div className="flex flex-wrap gap-3">
											{['fresher', 'experienced'].map((level) => (
												<motion.label
													key={level}
													whileHover={{ scale: 1.05 }}
													whileTap={{ scale: 0.95 }}
													className={`flex items-center gap-3 rounded-xl border-2 px-5 py-3 text-sm transition-all cursor-pointer ${
														form.experienceLevel === level 
															? 'border-purple-500 bg-purple-500/20 text-white shadow-glow-sm' 
															: 'border-zinc-700 text-zinc-300 hover:border-zinc-600 bg-white/5'
													}`}
												>
													<input
														type="radio"
														name="experienceLevel"
														value={level}
														onChange={(e) => setForm((prev) => ({
															...prev,
															experienceLevel: e.target.value,
															servingNotice: '',
															noticePeriod: '',
															lastWorkingDay: '',
														}))}
														className="sr-only"
														checked={form.experienceLevel === level}
													/>
													<div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
														form.experienceLevel === level ? 'border-purple-400' : 'border-zinc-600'
													}`}>
														{form.experienceLevel === level && (
															<motion.div
																initial={{ scale: 0 }}
																animate={{ scale: 1 }}
																className="w-3 h-3 rounded-full bg-purple-400"
															/>
														)}
													</div>
													<span className="capitalize font-medium">{level}</span>
												</motion.label>
											))}
										</div>
										{errors.experienceLevel && (
											<motion.p
												initial={{ opacity: 0, y: -5 }}
												animate={{ opacity: 1, y: 0 }}
												className="mt-2 text-xs text-red-400 flex items-center gap-1"
											>
												<FiAlertCircle className="w-3 h-3" />
												{errors.experienceLevel}
											</motion.p>
										)}
									</div>

									<AnimatePresence>
										{form.experienceLevel === 'experienced' && (
											<motion.div
												initial={{ opacity: 0, height: 0 }}
												animate={{ opacity: 1, height: 'auto' }}
												exit={{ opacity: 0, height: 0 }}
												className="space-y-6"
											>
												<div>
													<label className="block text-sm font-medium text-zinc-300 mb-3">
														Are you currently serving your notice period? <span className="text-red-400">*</span>
													</label>
													<div className="flex flex-wrap gap-3">
														{[{ value: 'yes', label: 'Yes' }, { value: 'no', label: 'No' }].map((option) => (
															<motion.label
																key={option.value}
																whileHover={{ scale: 1.05 }}
																whileTap={{ scale: 0.95 }}
																className={`flex items-center gap-3 rounded-xl border-2 px-5 py-3 text-sm transition-all cursor-pointer ${
																	form.servingNotice === option.value 
																		? 'border-purple-500 bg-purple-500/20 text-white shadow-glow-sm' 
																		: 'border-zinc-700 text-zinc-300 hover:border-zinc-600 bg-white/5'
																}`}
															>
																<input
																	type="radio"
																	name="servingNotice"
																	value={option.value}
																	onChange={(e) => {
																		setForm((prev) => ({
																			...prev,
																			servingNotice: e.target.value,
																		}))
																		if (errors.servingNotice) setErrors((er)=>({ ...er, servingNotice: undefined }))
																	}}
																	className="sr-only"
																	checked={form.servingNotice === option.value}
																/>
																<div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
																	form.servingNotice === option.value ? 'border-purple-400' : 'border-zinc-600'
																}`}>
																	{form.servingNotice === option.value && (
																		<motion.div
																			initial={{ scale: 0 }}
																			animate={{ scale: 1 }}
																			className="w-3 h-3 rounded-full bg-purple-400"
																		/>
																	)}
																</div>
																<span className="font-medium">{option.label}</span>
															</motion.label>
														))}
													</div>
												</div>

												<PremiumInput
													label="What is your notice period?"
													required
													as="select"
													value={form.noticePeriod}
													onChange={(e) => {
														updateField('noticePeriod', e.target.value)
														if (errors.noticePeriod) setErrors((er)=>({ ...er, noticePeriod: undefined }))
													}}
													error={errors.noticePeriod}
													className="premium-input"
												>
													<option value="" style={{ color: '#f3f4f6', backgroundColor: '#18181b' }}>Select</option>
													<option style={{ color: '#f3f4f6', backgroundColor: '#18181b' }}>Immediate</option>
													<option style={{ color: '#f3f4f6', backgroundColor: '#18181b' }}>&lt; 30 days</option>
													<option style={{ color: '#f3f4f6', backgroundColor: '#18181b' }}>&lt; 45 days</option>
													<option style={{ color: '#f3f4f6', backgroundColor: '#18181b' }}>&lt; 60 days</option>
													<option style={{ color: '#f3f4f6', backgroundColor: '#18181b' }}>&lt; 90 days</option>
													<option style={{ color: '#f3f4f6', backgroundColor: '#18181b' }}>Serving Notice Period</option>
												</PremiumInput>

												{(form.servingNotice === 'yes' || form.noticePeriod === 'Immediate') && (
													<PremiumInput
														label={form.noticePeriod === 'Immediate' ? 'Joining date' : 'Last working day'}
														type="date"
														required
														value={form.lastWorkingDay}
														onChange={(e) => { 
															updateField('lastWorkingDay', e.target.value)
															if (errors.lastWorkingDay) setErrors((er)=>({ ...er, lastWorkingDay: undefined }))
														}}
														error={errors.lastWorkingDay}
														helperText={form.noticePeriod === 'Immediate' ? 'As an immediate joiner, you cannot select a future date' : ''}
														max={form.noticePeriod === 'Immediate' ? new Date().toISOString().split('T')[0] : undefined}
														className="date-picker-dark"
													/>
												)}
											</motion.div>
										)}
									</AnimatePresence>
								</div>
							</motion.div>

							{/* Location */}
							<motion.div
								initial={{ opacity: 0, y: 20 }}
								animate={{ opacity: 1, y: 0 }}
								transition={{ delay: 0.6 }}
								className="grid sm:grid-cols-2 gap-6"
							>
								<PremiumInput
									label="Current Location"
									icon={FiMapPin}
									required
									value={form.currentLocation}
									onChange={(e) => { 
										updateField('currentLocation', e.target.value); 
										if (errors.currentLocation) setErrors((er)=>({ ...er, currentLocation: undefined })) 
									}}
									error={errors.currentLocation}
								/>
								<PremiumInput
									label="Preferred Location"
									icon={FiMapPin}
									required
									value={form.preferredLocation}
									onChange={(e) => { 
										updateField('preferredLocation', e.target.value); 
										if (errors.preferredLocation) setErrors((er)=>({ ...er, preferredLocation: undefined })) 
									}}
									error={errors.preferredLocation}
								/>
							</motion.div>

							{/* Social Links */}
							<motion.div
								initial={{ opacity: 0, y: 20 }}
								animate={{ opacity: 1, y: 0 }}
								transition={{ delay: 0.7 }}
								className="grid sm:grid-cols-2 gap-6"
							>
								<PremiumInput
									label="LinkedIn URL"
									icon={FiLinkedin}
									type="url"
									placeholder="https://linkedin.com/in/username"
									value={form.linkedinUrl}
									onChange={(e) => updateField('linkedinUrl', e.target.value)}
								/>
								<PremiumInput
									label="Website/Portfolio"
									icon={FiGlobe}
									type="url"
									placeholder="https://your-portfolio.com"
									value={form.portfolioUrl}
									onChange={(e) => updateField('portfolioUrl', e.target.value)}
								/>
							</motion.div>

							{/* Education */}
							<motion.div
								initial={{ opacity: 0, y: 20 }}
								animate={{ opacity: 1, y: 0 }}
								transition={{ delay: 0.8 }}
							>
								<div className="flex items-center justify-between mb-4">
									<div>
										<label className="block text-sm font-medium text-zinc-300">
											Education <span className="text-red-400">*</span>
										</label>
										<p className="mt-1 text-xs text-zinc-400">Include all education from 10th standard onwards</p>
									</div>
									<PremiumButton
										type="button"
										variant="secondary"
										size="sm"
										onClick={() => { 
											addListItem('education'); 
											if (errors.education) setErrors((er)=>({ ...er, education: undefined })) 
										}}
									>
										Add
									</PremiumButton>
								</div>
								{errors.education && (
									<motion.div
										initial={{ opacity: 0, y: -5 }}
										animate={{ opacity: 1, y: 0 }}
										className="mb-3 text-xs text-red-400 flex items-center gap-1"
									>
										<FiAlertCircle className="w-3 h-3" />
										{errors.education}
									</motion.div>
								)}
								<div className="space-y-4">
									{form.education.map((ed, i) => (
										<motion.div
											key={i}
											initial={{ opacity: 0, scale: 0.95 }}
											animate={{ opacity: 1, scale: 1 }}
											exit={{ opacity: 0, scale: 0.95 }}
											className="glass-card border border-white/10 rounded-xl p-4 bg-white/5"
										>
											<div className="grid sm:grid-cols-5 gap-3">
												<input placeholder="Degree" className="premium-input" value={ed.degree || ''} onChange={(e) => updateListItem('education', i, 'degree', e.target.value)} />
												<input placeholder="Institution" className="premium-input" value={ed.institution || ''} onChange={(e) => updateListItem('education', i, 'institution', e.target.value)} />
												<input placeholder="CGPA/%" className="premium-input" value={ed.cgpa || ''} onChange={(e) => updateListItem('education', i, 'cgpa', e.target.value)} />
												<MonthYearPicker placeholder="Start" value={ed.startMonth || ''} onChange={(v) => updateListItem('education', i, 'startMonth', v)} />
												<MonthYearPicker placeholder="End" value={ed.endMonth || ''} onChange={(v) => updateListItem('education', i, 'endMonth', v)} />
											</div>
											<div className="mt-3 flex justify-end">
												<button type="button" className="text-xs text-zinc-400 hover:text-red-400 transition-colors" onClick={() => removeListItem('education', i)}>Remove</button>
											</div>
										</motion.div>
									))}
								</div>
							</motion.div>

							{/* Certifications */}
							<motion.div
								initial={{ opacity: 0, y: 20 }}
								animate={{ opacity: 1, y: 0 }}
								transition={{ delay: 0.9 }}
							>
								<div className="flex items-center justify-between mb-4">
									<label className="block text-sm font-medium text-zinc-300">Certifications</label>
									<PremiumButton
										type="button"
										variant="secondary"
										size="sm"
										onClick={() => addListItem('certifications')}
									>
										Add
									</PremiumButton>
								</div>
								<div className="space-y-4">
									{form.certifications.map((ce, i) => (
										<motion.div
											key={i}
											initial={{ opacity: 0, scale: 0.95 }}
											animate={{ opacity: 1, scale: 1 }}
											exit={{ opacity: 0, scale: 0.95 }}
											className="glass-card border border-white/10 rounded-xl p-4 bg-white/5"
										>
											<div className="grid sm:grid-cols-2 gap-3">
												<input placeholder="Certification Name" className="premium-input" value={ce.name || ''} onChange={(e) => updateListItem('certifications', i, 'name', e.target.value)} />
												<input placeholder="Issuer" className="premium-input" value={ce.issuer || ''} onChange={(e) => updateListItem('certifications', i, 'issuer', e.target.value)} />
											</div>
											<div className="grid sm:grid-cols-3 gap-3 mt-3">
												<input 
													type="date" 
													placeholder="Valid Till" 
													min="1000-01-01"
													className={`date-picker-dark premium-input ${
														ce.validTill && new Date(ce.validTill) < new Date() && ce.status !== 'pursuing' ? 'border-red-500' : ''
													}`} 
													value={ce.validTill || ''} 
													onChange={(e) => {
														const date = e.target.value;
														if (date && new Date(date) < new Date() && ce.status !== 'pursuing') {
															alert('Cannot save an expired certification. Please select a future date or mark as Pursuing.');
															return;
														}
														updateListItem('certifications', i, 'validTill', date);
													}}
													disabled={ce.status === 'pursuing'}
												/>
												<select 
													className="premium-input"
													value={ce.status || ''}
													onChange={(e) => updateListItem('certifications', i, 'status', e.target.value)}
													style={{ color: '#f3f4f6' }}
												>
													<option value="" style={{ color: '#f3f4f6', backgroundColor: '#18181b' }}>Status</option>
													<option value="completed" style={{ color: '#f3f4f6', backgroundColor: '#18181b' }}>Completed</option>
													<option value="pursuing" style={{ color: '#f3f4f6', backgroundColor: '#18181b' }}>Pursuing</option>
												</select>
												<input 
													type="url" 
													placeholder="Validation URL" 
													className="premium-input" 
													value={ce.validationUrl || ''} 
													onChange={(e) => updateListItem('certifications', i, 'validationUrl', e.target.value)}
												/>
											</div>
											<div className="mt-3 flex justify-end">
												<button type="button" className="text-xs text-zinc-400 hover:text-red-400 transition-colors" onClick={() => removeListItem('certifications', i)}>Remove</button>
											</div>
										</motion.div>
									))}
								</div>
							</motion.div>

							{/* Experience */}
							<motion.div
								initial={{ opacity: 0, y: 20 }}
								animate={{ opacity: 1, y: 0 }}
								transition={{ delay: 1.0 }}
							>
								<div className="flex items-center justify-between mb-4">
									<label className="block text-sm font-medium text-zinc-300">Experience</label>
									<PremiumButton
										type="button"
										variant="secondary"
										size="sm"
										onClick={() => addListItem('experiences')}
									>
										Add
									</PremiumButton>
								</div>
								<div className="space-y-4">
									{form.experiences.map((ex, i) => (
										<motion.div
											key={i}
											initial={{ opacity: 0, scale: 0.95 }}
											animate={{ opacity: 1, scale: 1 }}
											exit={{ opacity: 0, scale: 0.95 }}
											className="glass-card border border-white/10 rounded-xl p-4 bg-white/5"
										>
											<div className="grid sm:grid-cols-5 gap-3">
												<input placeholder="Company" className="premium-input" value={ex.company || ''} onChange={(e) => updateListItem('experiences', i, 'company', e.target.value)} />
												<input placeholder="Role" className="premium-input" value={ex.role || ''} onChange={(e) => updateListItem('experiences', i, 'role', e.target.value)} />
												<MonthYearPicker placeholder="Start" value={ex.startMonth || ''} onChange={(v) => updateListItem('experiences', i, 'startMonth', v)} />
												{!ex.isCurrent ? (
													<MonthYearPicker placeholder="End" value={ex.endMonth || ''} onChange={(v) => {
														updateListItem('experiences', i, 'endMonth', v)
														if (v) updateListItem('experiences', i, 'isCurrent', false)
													}} />
												) : (
													<div className="flex items-center text-zinc-300 border-b border-zinc-700">
														<span className="py-2.5">Present</span>
													</div>
												)}
												<label className="flex items-center gap-2 text-sm text-zinc-300 select-none">
													<input
														type="checkbox"
														className="accent-purple-500 w-4 h-4"
														checked={!!ex.isCurrent}
														onChange={(e) => {
															const val = e.target.checked
															updateListItem('experiences', i, 'isCurrent', val)
															if (val) updateListItem('experiences', i, 'endMonth', '')
														}}
													/>
													<span>Present</span>
												</label>
											</div>
											<div className="mt-3 flex justify-end">
												<button type="button" className="text-xs text-zinc-400 hover:text-red-400 transition-colors" onClick={() => removeListItem('experiences', i)}>Remove</button>
											</div>
										</motion.div>
									))}
								</div>
							</motion.div>

							{/* Action Buttons */}
							<motion.div
								initial={{ opacity: 0, y: 20 }}
								animate={{ opacity: 1, y: 0 }}
								transition={{ delay: 1.1 }}
								className="flex items-center justify-end gap-4 pt-4"
							>
							<PremiumButton
								type="submit"
								variant="secondary"
								icon={FiSave}
								onClick={(e) => {
									// Ensure the form submission is triggered
									console.log('DEBUG: Save button clicked')
								}}
							>
								Save
							</PremiumButton>
								<PremiumButton
									type="button"
									onClick={onComplete}
									variant="primary"
									icon={FiCheck}
								>
									Save & Complete
								</PremiumButton>
							</motion.div>
						</form>
					</div>
				</div>
			</motion.div>
		</section>
	)
}
