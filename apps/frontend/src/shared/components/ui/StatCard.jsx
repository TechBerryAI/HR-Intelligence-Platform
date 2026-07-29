import React from 'react'
import { Card, CardContent } from './Card.jsx'
import { cn } from '@/shared/lib/utils.js'

/**
 * Stat card for dashboards: white background, clear metric and label.
 * Use grid: grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6
 */
export default function StatCard({ title, value, subtitle, icon: Icon, className }) {
  return (
    <Card className={cn('p-6 rounded-2xl', className)}>
      <CardContent className="p-0">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-slate-500">{title}</p>
            <p className="mt-1 text-3xl font-bold text-slate-900">{value ?? '—'}</p>
            {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
          </div>
          {Icon && (
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
              <Icon className="h-6 w-6" />
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
