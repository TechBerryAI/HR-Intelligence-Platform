import React, {
  useRef,
  useState,
  useEffect,
  useCallback,
  forwardRef,
  useImperativeHandle,
} from 'react'
import { useReducedMotion } from 'framer-motion'
import gsap from 'gsap'
import { FiZap } from 'react-icons/fi'
import { HERO_VIDEO_SRC, heroVideoRetrySrc } from '../constants/heroVideo.js'

/** Hotspots across the full-screen frame (normalized 0–1) */
const MODULE_ZONES = [
  { id: 'talent', label: 'Talent Acquisition', x: [0.04, 0.34], y: [0.16, 0.58] },
  { id: 'core', label: 'HR Intelligence Core', x: [0.3, 0.68], y: [0.2, 0.78] },
  { id: 'enterprise', label: 'Enterprise Agile', x: [0.62, 0.97], y: [0.06, 0.48] },
  { id: 'payroll', label: 'Quantum Payroll', x: [0.58, 0.97], y: [0.5, 0.94] },
]

function hitModule(nx, ny) {
  for (const z of MODULE_ZONES) {
    if (nx >= z.x[0] && nx <= z.x[1] && ny >= z.y[0] && ny <= z.y[1]) return z
  }
  return null
}

const LandingInteractiveHero = forwardRef(function LandingInteractiveHero(
  { scrollProgress = 0 },
  ref,
) {
  const shellRef = useRef(null)
  const stageRef = useRef(null)
  const videoWrapRef = useRef(null)
  const videoRef = useRef(null)
  const spotlightRef = useRef(null)
  const cursorRef = useRef(null)
  const prefersReducedMotion = useReducedMotion()

  const target = useRef({ x: 0, y: 0, rx: 0, ry: 0 })
  const current = useRef({ x: 0, y: 0, rx: 0, ry: 0 })
  const mouseNorm = useRef({ x: 0.5, y: 0.5 })

  const [hoverZone, setHoverZone] = useState(null)
  const [videoReady, setVideoReady] = useState(false)
  const [videoFailed, setVideoFailed] = useState(false)
  const [videoSrc, setVideoSrc] = useState(HERO_VIDEO_SRC)
  const [ripples, setRipples] = useState([])
  const [pointerInside, setPointerInside] = useState(false)
  const videoRetryUsed = useRef(false)

  useImperativeHandle(ref, () => shellRef.current)

  useEffect(() => {
    if (!shellRef.current || prefersReducedMotion) {
      if (shellRef.current) shellRef.current.style.opacity = '1'
      return
    }
    const tl = gsap.fromTo(
      shellRef.current,
      { opacity: 0 },
      { opacity: 1, duration: 0.85, ease: 'power2.out' },
    )
    return () => tl.kill()
  }, [prefersReducedMotion])

  useEffect(() => {
    const video = videoRef.current
    if (!video || videoFailed) return
    video.muted = true
    video.playsInline = true
    video.setAttribute('playsinline', '')
    video.setAttribute('webkit-playsinline', '')

    const onReady = () => {
      setVideoReady(true)
      video.play().catch(() => {})
    }

    const onError = () => {
      if (!videoRetryUsed.current) {
        videoRetryUsed.current = true
        setVideoReady(false)
        setVideoSrc(heroVideoRetrySrc(HERO_VIDEO_SRC))
        return
      }
      setVideoFailed(true)
      setVideoReady(false)
    }

    if (video.readyState >= 2) onReady()
    video.addEventListener('loadeddata', onReady)
    video.addEventListener('canplaythrough', onReady)
    video.addEventListener('error', onError)
    video.play().catch(() => {})

    return () => {
      video.removeEventListener('loadeddata', onReady)
      video.removeEventListener('canplaythrough', onReady)
      video.removeEventListener('error', onError)
    }
  }, [videoSrc, videoFailed])

  useEffect(() => {
    if (prefersReducedMotion || !videoWrapRef.current) return

    let raf = 0
    const tick = () => {
      const c = current.current
      const t = target.current
      const ease = hoverZone ? 0.12 : 0.08

      c.x += (t.x - c.x) * ease
      c.y += (t.y - c.y) * ease
      c.rx += (t.rx - c.rx) * ease
      c.ry += (t.ry - c.ry) * ease

      const scrollPull = scrollProgress * 14
      if (videoWrapRef.current) {
        videoWrapRef.current.style.transform = [
          `translate3d(${c.x - scrollPull * 0.1}px, ${c.y + scrollPull * 0.05}px, 0)`,
          `rotateY(${c.ry}deg)`,
          `rotateX(${c.rx}deg)`,
        ].join(' ')
      }

      if (spotlightRef.current) {
        const mx = mouseNorm.current.x * 100
        const my = mouseNorm.current.y * 100
        spotlightRef.current.style.background = [
          `radial-gradient(600px circle at ${mx}% ${my}%, rgba(56,189,248,0.14), transparent 55%)`,
          `radial-gradient(900px circle at ${mx}% ${my}%, rgba(59,130,246,0.08), transparent 70%)`,
        ].join(', ')
      }

      if (cursorRef.current && pointerInside) {
        cursorRef.current.style.left = `${mouseNorm.current.x * 100}%`
        cursorRef.current.style.top = `${mouseNorm.current.y * 100}%`
      }

      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [prefersReducedMotion, scrollProgress, hoverZone, pointerInside])

  const onPointerMove = useCallback(
    (e) => {
      const rect = stageRef.current?.getBoundingClientRect()
      if (!rect) return

      setPointerInside(true)

      const nx = (e.clientX - rect.left) / rect.width
      const ny = (e.clientY - rect.top) / rect.height
      const cx = nx - 0.5
      const cy = ny - 0.5

      mouseNorm.current = { x: nx, y: ny }
      const zone = hitModule(nx, ny)
      setHoverZone(zone)

      if (!prefersReducedMotion) {
        const boost = zone ? 1.2 : 1
        target.current.x = cx * 10 * boost
        target.current.y = cy * 8 * boost
        target.current.ry = cx * 1.8 * boost
        target.current.rx = -cy * 1.2 * boost
      }
    },
    [prefersReducedMotion],
  )

  const onPointerLeave = useCallback(() => {
    target.current.x = 0
    target.current.y = 0
    target.current.rx = 0
    target.current.ry = 0
    mouseNorm.current = { x: 0.5, y: 0.5 }
    setHoverZone(null)
    setPointerInside(false)
  }, [])

  const onPointerDown = useCallback((e) => {
    const rect = stageRef.current?.getBoundingClientRect()
    if (!rect) return
    const id = Date.now()
    const x = ((e.clientX - rect.left) / rect.width) * 100
    const y = ((e.clientY - rect.top) / rect.height) * 100
    setRipples((prev) => [...prev.slice(-4), { id, x, y }])
    window.setTimeout(() => {
      setRipples((prev) => prev.filter((r) => r.id !== id))
    }, 900)
  }, [])

  const hotspotStyle = (zone) => {
    const left = ((zone.x[0] + zone.x[1]) / 2) * 100
    const top = ((zone.y[0] + zone.y[1]) / 2) * 100
    const w = (zone.x[1] - zone.x[0]) * 100
    const h = (zone.y[1] - zone.y[0]) * 100
    return { left: `${left}%`, top: `${top}%`, width: `${w}%`, height: `${h}%` }
  }

  return (
    <div
      ref={shellRef}
      className="fixed inset-0 bg-[#050a14] overflow-hidden"
      style={{ opacity: prefersReducedMotion ? 1 : 0 }}
    >
      {/* Full-screen interactive stage */}
      <div
        ref={stageRef}
        className="absolute inset-0 z-[1] cursor-none touch-none"
        style={{ perspective: '1600px', perspectiveOrigin: '50% 50%' }}
        onPointerMove={onPointerMove}
        onPointerLeave={onPointerLeave}
        onPointerDown={onPointerDown}
        role="img"
        aria-label="Full-screen interactive 3D HR platform animation"
      >
        {/* Sharp native-resolution video — no upscale scale, cover-fit centering */}
        <div
          ref={videoWrapRef}
          className="absolute inset-0 will-change-transform overflow-hidden"
          style={{ transformStyle: 'preserve-3d' }}
        >
          {!videoFailed && (
            <video
              ref={videoRef}
              key={videoSrc}
              src={videoSrc}
              autoPlay
              loop
              muted
              playsInline
              preload="auto"
              className={`landing-hero-video transition-opacity duration-500 ${
                videoReady ? 'opacity-100' : 'opacity-0'
              }`}
            />
          )}
          {/* Atmospheric fallback when the stream cannot load */}
          <div
            className={`absolute inset-0 pointer-events-none transition-opacity duration-500 ${
              videoReady && !videoFailed ? 'opacity-0' : 'opacity-100'
            }`}
            style={{
              background:
                'radial-gradient(ellipse 80% 60% at 50% 40%, rgba(14,165,233,0.18) 0%, transparent 55%), linear-gradient(160deg, #050a14 0%, #0a1628 45%, #071018 100%)',
            }}
            aria-hidden
          />
        </div>

        {/* Cursor spotlight — interactive only, no dark scrims */}
        <div
          ref={spotlightRef}
          className="absolute inset-0 pointer-events-none z-[2] mix-blend-screen transition-opacity duration-300"
          style={{ opacity: hoverZone ? 0.5 : 0.25 }}
        />

        {/* Click ripples */}
        {ripples.map((r) => (
          <span
            key={r.id}
            className="absolute z-[3] pointer-events-none rounded-full border border-cyan-400/60 animate-[ripple_0.9s_ease-out_forwards]"
            style={{
              left: `${r.x}%`,
              top: `${r.y}%`,
              width: 24,
              height: 24,
              marginLeft: -12,
              marginTop: -12,
            }}
          />
        ))}

        {/* Module hotspots */}
        {MODULE_ZONES.map((zone) => {
          const active = hoverZone?.id === zone.id
          return (
            <div
              key={zone.id}
              className="absolute pointer-events-none rounded-3xl transition-all duration-200 z-[3]"
              style={{
                ...hotspotStyle(zone),
                boxShadow: active
                  ? '0 0 80px 24px rgba(34,211,238,0.4), inset 0 0 50px rgba(59,130,246,0.2)'
                  : 'none',
                border: active ? '1px solid rgba(34,211,238,0.55)' : '1px solid transparent',
                background: active
                  ? 'radial-gradient(circle, rgba(14,165,233,0.12) 0%, transparent 70%)'
                  : 'transparent',
                transform: active ? 'scale(1.02)' : 'scale(1)',
              }}
            />
          )
        })}

        {hoverZone && (
          <div
            className="absolute z-[4] pointer-events-none flex items-center gap-2 px-3 py-1.5 rounded-full bg-black/60 border border-cyan-400/40 text-cyan-100 text-xs font-semibold shadow-[0_0_24px_rgba(34,211,238,0.35)]"
            style={{
              left: `${((hoverZone.x[0] + hoverZone.x[1]) / 2) * 100}%`,
              top: `${hoverZone.y[0] * 100 - 5}%`,
              transform: 'translate(-50%, -100%)',
            }}
          >
            <FiZap className="w-3 h-3 text-cyan-400" />
            {hoverZone.label}
          </div>
        )}

        {/* Custom cursor ring */}
        {!prefersReducedMotion && pointerInside && (
          <div
            ref={cursorRef}
            className="absolute z-[5] pointer-events-none w-8 h-8 rounded-full border border-cyan-400/50 shadow-[0_0_12px_rgba(34,211,238,0.4)]"
            style={{ left: '50%', top: '50%', transform: 'translate(-50%, -50%)' }}
          />
        )}
      </div>
    </div>
  )
})

export default LandingInteractiveHero
