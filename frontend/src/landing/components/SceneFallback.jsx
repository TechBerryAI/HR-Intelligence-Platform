import React from 'react'

export default function SceneFallback() {
  return (
    <div className="fixed inset-0 bg-[#040c1e]" aria-hidden>
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_70%_55%_at_60%_50%,rgba(0,120,255,0.14),transparent)]" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_50%_40%_at_38%_36%,rgba(0,180,255,0.18),transparent)]" />
      <div
        className="absolute inset-0 opacity-[0.08]"
        style={{
          backgroundImage:
            'linear-gradient(rgba(30,80,160,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(30,80,160,0.5) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />
      <div className="absolute top-[36%] left-[38%] -translate-x-1/2 -translate-y-1/2 w-20 h-20 rounded-full bg-blue-500/30 blur-xl" />
      <div className="absolute top-[50%] left-[60%] -translate-x-1/2 -translate-y-1/2 w-64 h-40 rounded-2xl border border-blue-400/20 bg-blue-900/20 backdrop-blur-sm" />
    </div>
  )
}
