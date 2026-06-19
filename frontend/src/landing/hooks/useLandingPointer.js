import { useState, useCallback } from 'react'

/** Normalized pointer 0–1; core hover when near viewport center */
export function useLandingPointer() {
  const [mouse, setMouse] = useState({ x: 0.5, y: 0.5 })
  const [hoverCore, setHoverCore] = useState(false)

  const hitTestCore = useCallback((normX, normY) => {
    const dx = normX - 0.5
    const dy = normY - 0.42
    const dist = Math.sqrt(dx * dx + dy * dy)
    return dist < 0.18
  }, [])

  const handlePointerMove = useCallback(
    (event) => {
      const x = event.clientX / window.innerWidth
      const y = event.clientY / window.innerHeight
      setMouse({ x, y })
      setHoverCore(hitTestCore(x, y))
    },
    [hitTestCore],
  )

  const handlePointerLeave = useCallback(() => {
    setMouse({ x: 0.5, y: 0.5 })
    setHoverCore(false)
  }, [])

  return { mouse, hoverCore, handlePointerMove, handlePointerLeave }
}
