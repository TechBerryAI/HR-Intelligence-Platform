import React, { Suspense, useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { Environment } from '@react-three/drei'
import * as THREE from 'three'
import LandingCameraRig from './LandingCameraRig.jsx'
import HRIntelligenceCore from './HRIntelligenceCore.jsx'
import FloatingPanels from './FloatingPanels.jsx'
import ParticleField from './ParticleField.jsx'
import NeuralConnections from './NeuralConnections.jsx'
import {
  SceneLighting,
  AmbientField,
  OrbitRings,
  NeuralCloud,
  DepthGlow,
} from './index.js'

function SceneGroup({ mouse, scrollProgress, reducedMotion, hoverBoost, quality }) {
  const groupRef = useRef()

  useFrame(() => {
    if (!groupRef.current || reducedMotion) return
    const px = (mouse.x - 0.5) * 0.06
    const py = (mouse.y - 0.5) * 0.04
    groupRef.current.rotation.y = THREE.MathUtils.lerp(groupRef.current.rotation.y, px, 0.03)
    groupRef.current.rotation.x = THREE.MathUtils.lerp(groupRef.current.rotation.x, -py, 0.03)
  })

  return (
    <group ref={groupRef}>
      <AmbientField quality={quality} scrollProgress={scrollProgress} />
      <NeuralCloud quality={quality} reducedMotion={reducedMotion} mouse={mouse} />
      <OrbitRings reducedMotion={reducedMotion} scrollProgress={scrollProgress} />
      <DepthGlow quality={quality} hoverBoost={hoverBoost} />
    </group>
  )
}

function SceneContent({
  mouse,
  scrollProgress,
  quality,
  reducedMotion,
  hoverBoost,
  coreRef,
  cameraRef,
  isTransitioning,
}) {
  const particleCount = quality === 'high' ? 200 : quality === 'medium' ? 120 : 80

  return (
    <>
      <LandingCameraRig
        mouse={mouse}
        scrollProgress={scrollProgress}
        reducedMotion={reducedMotion}
        hoverBoost={hoverBoost}
        cameraRef={cameraRef}
        transitionActive={isTransitioning}
      />
      <fog attach="fog" args={['#020617', 6, 18]} />
      <SceneLighting quality={quality} hoverBoost={hoverBoost} />
      {quality === 'high' && <Environment preset="city" environmentIntensity={0.15} />}

      <HRIntelligenceCore
        quality={quality}
        reducedMotion={reducedMotion}
        hoverBoost={hoverBoost}
        coreRef={coreRef}
      />
      <FloatingPanels quality={quality} scrollProgress={scrollProgress} />
      <NeuralConnections quality={quality} />
      <ParticleField count={particleCount} reducedMotion={reducedMotion} />
      <SceneGroup
        mouse={mouse}
        scrollProgress={scrollProgress}
        reducedMotion={reducedMotion}
        hoverBoost={hoverBoost}
        quality={quality}
      />
    </>
  )
}

export default function LandingScene3D({
  mouse = { x: 0.5, y: 0.5 },
  scrollProgress = 0,
  quality = 'high',
  reducedMotion = false,
  hoverBoost = false,
  coreRef,
  cameraRef,
  isTransitioning = false,
  frameloop = 'always',
  className = '',
}) {
  const dpr = quality === 'high' ? [1, 1.5] : [1, 1]

  return (
    <div className={`fixed inset-0 ${className}`} aria-hidden>
      <Canvas
        dpr={dpr}
        camera={{ position: [0, 0.15, 8], fov: 42, near: 0.1, far: 30 }}
        gl={{
          antialias: quality === 'high',
          alpha: true,
          powerPreference: 'high-performance',
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: 1.08,
        }}
        style={{ background: 'transparent' }}
        frameloop={frameloop}
      >
        <Suspense fallback={null}>
          <SceneContent
            mouse={mouse}
            scrollProgress={scrollProgress}
            quality={quality}
            reducedMotion={reducedMotion}
            hoverBoost={hoverBoost}
            coreRef={coreRef}
            cameraRef={cameraRef}
            isTransitioning={isTransitioning}
          />
        </Suspense>
      </Canvas>
    </div>
  )
}
