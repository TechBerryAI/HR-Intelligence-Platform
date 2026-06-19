import React, { useRef, useState, useEffect, useCallback, Suspense, forwardRef, useImperativeHandle } from 'react'
import { useReducedMotion } from 'framer-motion'
import gsap from 'gsap'
import { useHeroCanvas } from '../../components/hero/useHeroCanvas.js'

const HeroScene3D = React.lazy(() => import('../../components/hero/HeroScene3D.jsx'))

function getInitialQuality() {
  if (typeof window === 'undefined') return 'high'
  const coarse = window.matchMedia('(pointer: coarse)').matches
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const narrow = window.innerWidth < 640
  if (reduced || coarse || narrow) return 'low'
  if (window.innerWidth < 1024) return 'medium'
  return 'high'
}

const LandingVisual = forwardRef(function LandingVisual(
  { scrollProgress = 0, frameloop = 'always', onPointerMove: onPointerMoveProp, onPointerLeave: onPointerLeaveProp },
  ref,
) {
  const containerRef = useRef(null)
  const shellRef = useRef(null)
  const prefersReducedMotion = useReducedMotion()
  const [mouse, setMouse] = useState({ x: 0.5, y: 0.5 })
  const [hoverBoost, setHoverBoost] = useState(false)
  const [quality, setQuality] = useState(getInitialQuality)
  const [sceneReady, setSceneReady] = useState(false)

  useImperativeHandle(ref, () => shellRef.current)

  const {
    canvasRef,
    handlePointerMove,
    handlePointerLeave,
    setScrollProgress,
    setHoverBoost: syncHoverBoost,
    hitTestAICore,
    getQuality,
  } = useHeroCanvas(containerRef, { landingMode: true })

  useEffect(() => {
    const mq = window.matchMedia('(pointer: coarse)')
    const update = () => setQuality(getQuality() || getInitialQuality())
    update()
    mq.addEventListener('change', update)
    window.addEventListener('resize', update)
    return () => {
      mq.removeEventListener('change', update)
      window.removeEventListener('resize', update)
    }
  }, [getQuality])

  useEffect(() => {
    setScrollProgress(scrollProgress)
  }, [scrollProgress, setScrollProgress])

  useEffect(() => {
    if (!shellRef.current || prefersReducedMotion) return
    const tl = gsap.fromTo(
      shellRef.current,
      { opacity: 0, scale: 1.02 },
      { opacity: 1, scale: 1, duration: 1.1, ease: 'power2.out' },
    )
    return () => tl.kill()
  }, [prefersReducedMotion])

  useEffect(() => {
    const timer = setTimeout(() => setSceneReady(true), 60)
    return () => clearTimeout(timer)
  }, [])

  const onPointerMove = useCallback(
    (e) => {
      handlePointerMove(e)
      const rect = containerRef.current?.getBoundingClientRect()
      if (!rect) return
      const x = (e.clientX - rect.left) / rect.width
      const y = (e.clientY - rect.top) / rect.height
      setMouse({ x, y })
      const boost = hitTestAICore(x, y)
      setHoverBoost(boost)
      syncHoverBoost(boost)
      onPointerMoveProp?.(e)
    },
    [handlePointerMove, hitTestAICore, syncHoverBoost, onPointerMoveProp],
  )

  const onPointerLeave = useCallback(() => {
    handlePointerLeave()
    setMouse({ x: 0.5, y: 0.5 })
    setHoverBoost(false)
    syncHoverBoost(false)
    onPointerLeaveProp?.()
  }, [handlePointerLeave, syncHoverBoost, onPointerLeaveProp])

  const sceneQuality = quality === 'medium' ? 'high' : quality

  return (
    <div
      ref={shellRef}
      className="fixed inset-0 will-change-transform"
      style={{ opacity: prefersReducedMotion ? 1 : 0 }}
    >
      <div
        ref={containerRef}
        className="absolute inset-0 bg-[#040c1e] cursor-crosshair touch-none"
        onPointerMove={onPointerMove}
        onPointerLeave={onPointerLeave}
        role="img"
        aria-label="Animated HRMS AI platform with workforce analytics dashboards, AI engine, resume parsing, and recruitment pipeline"
      >
        {sceneReady && !prefersReducedMotion && (
          <Suspense
            fallback={
              <div
                className="absolute inset-0 bg-gradient-to-br from-[#040c1e] via-[#071428] to-[#04101f]"
                aria-hidden
              />
            }
          >
            <div className="absolute inset-0 opacity-40">
              <HeroScene3D
                mouse={mouse}
                scrollProgress={scrollProgress}
                quality={sceneQuality}
                reducedMotion={!!prefersReducedMotion}
                hoverBoost={hoverBoost}
              />
            </div>
          </Suspense>
        )}

        <canvas ref={canvasRef} className="absolute inset-0 w-full h-full block pointer-events-none z-[2]" />

        <div className="absolute inset-0 pointer-events-none ring-1 ring-inset ring-white/5 z-[3]" aria-hidden />
        <div
          className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent pointer-events-none z-[3]"
          aria-hidden
        />
        <div
          className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-[#040c1e]/25 to-transparent pointer-events-none z-[3]"
          aria-hidden
        />
        <div
          className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-[#040c1e]/25 to-transparent pointer-events-none z-[3]"
          aria-hidden
        />
      </div>
    </div>
  )
})

export default LandingVisual
