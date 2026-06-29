import { useLocation } from 'react-router-dom'
import { OrgPanelProvider } from '../../context/OrgPanelContext.jsx'
import CeoLayout from '../ceo/CeoLayout.jsx'
import HeadHrLayout from '../head-hr/HeadHrLayout.jsx'

export function usePanelLayout() {
  const location = useLocation()
  return location.pathname.startsWith('/ceo') ? CeoLayout : HeadHrLayout
}

export function usePanelBasePath() {
  const location = useLocation()
  return location.pathname.startsWith('/ceo') ? '/ceo' : '/head-hr'
}

export function usePanelReadOnly() {
  const location = useLocation()
  return location.pathname.startsWith('/ceo')
}

export default function PanelShell({ children }) {
  const location = useLocation()
  const isCeo = location.pathname.startsWith('/ceo')
  const Layout = isCeo ? CeoLayout : HeadHrLayout
  const inner = isCeo ? (
    <OrgPanelProvider basePath="/ceo" readOnly>
      {children}
    </OrgPanelProvider>
  ) : (
    children
  )
  return <Layout>{inner}</Layout>
}
