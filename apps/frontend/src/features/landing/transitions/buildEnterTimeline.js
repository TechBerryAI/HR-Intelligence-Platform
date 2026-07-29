import gsap from 'gsap'

export function buildEnterTimeline({ visualRef, overlayRef, uiRef, onComplete }) {
  const tl = gsap.timeline({ onComplete })

  if (uiRef?.current) {
    tl.to(uiRef.current, { opacity: 0, y: -24, duration: 0.4, ease: 'power2.in' }, 0)
  }

  if (visualRef?.current) {
    tl.to(
      visualRef.current,
      {
        scale: 2.2,
        duration: 0.95,
        ease: 'power3.in',
        transformOrigin: '50% 50%',
      },
      0.08,
    )
    tl.to(visualRef.current, { opacity: 0.15, duration: 0.45, ease: 'power2.in' }, 0.35)
  }

  if (overlayRef?.current) {
    tl.to(overlayRef.current, { opacity: 1, duration: 0.55, ease: 'power2.in' }, 0.48)
  }

  return tl
}
