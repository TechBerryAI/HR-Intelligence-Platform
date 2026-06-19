import { useEffect, useRef, useCallback } from 'react'
import { createHeroIllustrationEngine } from './heroIllustrationEngine'
import { createHeroAtmosphereEngine } from './heroAtmosphereEngine'

function getDeviceQuality() {
  if (typeof window === 'undefined') return 'high'
  const coarse = window.matchMedia('(pointer: coarse)').matches
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const narrow = window.innerWidth < 640
  if (reduced || coarse || narrow) return 'low'
  return 'high'
}

function getMaxDpr(quality) {
  return quality === 'low' ? 1 : Math.min(window.devicePixelRatio || 1, 2)
}

export function useHeroCanvas(containerRef, { landingMode = false } = {}) {
  const canvasRef = useRef(null)
  const illustrationRef = useRef(null)
  const atmosphereRef = useRef(null)
  const rafRef = useRef(0)
  const visibleRef = useRef(true)
  const qualityRef = useRef('high')
  const hoverBoostRef = useRef(false)

  const resize = useCallback(() => {
    const canvas = canvasRef.current
    const container = containerRef.current
    const illustration = illustrationRef.current
    const atmosphere = atmosphereRef.current
    if (!canvas || !container || !illustration || !atmosphere) return

    const rect = container.getBoundingClientRect()
    const cssW = Math.max(rect.width, 320)
    const cssH = Math.max(rect.height, 200)
    const quality = getDeviceQuality()
    qualityRef.current = quality
    const dpr = getMaxDpr(quality)

    illustration.setQuality(quality)
    atmosphere.setQuality(quality)
    illustration.resize(cssW, cssH)
    atmosphere.resize(cssW, cssH)

    canvas.width = Math.floor(cssW * dpr)
    canvas.height = Math.floor(cssH * dpr)
    canvas.style.width = `${cssW}px`
    canvas.style.height = `${cssH}px`

    const ctx = canvas.getContext('2d', { alpha: true })
    if (ctx) {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
  }, [containerRef])

  useEffect(() => {
    const canvas = canvasRef.current
    const container = containerRef.current
    if (!canvas || !container) return

    const illustration = createHeroIllustrationEngine()
    const atmosphere = createHeroAtmosphereEngine()
    illustrationRef.current = illustration
    atmosphereRef.current = atmosphere
    if (landingMode) {
      illustration.setShowLeftDecor(false)
      illustration.setLandingMode(true)
      atmosphere.setLandingMode(true)
    }

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const timeScale = reducedMotion ? 0.3 : 1
    illustration.setTimeScale(timeScale)
    atmosphere.setTimeScale(timeScale)

    resize()

    const observer = new IntersectionObserver(
      ([entry]) => {
        visibleRef.current = entry.isIntersecting
      },
      { threshold: 0.08 },
    )
    observer.observe(container)

    const ro = new ResizeObserver(() => resize())
    ro.observe(container)

    let frameSkip = 0
    const loop = () => {
      rafRef.current = requestAnimationFrame(loop)
      if (!visibleRef.current) return

      if (qualityRef.current === 'low') {
        frameSkip += 1
        if (frameSkip % 2 !== 0) return
      }

      const ctx = canvas.getContext('2d')
      const ill = illustrationRef.current
      const atm = atmosphereRef.current
      if (!ctx || !ill || !atm) return

      ill.setHoverBoost(hoverBoostRef.current)
      ill.render(ctx)
      ctx.save()
      ctx.globalCompositeOperation = 'screen'
      ctx.globalAlpha = landingMode ? 0.4 : 1
      atm.render(ctx)
      ctx.restore()
    }
    rafRef.current = requestAnimationFrame(loop)

    return () => {
      cancelAnimationFrame(rafRef.current)
      observer.disconnect()
      ro.disconnect()
      illustrationRef.current = null
      atmosphereRef.current = null
    }
  }, [containerRef, resize, landingMode])

  const handlePointerMove = useCallback(
    (event) => {
      const container = containerRef.current
      const illustration = illustrationRef.current
      const atmosphere = atmosphereRef.current
      if (!container || !illustration || !atmosphere) return

      const rect = container.getBoundingClientRect()
      const x = (event.clientX - rect.left) / rect.width
      const y = (event.clientY - rect.top) / rect.height
      illustration.setMouse(x, y)
      atmosphere.setMouse(x, y)
    },
    [containerRef],
  )

  const handlePointerLeave = useCallback(() => {
    illustrationRef.current?.setMouse(0.5, 0.5)
    atmosphereRef.current?.setMouse(0.5, 0.5)
    hoverBoostRef.current = false
  }, [])

  const setScrollProgress = useCallback((progress) => {
    illustrationRef.current?.setScrollProgress(progress)
    atmosphereRef.current?.setScrollProgress(progress)
  }, [])

  const setHoverBoost = useCallback((boost) => {
    hoverBoostRef.current = boost
  }, [])

  const hitTestAICore = useCallback((normX, normY) => {
    return illustrationRef.current?.hitTestAICore(normX, normY) ?? false
  }, [])

  const getQuality = useCallback(() => qualityRef.current, [])

  return {
    canvasRef,
    handlePointerMove,
    handlePointerLeave,
    setScrollProgress,
    setHoverBoost,
    hitTestAICore,
    getQuality,
  }
}
