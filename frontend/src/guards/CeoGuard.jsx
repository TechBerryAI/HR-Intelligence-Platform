import { Navigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'
import { isCeo } from '../utils/rbac.js'

export default function CeoGuard({ children }) {
  const { auth } = useApp()
  if (!auth.isLoggedIn || !isCeo(auth)) {
    return <Navigate to="/login/admin" replace />
  }
  return children
}
