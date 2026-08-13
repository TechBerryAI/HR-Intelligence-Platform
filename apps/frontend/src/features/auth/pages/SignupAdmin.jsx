import React, { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import AuthPageLayout from '@/layouts/AuthPageLayout.jsx'

/**
 * Open recruiter self-signup is disabled for multi-tenant isolation.
 * Accounts are created by Head of HR within a company (or via platform provision).
 */
export default function SignupAdmin() {
  const navigate = useNavigate()
  const [acknowledged, setAcknowledged] = useState(false)

  return (
    <AuthPageLayout
      title="HR accounts by invitation"
      subtitle="Companies manage their own admins."
    >
      <div className="auth-glass-card">
        <h2 className="text-xl font-semibold text-[var(--ei-text-primary)]">
          Self-registration is closed
        </h2>
        <p className="mt-3 text-sm text-[var(--ei-text-secondary)] leading-relaxed">
          New companies are provisioned by a platform administrator. Recruiters and other
          admins are created by your company&apos;s Head of HR — ask them for an account
          instead of signing up here.
        </p>
        {!acknowledged ? (
          <button
            type="button"
            className="mt-6 w-full rounded-xl bg-[var(--ei-btn-primary-from)] text-[var(--ei-btn-primary-text)] py-2.5 text-sm font-medium"
            onClick={() => setAcknowledged(true)}
          >
            I understand
          </button>
        ) : (
          <div className="mt-6 space-y-3">
            <button
              type="button"
              className="w-full rounded-xl bg-[var(--ei-btn-primary-from)] text-[var(--ei-btn-primary-text)] py-2.5 text-sm font-medium"
              onClick={() => navigate('/login/admin')}
            >
              Go to admin login
            </button>
            <Link
              to="/"
              className="block text-center text-sm text-[var(--ei-text-muted)] hover:text-[var(--ei-text-primary)]"
            >
              Back to home
            </Link>
          </div>
        )}
        <p className="mt-6 text-xs text-[var(--ei-text-muted)]">
          Already have an account?{' '}
          <Link to="/login/admin" className="text-[var(--ei-text-secondary)] underline">
            Sign in
          </Link>
        </p>
      </div>
    </AuthPageLayout>
  )
}
