import { Navigate } from 'react-router-dom'
import { useApp } from '@/core/context/AppContext.jsx'
import { isCeo, isHeadHr } from '@/core/permissions/rbac.js'

export default function CeoGuard({ children }) {
  const { auth } = useApp()
  if (!auth.isLoggedIn) {
    return <Navigate to="/login/admin" replace />
  }
  if (isHeadHr(auth)) {
    return <Navigate to="/head-hr" replace />
  }
  if (!isCeo(auth)) {
    return <Navigate to="/login/admin" replace />
  }
  return children
}
