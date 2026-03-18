import { cn } from '@/lib/utils.js'

function Skeleton({ className, ...props }) {
  return (
    <div
      className={cn('animate-pulse rounded-xl bg-slate-200', className)}
      {...props}
    />
  )
}

export { Skeleton }
