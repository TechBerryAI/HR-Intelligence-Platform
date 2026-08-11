import React from 'react'

/**
 * Premium brand monogram — charcoal mark, no accent glow / blue rings.
 * @param {{ size?: 'sm' | 'md' | 'lg', className?: string }} props
 */
export default function BrandMark({ size = 'md', className = '' }) {
  const dims =
    size === 'lg'
      ? { box: 'h-12 w-12', svg: 22 }
      : size === 'sm'
        ? { box: 'h-9 w-9', svg: 16 }
        : { box: 'h-10 w-10', svg: 18 }

  return (
    <span
      className={[
        'inline-flex items-center justify-center rounded-[11px]',
        'bg-[linear-gradient(155deg,#222c38_0%,#141b24_55%,#10161e_100%)]',
        'text-[#eef2f6]',
        'border border-white/[0.1]',
        'shadow-[inset_0_1px_0_rgba(255,255,255,0.12),0_1px_2px_rgba(0,0,0,0.35)]',
        dims.box,
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      aria-hidden="true"
    >
      <svg
        width={dims.svg}
        height={dims.svg}
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="block"
      >
        <path
          d="M6.5 4.75h2.35v5.85h6.3V4.75h2.35v14.5h-2.35v-6.4h-6.3v6.4H6.5V4.75Z"
          fill="currentColor"
        />
      </svg>
    </span>
  )
}
