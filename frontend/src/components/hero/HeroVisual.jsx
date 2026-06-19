import React, { useRef, useState, useEffect, useCallback, Suspense } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import gsap from 'gsap'
import { useHeroCanvas } from './useHeroCanvas'

const HeroScene3D = React.lazy(() => import('./HeroScene3D.jsx'))

const chipVariants = {
  hidden: { opacity: 0, y: 12 },
  visible: (delay) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.55, delay, ease: [0.22, 1, 0.36, 1] },
  }),
}

function getInitialQuality() {
  if (typeof window === 'undefined') return 'high'
  const coarse = window.matchMedia('(pointer: coarse)').matches
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const narrow = window.innerWidth < 640
  if (reduced || coarse || narrow) return 'low'
  return 'high'
}

export default function HeroVisual() {
  const containerRef = useRef(null)
  const shellRef = useRef(null)
  const prefersReducedMotion = useReducedMotion()
  const [mouse, setMouse] = useState({ x: 0.5, y: 0.5 })
  const [scrollProgress, setScrollProgressState] = useState(0)
  const [hoverBoost, setHoverBoost] = useState(false)
  const [quality, setQuality] = useState(getInitialQuality)
  const [sceneReady, setSceneReady] = useState(false)

  const {
    canvasRef,
    handlePointerMove,
    handlePointerLeave,
    setScrollProgress,
    setHoverBoost: syncHoverBoost,
    hitTestAICore,
    getQuality,
  } = useHeroCanvas(containerRef)

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
    if (!shellRef.current || prefersReducedMotion) return
    const tl = gsap.timeline({ delay: 0.08 })
    tl.fromTo(
      shellRef.current,
      { opacity: 0, scale: 0.96 },
      {
        opacity: 1,
        scale: 1,
        duration: 0.9,
        ease: 'power2.out',
      },
    )
    return () => tl.kill()
  }, [prefersReducedMotion])

  useEffect(() => {
    const onScroll = () => {
      const el = containerRef.current
      if (!el) return
      const rect = el.getBoundingClientRect()
      // 0 when hero is in view at the top; increases as the user scrolls past it
      const scrolled = -rect.top
      const progress = Math.min(1, Math.max(0, scrolled / Math.max(rect.height, 1)))
      setScrollProgressState(progress)
      setScrollProgress(progress)
    }
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [setScrollProgress])

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
    },
    [handlePointerMove, hitTestAICore, syncHoverBoost],
  )

  return (
    <div className="relative w-full max-w-xl mx-auto lg:max-w-none lg:mx-0 pb-2">
      <div
        className="absolute -inset-6 sm:-inset-8 rounded-[2rem] sm:rounded-[2.5rem] bg-gradient-to-br from-accent-blue/30 via-primary/12 to-cyan-500/25 blur-3xl opacity-95 pointer-events-none"
        aria-hidden
      />
      <div
        className="absolute top-1/4 -left-4 w-36 h-36 rounded-full bg-accent-blue/35 blur-2xl pointer-events-none"
        aria-hidden
        style={{ animation: prefersReducedMotion ? undefined : 'heroPulse 4s ease-in-out infinite' }}
      />
      <div className="absolute bottom-4 right-0 w-44 h-44 rounded-full bg-cyan-400/18 blur-2xl pointer-events-none" aria-hidden />

      <div
        ref={shellRef}
        className="relative rounded-2xl sm:rounded-3xl overflow-hidden border border-slate-700/50 dark:border-slate-600/40 shadow-premium dark:shadow-premium-dark will-change-transform"
        style={{ opacity: prefersReducedMotion ? 1 : 0 }}
      >
        <div
          ref={containerRef}
          className="relative w-full aspect-[900/580] min-h-[220px] sm:min-h-[320px] bg-[#040c1e] cursor-crosshair touch-none"
          onPointerMove={onPointerMove}
          onPointerLeave={() => {
            handlePointerLeave()
            setMouse({ x: 0.5, y: 0.5 })
            setHoverBoost(false)
            syncHoverBoost(false)
          }}
          role="img"
          aria-label="Animated HRMS AI platform visualization with workforce analytics, neural engine, and recruitment pipeline"
        >
          {sceneReady && (
            <Suspense
              fallback={
                <div
                  className="absolute inset-0 bg-gradient-to-br from-[#040c1e] via-[#071428] to-[#04101f] animate-pulse"
                  aria-hidden
                />
              }
            >
              <HeroScene3D
                mouse={mouse}
                scrollProgress={scrollProgress}
                quality={quality}
                reducedMotion={!!prefersReducedMotion}
                hoverBoost={hoverBoost}
              />
            </Suspense>
          )}

          <canvas
            ref={canvasRef}
            className="absolute inset-0 w-full h-full block pointer-events-none z-[1]"
          />

          <div
            className="absolute inset-0 pointer-events-none rounded-2xl sm:rounded-3xl ring-1 ring-inset ring-white/10 z-[2]"
            aria-hidden
          />
          <div
            className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/35 to-transparent pointer-events-none z-[2]"
            aria-hidden
          />
          <div
            className="absolute inset-x-0 bottom-0 h-16 sm:h-20 z-10 pointer-events-none bg-gradient-to-t from-[#040c1e]/80 to-transparent"
            aria-hidden
          />
        </div>
      </div>

      <motion.div
        custom={0.55}
        variants={chipVariants}
        initial="hidden"
        animate="visible"
        whileHover={{ scale: 1.05, y: -3 }}
        transition={{ type: 'spring', stiffness: 400, damping: 22 }}
        className="absolute right-2 sm:right-4 top-[18%] z-20 px-3 py-2 rounded-xl bg-white/90 dark:bg-slate-800/90 border border-slate-200/80 dark:border-slate-600/60 shadow-card backdrop-blur-md"
      >
        <p className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400 font-medium">AI Match</p>
        <p className="text-lg font-bold text-accent-blue tabular-nums">94%</p>
      </motion.div>

      <motion.div
        custom={0.7}
        variants={chipVariants}
        initial="hidden"
        animate="visible"
        whileHover={{ scale: 1.05, y: -3 }}
        transition={{ type: 'spring', stiffness: 400, damping: 22 }}
        className="absolute left-2 sm:left-3 bottom-[22%] z-20 px-3 py-2 rounded-xl bg-white/90 dark:bg-slate-800/90 border border-slate-200/80 dark:border-slate-600/60 shadow-card backdrop-blur-md"
      >
        <p className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400 font-medium">Hire Rate</p>
        <p className="text-lg font-bold text-primary dark:text-white tabular-nums">92%</p>
      </motion.div>

      <motion.div
        custom={0.85}
        variants={chipVariants}
        initial="hidden"
        animate="visible"
        className="absolute left-1/2 -translate-x-1/2 bottom-3 sm:bottom-4 z-20 px-4 py-1.5 rounded-full bg-primary/95 dark:bg-accent-blue/95 text-white text-xs font-semibold shadow-lg whitespace-nowrap backdrop-blur-sm border border-white/10"
      >
        AI-Powered Workforce Platform
      </motion.div>

      <style>{`
        @keyframes heroPulse {
          0%, 100% { opacity: 0.7; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.08); }
        }
      `}</style>
    </div>
  )
}
