import React, { Suspense, useRef } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Environment } from '@react-three/drei'
import * as THREE from 'three'
import {
  SceneLighting,
  AmbientField,
  OrbitRings,
  NeuralCloud,
  DepthGlow,
  EnergyField,
} from './scene/HeroSceneElements'

function CameraRig({ mouse, scrollProgress, reducedMotion, hoverBoost }) {
  const { camera } = useThree()
  const lookAt = useRef(new THREE.Vector3(0, 0, 0))

  useFrame(() => {
    const mx = (mouse.x - 0.5) * (reducedMotion ? 0.12 : 0.38)
    const my = (mouse.y - 0.5) * (reducedMotion ? 0.08 : 0.22)
    const scrollPull = scrollProgress * 0.42
    const hoverZ = hoverBoost ? -0.22 : 0

    const desiredX = mx * 0.6
    const desiredY = 0.08 - my * 0.5 + scrollPull * 0.15
    const desiredZ = 6.8 + scrollPull * 0.65 + hoverZ

    camera.position.x = THREE.MathUtils.lerp(camera.position.x, desiredX, 0.038)
    camera.position.y = THREE.MathUtils.lerp(camera.position.y, desiredY, 0.038)
    camera.position.z = THREE.MathUtils.lerp(camera.position.z, desiredZ, 0.035)

    lookAt.current.set(mx * 0.25, -my * 0.18 + scrollPull * 0.08, 0)
    camera.lookAt(lookAt.current)
  })

  return null
}

function SceneContent({ mouse, scrollProgress, quality, reducedMotion, hoverBoost }) {
  const groupRef = useRef()

  useFrame(() => {
    if (!groupRef.current || reducedMotion) return
    const px = (mouse.x - 0.5) * 0.08
    const py = (mouse.y - 0.5) * 0.05
    groupRef.current.rotation.y = THREE.MathUtils.lerp(groupRef.current.rotation.y, px, 0.035)
    groupRef.current.rotation.x = THREE.MathUtils.lerp(groupRef.current.rotation.x, -py, 0.035)
  })

  return (
    <>
      <CameraRig
        mouse={mouse}
        scrollProgress={scrollProgress}
        reducedMotion={reducedMotion}
        hoverBoost={hoverBoost}
      />
      <fog attach="fog" args={['#040c1e', 5.5, 14]} />
      <SceneLighting quality={quality} hoverBoost={hoverBoost} />
      {quality === 'high' && <Environment preset="city" environmentIntensity={0.12} />}

      <group ref={groupRef}>
        <AmbientField quality={quality} scrollProgress={scrollProgress} />
        <NeuralCloud quality={quality} reducedMotion={reducedMotion} mouse={mouse} />
        <OrbitRings reducedMotion={reducedMotion} scrollProgress={scrollProgress} />
        <DepthGlow quality={quality} hoverBoost={hoverBoost} />
        <EnergyField quality={quality} reducedMotion={reducedMotion} />
      </group>
    </>
  )
}

export default function HeroScene3D({
  mouse = { x: 0.5, y: 0.5 },
  scrollProgress = 0,
  quality = 'high',
  reducedMotion = false,
  hoverBoost = false,
  className = '',
  frameloop,
}) {
  const dpr = quality === 'high' ? [1, 1.5] : [1, 1]
  const loop = frameloop ?? (reducedMotion ? 'demand' : 'always')

  return (
    <div className={`absolute inset-0 ${className}`} aria-hidden>
      <Canvas
        dpr={dpr}
        camera={{ position: [0, 0.08, 6.8], fov: 38, near: 0.1, far: 22 }}
        gl={{
          antialias: quality === 'high',
          alpha: true,
          powerPreference: 'high-performance',
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: 1.05,
        }}
        style={{ background: 'transparent' }}
        frameloop={loop}
      >
        <Suspense fallback={null}>
          <SceneContent
            mouse={mouse}
            scrollProgress={scrollProgress}
            quality={quality}
            reducedMotion={reducedMotion}
            hoverBoost={hoverBoost}
          />
        </Suspense>
      </Canvas>
    </div>
  )
}
