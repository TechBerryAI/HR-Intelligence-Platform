import React, { useMemo, useRef, useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'
import { useToast } from '../components/Toast.jsx'
import MonthYearPicker from '../components/MonthYearPicker.jsx'
import ResumeUploadWithParsing from '../components/ResumeUploadWithParsing.jsx'
import PremiumInput from '../components/PremiumInput.jsx'
import PremiumButton from '../components/PremiumButton.jsx'
import { motion, AnimatePresence } from 'framer-motion'
import { FiUser, FiMail, FiPhone, FiMapPin, FiLinkedin, FiGlobe, FiSave, FiCheck, FiAlertCircle } from 'react-icons/fi'

export default function ApplicantProfile() {
	const { applicantProfile, saveApplicantProfile, markApplicantProfileCompleted, applyToJobAsApplicant, fetchApplicantData, applicantSavedJobs, toggleSaveJob } = useApp()
	const navigate = useNavigate()
	const location = useLocation()
	const toast = useToast()
  const firstErrorRef = useRef(null)
  const fileInputRef = useRef(null)

	const [form, setForm] = useState({
		experienceLevel: applicantProfile.experienceLevel || '',
		servingNotice: applicantProfile.servingNotice || '',
		noticePeriod: applicantProfile.noticePeriod || '',
		lastWorkingDay: applicantProfile.lastWorkingDay || '',
		fullName: applicantProfile.fullName || '',
		email: applicantProfile.email || '',
		phone: applicantProfile.phone || '',
		linkedinUrl: applicantProfile.linkedinUrl || '',
		portfolioUrl: applicantProfile.portfolioUrl || '',
		currentLocation: applicantProfile.currentLocation || '',
		preferredLocation: applicantProfile.preferredLocation || '',
		resumeFile: null,
		resumeFileName: applicantProfile.resumeFileName || '',
		education: applicantProfile.education.length ? applicantProfile.education : [{ degree: '', institution: '', cgpa: '', startMonth: '', endMonth: '' }],
		certifications: applicantProfile.certifications && applicantProfile.certifications.length ? applicantProfile.certifications : [{ name: '', issuer: '', validTill: '', validationUrl: '', status: '' }],
		experiences: applicantProfile.experiences.length ? applicantProfile.experiences : [{ company: '', role: '', startMonth: '', endMonth: '', isCurrent: false }],
	})
	const [saved, setSaved] = useState('')
	const [errors, setErrors] = useState({})
	const [autofilledFields, setAutofilledFields] = useState({})
	
	useEffect(() => {
		if (applicantProfile.resumeFileName) {
			if (!form.resumeFile) {
				updateField('resumeFileName', applicantProfile.resumeFileName)
			}
		}
	}, [applicantProfile.resumeFileName])

	const validate = (f) => {
		const e = {}
		if (!f.fullName?.trim()) e.fullName = 'Full name is required'
		if (!f.email?.trim()) e.email = 'Email is required'
		if (!f.phone?.trim()) e.phone = 'Phone is required'
		if (!f.currentLocation?.trim()) e.currentLocation = 'Current location is required'
		if (!f.preferredLocation?.trim()) e.preferredLocation = 'Preferred location is required'
		if (!f.resumeFileName) e.resumeFileName = 'Resume is required'
		
		const hasEducation = Array.isArray(f.education) && f.education.some(ed => ed.degree?.trim() && ed.institution?.trim())
		if (!hasEducation) {
			e.education = 'At least one education entry with Degree and Institution is required'
		} else {
			const has10th = f.education.some(ed => 
				ed.degree?.toLowerCase().includes('10') || 
				ed.degree?.toLowerCase().includes('tenth') || 
				ed.degree?.toLowerCase().includes('ssc') ||
				ed.degree?.toLowerCase().includes('secondary')
			)
			const has12thOrDiploma = f.education.some(ed => 
				ed.degree?.toLowerCase().includes('12') || 
				ed.degree?.toLowerCase().includes('twelfth') || 
				ed.degree?.toLowerCase().includes('hsc') ||
				ed.degree?.toLowerCase().includes('senior secondary') ||
				ed.degree?.toLowerCase().includes('diploma') ||
				ed.degree?.toLowerCase().includes('intermediate')
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
		
		setAutofilledFields(autofilled);
		
		// Merge parsed data with existing form
		setForm((prevForm) => ({
			...prevForm,
			fullName: parsedData.fullName || prevForm.fullName,
			email: parsedData.email || prevForm.email,
			phone: parsedData.phone || prevForm.phone,
			experienceLevel: parsedData.experienceLevel || prevForm.experienceLevel,
			education: parsedData.education && parsedData.education.length > 0 ? parsedData.education : prevForm.education,
			experiences: parsedData.experiences && parsedData.experiences.length > 0 ? parsedData.experiences : prevForm.experiences,
			certifications: parsedData.certifications && parsedData.certifications.length > 0 ? parsedData.certifications : prevForm.certifications,
			resumeFile: parsedData.resumeFile || prevForm.resumeFile,
			resumeFileName: parsedData.resumeFileName || prevForm.resumeFileName,
		}));
		
		setErrors({});
		
		// Clear autofill indicators after 3 seconds
		setTimeout(() => {
			setAutofilledFields({});
		}, 3000);
		
		window.scrollTo({ top: 0, behavior: 'smooth' });
	}

	const onSave = async (e) => {
		e.preventDefault()
		const result = await saveApplicantProfile(form)
		if (result.ok) {
			setSaved('Profile saved')
			toast.push('Profile saved successfully! You can come back and complete it later.', { type: 'success', duration: 5000 })
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
			}
		} else {
			toast.push('Failed to save profile. Please try again.', { type: 'error', duration: 4000 })
		}
	}

	const onComplete = async (e) => {
		e.preventDefault()
		const eMap = validate(form)
		setErrors(eMap)
		if (Object.keys(eMap).length > 0) {
			if (firstErrorRef.current) firstErrorRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' })
			return
		}
		const saveResult = await saveApplicantProfile(form)
		
		if (fileInputRef.current) {
			fileInputRef.current.value = ''
		}
		
		if (form.resumeFile) {
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

						<form onSubmit={onSave} className="mt-8 space-y-8">
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
													<option value="">Select</option>
													<option>Immediate</option>
													<option>&lt; 30 days</option>
													<option>&lt; 45 days</option>
													<option>&lt; 60 days</option>
													<option>&lt; 90 days</option>
													<option>Serving Notice Period</option>
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
												>
													<option value="">Status</option>
													<option value="completed">Completed</option>
													<option value="pursuing">Pursuing</option>
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
								>
									Save
								</PremiumButton>
								<PremiumButton
									type="button"
									onClick={onComplete}
									disabled={!isComplete}
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
