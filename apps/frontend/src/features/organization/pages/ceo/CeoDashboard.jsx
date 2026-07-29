import CeoLayout from './CeoLayout.jsx'
import OrgOverviewDashboard from '@/features/organization/pages/org/OrgOverviewDashboard.jsx'
import { OrgPanelProvider } from '@/core/context/OrgPanelContext.jsx'

export default function CeoDashboard() {
  return (
    <OrgPanelProvider basePath="/ceo" readOnly>
      <CeoLayout>
        <OrgOverviewDashboard variant="ceo" />
      </CeoLayout>
    </OrgPanelProvider>
  )
}
