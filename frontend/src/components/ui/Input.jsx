import * as React from 'react'
import { cn } from '@/lib/utils.js'

const Input = React.forwardRef(({ className, type, ...props }, ref) => (
  <input
    type={type}
      className={cn(
      'block h-12 min-h-[3rem] w-full box-border appearance-none rounded-xl border border-slate-200 bg-white px-4 text-base leading-normal text-slate-900 placeholder:text-slate-500',
      'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-0 focus:border-blue-500',
      'disabled:cursor-not-allowed disabled:opacity-50',
      className
    )}
    ref={ref}
    {...props}
  />
))
Input.displayName = 'Input'

export { Input }
