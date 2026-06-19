import { useState, useEffect } from 'react'
import { useReducedMotion } from 'framer-motion'

function detectQuality() {
  if (typeof window === 'undefined') return 'high'
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const coarse = window.matchMedia('(pointer: coarse)').matches
  const narrow = window.innerWidth < 640
  const tablet = window.innerWidth < 1024
  const lowCores = navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 4

  if (reduced || lowCores) return 'low'
  if (coarse || narrow) return 'low'
  if (tablet) return 'medium'
  return 'high'
}

export function useSceneQuality() {
  const prefersReducedMotion = useReducedMotion()
  const [quality, setQuality] = useState(detectQuality)

  useEffect(() => {
    const update = () => setQuality(detectQuality())
    update()
    window.addEventListener('resize', update)
    const mq = window.matchMedia('(pointer: coarse)')
    mq.addEventListener('change', update)
    return () => {
      window.removeEventListener('resize', update)
      mq.removeEventListener('change', update)
    }
  }, [])

  const reducedMotion = !!prefersReducedMotion || quality === 'low'

  return { quality, reducedMotion }
}
