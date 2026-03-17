import React from 'react'

export default function SkeletonLoader({ className = '', ...props }) {
  return (
    <div
      className={`animate-pulse rounded-xl bg-slate-200 dark:bg-slate-700 ${className}`}
      {...props}
    />
  )
}

export function SkeletonCard() {
  return (
    <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/80 p-6">
      <div className="flex items-start gap-4">
        <SkeletonLoader className="w-12 h-12 rounded-xl" />
        <div className="flex-1 space-y-2">
          <SkeletonLoader className="h-5 w-3/4" />
          <SkeletonLoader className="h-4 w-1/2" />
          <SkeletonLoader className="h-4 w-full" />
          <SkeletonLoader className="h-4 w-2/3" />
        </div>
      </div>
    </div>
  )
}

export function SkeletonList({ count = 3 }) {
  return (
    <div className="space-y-4">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  )
}
