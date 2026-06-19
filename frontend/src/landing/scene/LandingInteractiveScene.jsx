import React, { Suspense, useRef } from 'react'
import { Canvas } from '@react-three/fiber'
import { Environment, useVideoTexture } from '@react-three/drei'
import * as THREE from 'three'
import LandingCameraRig from './LandingCameraRig.jsx'
import {
  GridFloor,
  IntelligenceSphere,
  TalentAcquisitionModule,
  EnterpriseAgileModule,
  PayrollVaultModule,
  TrainingModule,
} from './LandingModules.jsx'
import { HERO_VIDEO_SRC } from '../constants/heroVideo.js'

function VideoMotionPlane({ reducedMotion }) {
  if (reducedMotion) return null

  return (
    <Suspense fallback={null}>
      <VideoMotionPlaneInner />
    </Suspense>
  )
}

function VideoMotionPlaneInner() {
  const texture = useVideoTexture(HERO_VIDEO_SRC, {
    start: true,
    loop: true,
    muted: true,
    playsInline: true,
  })

  return (
    <mesh position={[0.5, 0, -6]} scale={[14, 8, 1]}>
      <planeGeometry />
      <meshBasicMaterial map={texture} transparent opacity={0.14} toneMapped={false} depthWrite={false} />
    </mesh>
  )
}

function SceneContent({ mouse, scrollProgress, reducedMotion, hoverCore, hoverModule, coreRef, cameraRef }) {
  return (
    <>
      <LandingCameraRig
        mouse={mouse}
        scrollProgress={scrollProgress}
        reducedMotion={reducedMotion}
        hoverBoost={hoverCore}
        cameraRef={cameraRef}
        transitionActive={false}
      />
      <color attach="background" args={['#030810']} />
      <fog attach="fog" args={['#030810', 8, 22]} />
      <ambientLight intensity={0.25} color="#1e3a5f" />
      <directionalLight position={[4, 6, 4]} intensity={0.5} color="#60a5fa" />
      <pointLight position={[-3, 2, 2]} intensity={0.8} color="#3b82f6" />
      <Environment preset="city" environmentIntensity={0.12} />

      <VideoMotionPlane reducedMotion={reducedMotion} />
      <GridFloor />
      <group ref={coreRef}>
        <IntelligenceSphere hoverBoost={hoverCore} position={[0.2, 0.15, 0]} />
      </group>
      <TalentAcquisitionModule hover={hoverModule === 'talent'} position={[-2.4, 0.6, -0.3]} />
      <EnterpriseAgileModule hover={hoverModule === 'enterprise'} position={[2.6, 1.0, -0.6]} />
      <PayrollVaultModule hover={hoverModule === 'payroll'} position={[2.8, -0.7, 0.1]} />
      <TrainingModule position={[-2.0, -1.0, 0.5]} />
    </>
  )
}

export default function LandingInteractiveScene({
  mouse = { x: 0.5, y: 0.5 },
  scrollProgress = 0,
  reducedMotion = false,
  hoverCore = false,
  hoverModule = null,
  coreRef,
  cameraRef,
}) {
  return (
    <Canvas
      dpr={[1, 1.5]}
      camera={{ position: [0, 0.5, 7], fov: 42, near: 0.1, far: 30 }}
      gl={{
        antialias: true,
        alpha: false,
        powerPreference: 'high-performance',
        toneMapping: THREE.ACESFilmicToneMapping,
        toneMappingExposure: 1.05,
      }}
      frameloop={reducedMotion ? 'demand' : 'always'}
    >
      <SceneContent
        mouse={mouse}
        scrollProgress={scrollProgress}
        reducedMotion={reducedMotion}
        hoverCore={hoverCore}
        hoverModule={hoverModule}
        coreRef={coreRef}
        cameraRef={cameraRef}
      />
    </Canvas>
  )
}
