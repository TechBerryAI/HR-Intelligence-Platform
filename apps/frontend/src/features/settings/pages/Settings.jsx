import React, { useState } from 'react'
import { useApp } from '@/core/context/AppContext.jsx'
import PremiumInput from '@/shared/components/PremiumInput.jsx'
import PremiumButton from '@/shared/components/PremiumButton.jsx'
import { motion } from 'framer-motion'
import { FiSettings, FiShield, FiLock, FiCheck, FiAlertCircle, FiX } from 'react-icons/fi'
import { PASSWORD_RULES, isPasswordStrong } from '@/shared/utils/passwordValidation.js'

/**
 * @param {'default' | 'enterprise'} [theme]
 * enterprise = Head HR / CEO org shell (dark glass). default = light staff settings.
 */
export default function Settings({ theme = 'default' }) {
  const { changePasswordHr } = useApp()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState({ type: '', text: '' })

  const enterprise = theme === 'enterprise'
  const changePassword = changePasswordHr

  const newPasswordValid = isPasswordStrong(newPassword)
  const confirmMatches = newPassword && newPassword === confirmPassword
  const canSubmit = currentPassword.trim() && newPasswordValid && confirmMatches && !loading

  const handleChangePassword = async (e) => {
    e.preventDefault()
    setMessage({ type: '', text: '' })
    if (!currentPassword.trim()) {
      setMessage({ type: 'error', text: 'Please enter your current password.' })
      return
    }
    if (!newPasswordValid) {
      setMessage({ type: 'error', text: 'New password must meet all requirements below.' })
      return
    }
    if (newPassword !== confirmPassword) {
      setMessage({ type: 'error', text: 'New password and confirmation do not match.' })
      return
    }
    setLoading(true)
    const res = await changePassword({ currentPassword: currentPassword.trim(), newPassword: newPassword.trim() })
    setLoading(false)
    if (res.ok) {
      setMessage({ type: 'success', text: 'Password updated successfully.' })
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } else {
      setMessage({ type: 'error', text: res.message || 'Failed to change password.' })
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8"
      >
        {enterprise ? (
          <>
            <h1 className="org-page-title flex items-center gap-3">
              <FiSettings className="w-7 h-7 text-[#00A6FF]" />
              Settings
            </h1>
            <p className="org-page-subtitle">Manage your account and security.</p>
          </>
        ) : (
          <>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
              <FiSettings className="w-7 h-7 text-primary" />
              Settings
            </h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Manage your account and security.
            </p>
          </>
        )}
      </motion.div>

      <motion.section
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className={
          enterprise
            ? 'org-card overflow-hidden'
            : 'rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 shadow-premium overflow-hidden'
        }
      >
        <div
          className={
            enterprise
              ? 'px-6 py-4 border-b border-white/[0.08] bg-white/[0.03] flex items-center gap-3'
              : 'px-6 py-4 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 flex items-center gap-3'
          }
        >
          <FiShield className={`w-5 h-5 ${enterprise ? 'text-[#00A6FF]' : 'text-primary'}`} />
          <h2
            className={
              enterprise
                ? 'text-lg font-semibold text-[#F5F7FA]'
                : 'text-lg font-semibold text-slate-900 dark:text-white'
            }
          >
            Security
          </h2>
        </div>

        <div className="p-6">
          <h3
            className={
              enterprise
                ? 'text-sm font-medium text-[#DCE3EA] mb-4 flex items-center gap-2'
                : 'text-sm font-medium text-slate-700 dark:text-slate-300 mb-4 flex items-center gap-2'
            }
          >
            <FiLock className="w-4 h-4" />
            Change password
          </h3>
          <p
            className={
              enterprise
                ? 'text-sm text-[#A0ABB6] mb-4 leading-relaxed'
                : 'text-sm text-slate-500 dark:text-slate-400 mb-4'
            }
          >
            Enter your current password and choose a new one. The new password must meet all requirements below.
          </p>

          <ul className="mb-5 space-y-2">
            {PASSWORD_RULES.map(({ id, label, test }) => {
              const pass = test(newPassword)
              return (
                <li key={id} className="flex items-center gap-2 text-sm">
                  {pass ? (
                    <FiCheck
                      className={`w-4 h-4 flex-shrink-0 ${enterprise ? 'text-[#36D6A0]' : 'text-green-600 dark:text-green-400'}`}
                      aria-hidden
                    />
                  ) : (
                    <FiX
                      className={`w-4 h-4 flex-shrink-0 ${enterprise ? 'text-[#71808E]' : 'text-slate-400'}`}
                      aria-hidden
                    />
                  )}
                  <span
                    className={
                      pass
                        ? enterprise
                          ? 'text-[#DCE3EA]'
                          : 'text-slate-700 dark:text-slate-300'
                        : enterprise
                          ? 'text-[#8E9BA8]'
                          : 'text-slate-500'
                    }
                  >
                    {label}
                  </span>
                </li>
              )
            })}
          </ul>

          {message.text && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              className={`mb-5 flex items-center gap-3 px-4 py-3 rounded-xl text-sm ${
                message.type === 'success'
                  ? enterprise
                    ? 'bg-[rgba(54,214,160,0.1)] border border-[rgba(54,214,160,0.28)] text-[#67DFB4]'
                    : 'bg-green-50 dark:bg-green-500/10 border border-green-200 dark:border-green-500/30 text-green-700 dark:text-green-300'
                  : enterprise
                    ? 'bg-[rgba(255,102,133,0.1)] border border-[rgba(255,90,110,0.4)] text-[#FF7B8E]'
                    : 'bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 text-red-700 dark:text-red-300'
              }`}
            >
              {message.type === 'success' ? (
                <FiCheck className="w-5 h-5 flex-shrink-0" />
              ) : (
                <FiAlertCircle className="w-5 h-5 flex-shrink-0" />
              )}
              <span>{message.text}</span>
            </motion.div>
          )}

          <form onSubmit={handleChangePassword} className="space-y-5">
            <PremiumInput
              label="Current password"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
              icon={FiLock}
            />
            <PremiumInput
              label="New password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Meet all requirements above"
              autoComplete="new-password"
              icon={FiLock}
            />
            <PremiumInput
              label="Confirm new password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete="new-password"
              icon={FiLock}
            />
            {enterprise ? (
              <button
                type="submit"
                disabled={!canSubmit}
                className="org-btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Updating…' : 'Update password'}
              </button>
            ) : (
              <PremiumButton
                type="submit"
                variant="primary"
                loading={loading}
                disabled={!canSubmit}
              >
                {loading ? 'Updating…' : 'Update password'}
              </PremiumButton>
            )}
          </form>
        </div>
      </motion.section>
    </div>
  )
}
