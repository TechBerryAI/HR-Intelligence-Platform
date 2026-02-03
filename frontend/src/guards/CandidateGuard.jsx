/**
 * Role guard: only Candidate (Applicant) can access. Redirects others to applicant login.
 */
import { Navigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'

export default function CandidateGuard({ children }) {
  const { applicantAuth, auth } = useApp()
  const isHr = auth?.isLoggedIn && auth?.role === 'HR'
  const isCandidate = applicantAuth?.isLoggedIn && !isHr
  if (!isCandidate) {
    return <Navigate to="/login/applicant" replace />
  }
  return children
}
