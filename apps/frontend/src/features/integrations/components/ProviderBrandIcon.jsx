import React from 'react'
import { FaLinkedin } from 'react-icons/fa'
import { FiGlobe } from 'react-icons/fi'
import naukriLogo from '@/features/integrations/assets/naukri-logo.png'

/**
 * Official Naukri brand icon (app tile).
 */
export function NaukriIcon({ className = 'w-5 h-5', title = 'Naukri' }) {
  return (
    <img
      src={naukriLogo}
      alt={title}
      title={title}
      className={`rounded-[20%] object-cover ${className}`}
      draggable={false}
    />
  )
}

/**
 * Provider brand icon for integrations UI (Settings, dashboard, publish strip).
 */
export default function ProviderBrandIcon({ provider, className = 'w-5 h-5' }) {
  const key = String(provider || '')
    .trim()
    .toLowerCase()

  if (key === 'linkedin') {
    return (
      <FaLinkedin
        className={className}
        color="#0A66C2"
        aria-label="LinkedIn"
        title="LinkedIn"
      />
    )
  }

  if (key === 'naukri') {
    return <NaukriIcon className={className} />
  }

  return <FiGlobe className={className} aria-hidden />
}
