import { createContext, useContext } from 'react'
import { useApp } from './AppContext.jsx'
import { isCeo } from '../utils/rbac.js'

const OrgPanelContext = createContext({
  basePath: '/head-hr',
  readOnly: false,
})

export function OrgPanelProvider({ children, basePath, readOnly }) {
  return (
    <OrgPanelContext.Provider value={{ basePath, readOnly }}>
      {children}
    </OrgPanelContext.Provider>
  )
}

export function useOrgPanel() {
  const ctx = useContext(OrgPanelContext)
  const { auth } = useApp()
  if (ctx.basePath !== '/head-hr' || ctx.readOnly) {
    return ctx
  }
  if (isCeo(auth)) {
    return { basePath: '/ceo', readOnly: true }
  }
  return ctx
}

export default OrgPanelContext
