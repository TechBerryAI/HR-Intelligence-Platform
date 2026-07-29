import React, { forwardRef } from 'react'

const TransitionOverlay = forwardRef(function TransitionOverlay(_, ref) {
  return (
    <div
      ref={ref}
      className="fixed inset-0 z-[100] pointer-events-none opacity-0"
      style={{
        background:
          'radial-gradient(ellipse at center, rgba(34,211,238,0.95) 0%, rgba(59,130,246,0.9) 40%, rgba(2,6,23,1) 100%)',
      }}
      aria-hidden
    />
  )
})

export default TransitionOverlay
