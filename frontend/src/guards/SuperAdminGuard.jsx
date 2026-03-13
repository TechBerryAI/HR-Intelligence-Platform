import { Navigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'

export default function SuperAdminGuard({ children }) {
  const { superAdminAuth } = useApp()
  if (!superAdminAuth?.isLoggedIn) {
    return <Navigate to="/login/admin" replace />
  }
  return children
}
