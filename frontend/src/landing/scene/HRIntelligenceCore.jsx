import React, { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import { Line } from '@react-three/drei'
import * as THREE from 'three'
import { COLORS } from '../../components/hero/scene/materials.js'

export default function HRIntelligenceCore({
  quality = 'high',
  reducedMotion = false,
  hoverBoost = false,
  coreRef,
}) {
  const innerRef = useRef()
  const ringRefs = useRef([])
  const networkRef = useRef()
  const count = quality === 'high' ? 80 : quality === 'medium' ? 50 : 28

  const { positions, linePositions } = useMemo(() => {
    const pos = new Float32Array(count * 3)
    const lines = new Float32Array(count * 6)
    for (let i = 0; i < count; i++) {
      const r = 0.55 + (i % 7) * 0.04
      const theta = (i * 2.399) % (Math.PI * 2)
      const phi = Math.acos(2 * ((i * 0.618) % 1) - 1)
      pos[i * 3] = r * Math.sin(phi) * Math.cos(theta)
      pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta)
      pos[i * 3 + 2] = r * Math.cos(phi)
    }
    for (let i = 0; i < count; i++) {
      const j = (i + 2 + (i % 4)) % count
      lines[i * 6] = pos[i * 3]
      lines[i * 6 + 1] = pos[i * 3 + 1]
      lines[i * 6 + 2] = pos[i * 3 + 2]
      lines[i * 6 + 3] = pos[j * 3]
      lines[i * 6 + 4] = pos[j * 3 + 1]
      lines[i * 6 + 5] = pos[j * 3 + 2]
    }
    return { positions: pos, linePositions: lines }
  }, [count])

  useFrame((state) => {
    const t = state.clock.elapsedTime
    const group = coreRef?.current || innerRef.current?.parent
    if (!group || reducedMotion) return

    const pulse = 1 + Math.sin(t * 0.9) * 0.04
    const boost = hoverBoost ? 1.12 : 1
    group.scale.setScalar(pulse * boost)

    if (innerRef.current?.material) {
      innerRef.current.material.emissiveIntensity = (hoverBoost ? 1.8 : 1.2) + Math.sin(t * 1.2) * 0.2
    }

    ringRefs.current.forEach((ring, i) => {
      if (!ring) return
      ring.rotation.x = t * (0.15 + i * 0.05)
      ring.rotation.y = t * (0.2 + i * 0.03)
      if (ring.material) {
        ring.material.opacity = 0.06 + Math.sin(t * 0.7 + i) * 0.02
      }
    })

    if (networkRef.current) {
      networkRef.current.rotation.y = t * 0.25
      networkRef.current.rotation.x = Math.sin(t * 0.3) * 0.08
    }
  })

  const ringConfigs = [
    { radius: 0.72, tube: 0.006, color: COLORS.cyan },
    { radius: 0.88, tube: 0.005, color: COLORS.blue },
    { radius: 1.02, tube: 0.004, color: COLORS.violet },
  ]

  return (
    <group ref={coreRef} position={[0, 0.1, 0]}>
      <mesh ref={innerRef}>
        <icosahedronGeometry args={[0.42, quality === 'high' ? 2 : 1]} />
        <meshPhysicalMaterial
          color={COLORS.blue}
          emissive={COLORS.blue}
          emissiveIntensity={1.2}
          roughness={0.05}
          metalness={0.3}
          transmission={quality === 'high' ? 0.85 : 0.5}
          thickness={0.5}
          transparent
          opacity={0.92}
          clearcoat={1}
          clearcoatRoughness={0.05}
        />
      </mesh>

      {ringConfigs.map((cfg, i) => (
        <mesh
          key={i}
          ref={(el) => {
            ringRefs.current[i] = el
          }}
          rotation={[Math.PI / 2 + i * 0.3, i * 0.5, 0]}
        >
          <torusGeometry args={[cfg.radius, cfg.tube, 8, 64]} />
          <meshBasicMaterial
            color={cfg.color}
            transparent
            opacity={0.07}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      ))}

      <group ref={networkRef}>
        <points>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" count={count} array={positions} itemSize={3} />
          </bufferGeometry>
          <pointsMaterial
            size={quality === 'high' ? 0.028 : 0.04}
            color={COLORS.blue}
            transparent
            opacity={0.55}
            sizeAttenuation
            depthWrite={false}
            blending={THREE.AdditiveBlending}
          />
        </points>
        {quality !== 'low' && (
          <lineSegments>
            <bufferGeometry>
              <bufferAttribute attach="attributes-position" count={count * 2} array={linePositions} itemSize={3} />
            </bufferGeometry>
            <lineBasicMaterial color={COLORS.blue} transparent opacity={0.12} depthWrite={false} />
          </lineSegments>
        )}
      </group>

      <pointLight
        position={[0, 0, 0.5]}
        intensity={hoverBoost ? 3 : 2}
        color={COLORS.cyan}
        distance={4}
        decay={2}
      />
    </group>
  )
}
