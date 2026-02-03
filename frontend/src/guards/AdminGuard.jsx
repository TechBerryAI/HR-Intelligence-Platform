/**
 * Role guard: only Admin (HR) can access. Redirects others to login.
 */
import { Navigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'

export default function AdminGuard({ children }) {
  const { auth } = useApp()
  if (!auth.isLoggedIn || auth.role !== 'HR') {
    return <Navigate to="/login/admin" replace />
  }
  return children
}
