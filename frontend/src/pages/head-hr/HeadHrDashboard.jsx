import HeadHrLayout from './HeadHrLayout.jsx'
import OrgOverviewDashboard from '../org/OrgOverviewDashboard.jsx'

export default function HeadHrDashboard() {
  return (
    <HeadHrLayout>
      <OrgOverviewDashboard variant="head-hr" showJobPosting />
    </HeadHrLayout>
  )
}
