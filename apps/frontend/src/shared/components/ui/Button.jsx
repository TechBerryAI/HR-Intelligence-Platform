import * as React from 'react'

const variantClasses = {
  default: 'bg-blue-600 text-white shadow-sm hover:bg-blue-700 hover:shadow-md',
  destructive: 'bg-red-600 text-white hover:bg-red-700',
  outline: 'border border-slate-200 bg-white text-slate-900 hover:bg-slate-50',
  secondary: 'bg-slate-100 text-slate-900 hover:bg-slate-200',
  ghost: 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
  link: 'text-blue-600 underline-offset-4 hover:underline',
}

const sizeClasses = {
  default: 'h-10 px-5 py-2',
  sm: 'h-9 rounded-lg px-3',
  lg: 'h-11 rounded-xl px-8',
  icon: 'h-10 w-10',
}

const baseClasses = 'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0'

const Button = React.forwardRef(({ className, variant = 'default', size = 'default', asChild = false, ...props }, ref) => {
  const classes = `${baseClasses} ${variantClasses[variant] || variantClasses.default} ${sizeClasses[size] || sizeClasses.default} ${className || ''}`.trim()
  if (asChild && props.children) {
    const child = React.Children.only(props.children)
    return React.cloneElement(child, { ...child.props, className: `${child.props.className || ''} ${classes}`.trim(), ref: ref ?? child.ref })
  }
  return <button ref={ref} className={classes} {...props} />
})
Button.displayName = 'Button'

export { Button, variantClasses as buttonVariants }
