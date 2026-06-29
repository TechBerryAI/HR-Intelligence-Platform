import CeoLayout from './CeoLayout.jsx'
import OrgOverviewDashboard from '../org/OrgOverviewDashboard.jsx'
import { OrgPanelProvider } from '../../context/OrgPanelContext.jsx'

export default function CeoDashboard() {
  return (
    <OrgPanelProvider basePath="/ceo" readOnly>
      <CeoLayout>
        <OrgOverviewDashboard variant="ceo" />
      </CeoLayout>
    </OrgPanelProvider>
  )
}
