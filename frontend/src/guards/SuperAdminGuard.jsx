import { Navigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'

export default function SuperAdminGuard({ children }) {
  const { superAdminAuth, auth } = useApp()
  const canAccess = superAdminAuth?.isLoggedIn || (auth?.isLoggedIn && auth?.role === 'head_hr')
  if (!canAccess) {
    return <Navigate to="/login/super-admin" replace />
  }
  return children
}
