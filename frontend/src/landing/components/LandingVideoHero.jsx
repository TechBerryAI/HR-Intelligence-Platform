import React, { forwardRef, useImperativeHandle, useRef, useEffect } from 'react'
import { useReducedMotion } from 'framer-motion'
import gsap from 'gsap'

const VIDEO_SRC = '/demo/landing-hero.mp4'

/**
 * Fullscreen hero background — plays the reference MP4 so the landing
 * animation is pixel-identical to make_it_look_as_a_website_so_t.mp4
 */
const LandingVideoHero = forwardRef(function LandingVideoHero(_, ref) {
  const shellRef = useRef(null)
  const videoRef = useRef(null)
  const prefersReducedMotion = useReducedMotion()

  useImperativeHandle(ref, () => shellRef.current)

  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    if (prefersReducedMotion) {
      video.pause()
      video.currentTime = 0
    } else {
      const play = () => video.play().catch(() => {})
      play()
      video.addEventListener('canplay', play, { once: true })
    }
  }, [prefersReducedMotion])

  useEffect(() => {
    if (!shellRef.current) return
    if (prefersReducedMotion) {
      shellRef.current.style.opacity = '1'
      return
    }
    const tl = gsap.fromTo(
      shellRef.current,
      { opacity: 0 },
      { opacity: 1, duration: 0.7, ease: 'power2.out' },
    )
    return () => tl.kill()
  }, [prefersReducedMotion])

  return (
    <div
      ref={shellRef}
      className="fixed inset-0 overflow-hidden bg-[#040c1e]"
      style={{ opacity: prefersReducedMotion ? 1 : 0 }}
    >
      <video
        ref={videoRef}
        className="absolute inset-0 w-full h-full object-cover"
        style={{ objectPosition: '58% center' }}
        src={VIDEO_SRC}
        autoPlay
        loop
        muted
        playsInline
        preload="auto"
        aria-hidden
      />

      {/* Left gradient so marketing copy stays readable; right stays video-sharp */}
      <div
        className="absolute inset-0 pointer-events-none bg-gradient-to-r from-[#040c1e]/95 via-[#040c1e]/55 to-transparent lg:from-[#040c1e]/90 lg:via-[#040c1e]/35 lg:to-transparent"
        aria-hidden
      />
      <div
        className="absolute inset-x-0 top-0 h-28 bg-gradient-to-b from-[#040c1e]/50 to-transparent pointer-events-none"
        aria-hidden
      />
      <div
        className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-[#040c1e]/45 to-transparent pointer-events-none"
        aria-hidden
      />
    </div>
  )
})

export default LandingVideoHero
