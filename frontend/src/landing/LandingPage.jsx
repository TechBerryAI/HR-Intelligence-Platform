import React, { useRef, useState } from 'react'
import LandingNav from './components/LandingNav.jsx'
import LandingHero from './components/LandingHero.jsx'
import LandingSections from './components/LandingSections.jsx'
import LandingInteractiveHero from './components/LandingInteractiveHero.jsx'
import TransitionOverlay from './transitions/TransitionOverlay.jsx'
import WatchDemoModal from './components/WatchDemoModal.jsx'
import { useLandingScroll } from './hooks/useLandingScroll.js'
import { useEnterAppTransition } from './hooks/useEnterAppTransition.js'

export default function LandingPage() {
  const scrollProgress = useLandingScroll()

  const visualRef = useRef(null)
  const overlayRef = useRef(null)
  const uiRef = useRef(null)

  const [demoOpen, setDemoOpen] = useState(false)

  const { start: startEnterTransition } = useEnterAppTransition({
    visualRef,
    overlayRef,
    uiRef,
  })

  const handleGetStarted = () => {
    startEnterTransition()
  }

  return (
    <div className="relative min-h-screen bg-[#050a14] text-white">
      {/* Interactive 3D hero — text-free video used only as subtle motion texture inside scene */}
      <div className="fixed inset-0 z-0">
        <LandingInteractiveHero ref={visualRef} scrollProgress={scrollProgress} />
      </div>

      {/* UI always above scene — nav, copy, CTAs are real HTML */}
      <div ref={uiRef} className="relative z-20">
        <LandingNav scrollProgress={scrollProgress} onGetStarted={handleGetStarted} />

        <main>
          <LandingHero
            onGetStarted={handleGetStarted}
            onWatchDemo={() => setDemoOpen(true)}
          />

          <LandingSections />
        </main>
      </div>

      <TransitionOverlay ref={overlayRef} />
      <WatchDemoModal open={demoOpen} onClose={() => setDemoOpen(false)} />
    </div>
  )
}
