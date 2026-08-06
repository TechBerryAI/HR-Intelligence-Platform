import React, { useState } from 'react'
import { FaLinkedin } from 'react-icons/fa'
import { FiGlobe } from 'react-icons/fi'

/**
 * Official Naukri brand mark as inline SVG (no binary assets in the repo).
 * App-tile style: #0B66FF square, white circle head, folded ribbon figure.
 */
export function NaukriIcon({ className = 'w-5 h-5', title = 'Naukri' }) {
  return (
    <svg
      viewBox="0 0 48 48"
      className={className}
      role="img"
      aria-label={title}
      xmlns="http://www.w3.org/2000/svg"
    >
      <title>{title}</title>
      <rect width="48" height="48" rx="10" fill="#0B66FF" />
      <g transform="translate(24 25) scale(0.92) translate(-24 -25)">
        <circle cx="18" cy="12.5" r="5" fill="#FFFFFF" />
        <path
          fill="#FFFFFF"
          fillRule="evenodd"
          d="M12.5 20.5c0-1.1.8-2 1.9-2.2 5.2-.9 11.8.6 15.5 4.2 1.1 1.1.4 2.9-1.1 3-3.1.2-5.9-1.2-8.5-2.7-2.1-1.2-4.4-1.6-6.6-.8-1 .3-1.9-.5-1.9-1.5h.7zm13.2 5.2c2.1 1.8 3.5 4.5 3.2 7.5-.4 4.1-3.3 7.3-7.2 8.6-1 .3-2-.5-2-1.5v-2.8c0-.6.4-1.1.9-1.3 2.4-1.1 4-3.2 4.2-5.6.2-1.8-.5-3.4-1.7-4.5-.6-.6-.4-1.6.4-1.9l1.8-.8c.5-.2 1.1 0 1.4.5z
             M15.5 24c1.5 2.5 4.1 7.2 5.6 11.5.5 1.4.8 2.5.9 3.2.2.9-.5 1.7-1.4 1.8l-2.9.4c-.9.1-1.7-.6-1.8-1.5-.5-2.5-1.8-6.6-3.6-10.5-1.2-2.6-2.5-4.8-3.4-5.9-.5-.7.1-1.7 1-1.9l3.5-1.1c.7-.2 1.4.2 1.7.9.1.3.2.6.2.8z"
        />
        <path
          fill="#8EC2FF"
          d="M24.8 27.2c1.1 1 1.7 2.6 1.6 4.3-.1 1.8-1.1 3.4-2.5 4.3-.5.3-1.2 0-1.3-.6l-.5-2.2c-.1-.4.1-.7.4-.9.9-.7 1.4-1.7 1.5-2.8.1-.8-.2-1.5-.6-2.1-.3-.4-.1-1 .3-1.2l.7-.4c.6-.3 1.2 0 1.4.7v.9z"
        />
      </g>
    </svg>
  )
}

function isHttpsLogoUrl(url) {
  if (!url || typeof url !== 'string') return false
  try {
    const u = new URL(url.trim())
    return u.protocol === 'https:'
  } catch {
    return false
  }
}

function RemoteLogo({ url, className, title }) {
  const [failed, setFailed] = useState(false)
  if (failed || !isHttpsLogoUrl(url)) {
    return <FiGlobe className={className} aria-hidden />
  }
  return (
    <img
      src={url.trim()}
      alt={title || 'Provider'}
      title={title}
      className={`rounded-[20%] object-cover ${className}`}
      draggable={false}
      onError={() => setFailed(true)}
    />
  )
}

/**
 * Provider brand icon for integrations UI (Settings, dashboard, publish strip).
 * Built-ins: inline SVG / react-icons. Customs: optional HTTPS logoUrl, else globe.
 */
export default function ProviderBrandIcon({
  provider,
  className = 'w-5 h-5',
  logoUrl,
  title,
}) {
  const key = String(provider || '')
    .trim()
    .toLowerCase()

  if (key === 'linkedin') {
    return (
      <FaLinkedin
        className={className}
        color="#0A66C2"
        aria-label="LinkedIn"
        title={title || 'LinkedIn'}
      />
    )
  }

  if (key === 'naukri') {
    return <NaukriIcon className={className} title={title || 'Naukri'} />
  }

  if (isHttpsLogoUrl(logoUrl)) {
    return <RemoteLogo url={logoUrl} className={className} title={title || key || 'Provider'} />
  }

  return <FiGlobe className={className} aria-hidden />
}
