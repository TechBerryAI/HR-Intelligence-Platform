import React, { useState } from 'react'
import { FiEye, FiEyeOff } from 'react-icons/fi'

/**
 * Password input with show/hide toggle (eye icon).
 * Reserves space for the icon via padding-right so the eye is always visible.
 */
export default function PasswordInput({ className = '', style, ...props }) {
  const [visible, setVisible] = useState(false)
  return (
    <div className="relative">
      <input
        type={visible ? 'text' : 'password'}
        className={`w-full pr-10 ${className}`.trim()}
        style={{ paddingRight: '2.5rem', ...style }}
        {...props}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 focus:outline-none focus:text-white transition-colors p-1 rounded"
        tabIndex={-1}
        aria-label={visible ? 'Hide password' : 'Show password'}
      >
        {visible ? <FiEyeOff className="w-5 h-5" /> : <FiEye className="w-5 h-5" />}
      </button>
    </div>
  )
}
