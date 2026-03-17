import * as React from 'react'
import { cva } from 'class-variance-authority'
import { cn } from '@/lib/utils.js'

const badgeVariants = cva(
  'inline-flex items-center rounded-lg border px-2.5 py-0.5 text-xs font-medium transition-colors',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-slate-100 text-slate-900',
        secondary: 'border-transparent bg-slate-100 text-slate-600',
        destructive: 'border-transparent bg-red-50 text-red-700 border-red-200',
        outline: 'text-slate-900 border-slate-200',
        success: 'border-transparent bg-emerald-50 text-emerald-700 border-emerald-200',
        warning: 'border-transparent bg-amber-50 text-amber-700 border-amber-200',
        blue: 'border-transparent bg-blue-50 text-blue-700 border-blue-200',
        accent: 'border-transparent bg-blue-50 text-blue-700 border-blue-200',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
)

function Badge({ className, variant, ...props }) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
