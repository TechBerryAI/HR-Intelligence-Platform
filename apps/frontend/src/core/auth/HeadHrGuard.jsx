import { Navigate } from 'react-router-dom'
import { useApp } from '@/core/context/AppContext.jsx'
import { isHeadHr, isCeo } from '@/core/permissions/rbac.js'

export default function HeadHrGuard({ children }) {
  const { auth } = useApp()
  if (!auth.isLoggedIn) {
    return <Navigate to="/login/admin" replace />
  }
  if (isCeo(auth)) {
    return <Navigate to="/ceo" replace />
  }
  if (!isHeadHr(auth)) {
    return <Navigate to="/login/admin" replace />
  }
  return children
}
