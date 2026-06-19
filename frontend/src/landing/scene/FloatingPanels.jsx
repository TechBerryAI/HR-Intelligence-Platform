import React, { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import { Float, Line } from '@react-three/drei'
import * as THREE from 'three'
import { createGlassMaterial, COLORS } from '../../components/hero/scene/materials.js'

const PANEL_CONFIGS = [
  { radius: 2.2, angle: 0.4, y: 0.5, w: 1.1, h: 0.7, color: COLORS.glassFill },
  { radius: 2.4, angle: 2.1, y: -0.2, w: 0.95, h: 0.55, color: '#1a4080' },
  { radius: 2.0, angle: 3.8, y: 0.3, w: 1.0, h: 0.6, color: '#0f3060' },
  { radius: 2.6, angle: 5.2, y: -0.5, w: 0.85, h: 0.5, color: '#124080' },
  { radius: 2.3, angle: 1.5, y: -0.8, w: 0.9, h: 0.5, color: '#1850a0' },
]

function GlassPanel({ config, quality, index }) {
  const meshRef = useRef()
  const material = useMemo(() => createGlassMaterial({ quality, color: config.color, opacity: 0.3 }), [quality, config.color])

  const edgePoints = useMemo(() => {
    const hw = config.w / 2
    const hh = config.h / 2
    return [
      new THREE.Vector3(-hw, hh, 0),
      new THREE.Vector3(hw, hh, 0),
      new THREE.Vector3(hw, -hh, 0),
      new THREE.Vector3(-hw, -hh, 0),
      new THREE.Vector3(-hw, hh, 0),
    ]
  }, [config.w, config.h])

  const x = Math.cos(config.angle) * config.radius
  const z = Math.sin(config.angle) * config.radius - 1.5

  useFrame((state) => {
    if (!meshRef.current) return
    meshRef.current.lookAt(state.camera.position)
  })

  if (quality === 'low' && index > 1) return null
  if (quality === 'medium' && index > 2) return null

  return (
    <Float speed={1.2 + index * 0.2} rotationIntensity={0.08} floatIntensity={0.25}>
      <group position={[x, config.y, z]}>
        <mesh ref={meshRef} material={material}>
          <planeGeometry args={[config.w, config.h]} />
        </mesh>
        {quality !== 'low' && (
          <Line
            points={edgePoints}
            color={COLORS.cyan}
            lineWidth={1}
            transparent
            opacity={0.35}
            toneMapped={false}
          />
        )}
      </group>
    </Float>
  )
}

export default function FloatingPanels({ quality = 'high', scrollProgress = 0 }) {
  const groupRef = useRef()

  useFrame((state) => {
    if (!groupRef.current) return
    groupRef.current.rotation.y = state.clock.elapsedTime * 0.04 + scrollProgress * 0.3
  })

  const configs = quality === 'low' ? PANEL_CONFIGS.slice(0, 2) : quality === 'medium' ? PANEL_CONFIGS.slice(0, 3) : PANEL_CONFIGS

  return (
    <group ref={groupRef}>
      {configs.map((cfg, i) => (
        <GlassPanel key={i} config={cfg} quality={quality} index={i} />
      ))}
    </group>
  )
}
