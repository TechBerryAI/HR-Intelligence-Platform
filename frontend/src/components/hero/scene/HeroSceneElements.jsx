import React, { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import { Sparkles, Line } from '@react-three/drei'
import * as THREE from 'three'
import { COLORS, createGlowSpriteMaterial } from './materials'

export function SceneLighting({ quality, hoverBoost }) {
  const coreIntensity = hoverBoost ? 2.4 : 1.8
  return (
    <>
      <ambientLight intensity={0.18} color="#1e3a5f" />
      <directionalLight position={[4, 6, 5]} intensity={0.38} color="#60a5fa" />
      <pointLight
        position={[-0.8, 1.2, 1.5]}
        intensity={quality === 'high' ? coreIntensity : 1.0}
        color="#0ea5e9"
        distance={10}
        decay={2}
      />
      <pointLight position={[1.2, 0.1, 2]} intensity={quality === 'high' ? 1.2 : 0.8} color="#3b82f6" distance={8} decay={2} />
      <pointLight position={[2, -0.6, 1.2]} intensity={0.55} color="#34d399" distance={6} decay={2} />
      <spotLight position={[0, 2.5, 3.5]} angle={0.5} penumbra={0.85} intensity={0.28} color="#818cf8" />
      {hoverBoost && (
        <pointLight position={[-0.4, 0.9, 1.8]} intensity={1.5} color="#22d3ee" distance={4} decay={2} />
      )}
    </>
  )
}

export function AmbientField({ quality, scrollProgress }) {
  const gridRef = useRef()
  const glowRef = useRef()

  useFrame((state) => {
    const t = state.clock.elapsedTime
    if (gridRef.current) {
      gridRef.current.position.y = -1.6 + Math.sin(t * 0.12) * 0.025 - scrollProgress * 0.08
    }
    if (glowRef.current) {
      glowRef.current.material.opacity = 0.035 + Math.sin(t * 0.4) * 0.012
    }
  })

  return (
    <group>
      <mesh position={[0, 0, -3.2]}>
        <planeGeometry args={[16, 10]} />
        <meshBasicMaterial color={COLORS.bg} />
      </mesh>

      <mesh ref={glowRef} position={[0.6, 0.1, -2.4]}>
        <planeGeometry args={[7, 5.5]} />
        <meshBasicMaterial
          color="#0078ff"
          transparent
          opacity={0.04}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      <mesh position={[1.4, -0.4, -2.3]}>
        <planeGeometry args={[4.5, 3.5]} />
        <meshBasicMaterial
          color="#00dc78"
          transparent
          opacity={0.028}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      {quality === 'high' && (
        <Sparkles
          count={120}
          scale={[10, 6, 5]}
          size={1.4}
          speed={0.2}
          opacity={0.32}
          color="#60a5fa"
          position={[0, 0.15, -0.8]}
        />
      )}

      {quality === 'high' && (
        <gridHelper
          ref={gridRef}
          args={[14, 28, '#0f2847', '#0a1a30']}
          position={[0, -1.6, -0.6]}
        />
      )}
    </group>
  )
}

export function OrbitRings({ reducedMotion, scrollProgress }) {
  const outerRef = useRef()
  const innerRef = useRef()
  const midRef = useRef()

  useFrame((state) => {
    if (reducedMotion) return
    const t = state.clock.elapsedTime
    const scrollFactor = 1 + scrollProgress * 0.3
    if (outerRef.current) outerRef.current.rotation.z = t * 0.08 * scrollFactor
    if (innerRef.current) innerRef.current.rotation.z = -t * 0.14 * scrollFactor
    if (midRef.current) midRef.current.rotation.z = t * 0.05 * scrollFactor
  })

  const makeEllipse = (rx, ry, segments = 72) => {
    const pts = []
    for (let i = 0; i <= segments; i++) {
      const a = (i / segments) * Math.PI * 2
      pts.push(new THREE.Vector3(Math.cos(a) * rx, Math.sin(a) * ry, 0))
    }
    return pts
  }

  const outerPoints = useMemo(() => makeEllipse(2.6, 0.98), [])
  const midPoints = useMemo(() => makeEllipse(2.0, 0.76), [])
  const innerPoints = useMemo(() => makeEllipse(1.5, 0.57), [])

  return (
    <group position={[0.45, -0.05, -0.5]}>
      <group ref={outerRef}>
        <Line
          points={outerPoints}
          color="#2850a0"
          lineWidth={1}
          transparent
          opacity={0.18}
          dashed
          dashScale={2}
          dashSize={0.12}
          gapSize={0.35}
        />
      </group>
      <group ref={midRef}>
        <Line
          points={midPoints}
          color="#1e4080"
          lineWidth={0.8}
          transparent
          opacity={0.14}
          dashed
          dashScale={2}
          dashSize={0.06}
          gapSize={0.5}
        />
      </group>
      <group ref={innerRef}>
        <Line
          points={innerPoints}
          color="#1a3870"
          lineWidth={0.8}
          transparent
          opacity={0.12}
          dashed
          dashScale={2}
          dashSize={0.04}
          gapSize={0.55}
        />
      </group>
    </group>
  )
}

export function DepthGlow({ quality, hoverBoost }) {
  const blueMat = useMemo(() => createGlowSpriteMaterial('#0ea5e9'), [])
  const greenMat = useMemo(() => createGlowSpriteMaterial('#34d399'), [])
  const groupRef = useRef()

  useFrame((state) => {
    if (!groupRef.current) return
    const t = state.clock.elapsedTime
    const scale = hoverBoost ? 1.15 : 1
    groupRef.current.children.forEach((child, i) => {
      const pulse = 1 + Math.sin(t * 0.8 + i * 1.2) * 0.08
      child.scale.setScalar(pulse * scale * (0.8 + i * 0.15))
    })
  })

  if (quality === 'low') return null

  return (
    <group ref={groupRef}>
      <sprite position={[-0.35, 0.55, -0.3]} scale={[2.2, 2.2, 1]} material={blueMat} />
      <sprite position={[0.5, -0.05, -0.2]} scale={[3.0, 3.0, 1]} material={blueMat} />
      <sprite position={[1.5, 0.3, -0.4]} scale={[1.6, 1.6, 1]} material={greenMat} />
    </group>
  )
}

export function EnergyField({ quality, reducedMotion }) {
  const meshRef = useRef()

  useFrame((state) => {
    if (!meshRef.current || reducedMotion) return
    meshRef.current.rotation.z = state.clock.elapsedTime * 0.06
    meshRef.current.material.opacity = 0.04 + Math.sin(state.clock.elapsedTime * 0.5) * 0.015
  })

  if (quality === 'low') return null

  return (
    <mesh ref={meshRef} position={[-0.35, 0.55, -0.8]} rotation={[0.3, 0.2, 0]}>
      <torusGeometry args={[0.9, 0.008, 8, 96]} />
      <meshBasicMaterial color="#22d3ee" transparent opacity={0.05} blending={THREE.AdditiveBlending} depthWrite={false} />
    </mesh>
  )
}

export function NeuralCloud({ quality, reducedMotion, mouse }) {
  const groupRef = useRef()
  const count = quality === 'high' ? 110 : 45

  const { positions, linePositions } = useMemo(() => {
    const pos = new Float32Array(count * 3)
    const lines = new Float32Array(count * 6)
    for (let i = 0; i < count; i++) {
      const r = 3.2 + (i % 9) * 0.12
      const theta = (i * 2.399) % (Math.PI * 2)
      const phi = Math.acos(2 * ((i * 0.618) % 1) - 1)
      pos[i * 3] = r * Math.sin(phi) * Math.cos(theta) * 0.6
      pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta) * 0.35
      pos[i * 3 + 2] = r * Math.cos(phi) * 0.4 - 2.2
    }
    for (let i = 0; i < count; i++) {
      const j = (i + 2 + (i % 5)) % count
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
    if (!groupRef.current || reducedMotion) return
    const t = state.clock.elapsedTime * 0.1
    const mx = (mouse.x - 0.5) * 0.15
    const my = (mouse.y - 0.5) * 0.1
    groupRef.current.rotation.y = t * 0.3 + mx
    groupRef.current.rotation.x = Math.sin(t * 0.35) * 0.05 - my
  })

  return (
    <group ref={groupRef} position={[0, 0, -1.2]}>
      <points>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" count={count} array={positions} itemSize={3} />
        </bufferGeometry>
        <pointsMaterial
          size={quality === 'high' ? 0.022 : 0.032}
          color="#60a5fa"
          transparent
          opacity={0.45}
          sizeAttenuation
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </points>
      {quality === 'high' && (
        <lineSegments>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" count={count * 2} array={linePositions} itemSize={3} />
          </bufferGeometry>
          <lineBasicMaterial color="#3b82f6" transparent opacity={0.06} depthWrite={false} />
        </lineSegments>
      )}
    </group>
  )
}
