import { useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { buildEnterTimeline } from '../transitions/buildEnterTimeline.js'

export function useEnterAppTransition({
  visualRef,
  overlayRef,
  uiRef,
  to = '/signup/applicant',
  state = { fromLanding: true },
}) {
  const navigate = useNavigate()
  const isTransitioningRef = useRef(false)

  const start = useCallback(() => {
    if (isTransitioningRef.current) return
    isTransitioningRef.current = true
    document.body.style.overflow = 'hidden'

    buildEnterTimeline({
      visualRef,
      overlayRef,
      uiRef,
      onComplete: () => {
        navigate(to, { state })
        document.body.style.overflow = ''
        isTransitioningRef.current = false
      },
    })
  }, [visualRef, overlayRef, uiRef, navigate, to, state])

  return { start, isTransitioning: isTransitioningRef }
}
