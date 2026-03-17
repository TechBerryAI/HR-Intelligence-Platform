import { cn } from '@/lib/utils.js'

/**
 * Standard page container: max-w-7xl mx-auto px-6 py-10
 * Use inside MainLayout / DashboardLayout / AdminLayout.
 */
export function PageContainer({ className, children, ...props }) {
  return (
    <div className={cn('max-w-7xl mx-auto px-6 py-10', className)} {...props}>
      {children}
    </div>
  )
}
