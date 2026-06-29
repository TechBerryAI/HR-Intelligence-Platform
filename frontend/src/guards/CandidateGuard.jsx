/**
 * Role guard: only Candidate (Applicant) can access. Redirects others to applicant login.
 */
import { Navigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'

import { isStaffRecruiter, isCeo } from '../utils/rbac.js'

export default function CandidateGuard({ children }) {
  const { applicantAuth, auth } = useApp()
  const isStaff = auth?.isLoggedIn && isStaffRecruiter(auth)
  const isCeoUser = auth?.isLoggedIn && isCeo(auth)
  const isCandidate = applicantAuth?.isLoggedIn && !isStaff && !isCeoUser
  if (!isCandidate) {
    return <Navigate to="/login/applicant" replace />
  }
  return children
}
