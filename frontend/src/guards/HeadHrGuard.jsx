import { Navigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'
import { isHeadHr } from '../utils/rbac.js'

export default function HeadHrGuard({ children }) {
  const { auth } = useApp()
  if (!auth.isLoggedIn || !isHeadHr(auth)) {
    return <Navigate to="/login/admin" replace />
  }
  return children
}
