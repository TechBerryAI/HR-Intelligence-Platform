/**
 * Recruiter routes only. HEAD_HR and CEO are redirected to their dashboards.
 */
import { Navigate } from 'react-router-dom'
import { useApp } from '@/core/context/AppContext.jsx'
import { ROLES, getRole } from '@/core/permissions/rbac.js'

export default function RecruiterGuard({ children }) {
  const { auth } = useApp()
  const role = getRole(auth)
  if (!auth.isLoggedIn) {
    return <Navigate to="/login/admin" replace />
  }
  if (role === ROLES.HEAD_HR) {
    return <Navigate to="/head-hr" replace />
  }
  if (role === ROLES.CEO) {
    return <Navigate to="/ceo" replace />
  }
  if (role !== ROLES.RECRUITER) {
    return <Navigate to="/login/admin" replace />
  }
  return children
}
