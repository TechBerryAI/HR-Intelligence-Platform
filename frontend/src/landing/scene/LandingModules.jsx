import React, { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { Line, Html } from '@react-three/drei'
import * as THREE from 'three'

export function GridFloor() {
  return (
    <group position={[0, -1.8, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <gridHelper args={[18, 36, '#1e4a8a', '#0c2040']} />
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0, -0.01]}>
        <planeGeometry args={[18, 18]} />
        <meshBasicMaterial color="#030810" transparent opacity={0.85} />
      </mesh>
    </group>
  )
}

export function IntelligenceSphere({ hoverBoost = false, position = [0, 0.2, 0] }) {
  const groupRef = useRef()
  const innerRef = useRef()

  useFrame((state) => {
    const t = state.clock.elapsedTime
    if (groupRef.current) groupRef.current.rotation.y = t * 0.15
    if (innerRef.current?.material) {
      innerRef.current.material.emissiveIntensity = (hoverBoost ? 2.2 : 1.4) + Math.sin(t * 1.5) * 0.3
    }
  })

  const ringPoints = useRef(
    Array.from({ length: 65 }, (_, i) => {
      const a = (i / 64) * Math.PI * 2
      return new THREE.Vector3(Math.cos(a) * 1.1, Math.sin(a) * 1.1, 0)
    }),
  ).current

  return (
    <group ref={groupRef} position={position}>
      <mesh ref={innerRef}>
        <sphereGeometry args={[0.55, 64, 64]} />
        <meshPhysicalMaterial
          color="#1d4ed8"
          emissive="#3b82f6"
          emissiveIntensity={1.4}
          roughness={0.05}
          metalness={0.2}
          transmission={0.88}
          thickness={0.6}
          transparent
          opacity={0.92}
          clearcoat={1}
        />
      </mesh>
      <Line points={ringPoints} color="#22d3ee" lineWidth={1} transparent opacity={0.35} />
      {[0.75, 0.95, 1.15].map((r, i) => (
        <mesh key={i} rotation={[Math.PI / 3 + i * 0.4, i, 0]}>
          <torusGeometry args={[r, 0.008, 8, 80]} />
          <meshBasicMaterial color="#22d3ee" transparent opacity={0.12} blending={THREE.AdditiveBlending} depthWrite={false} />
        </mesh>
      ))}
      <pointLight intensity={hoverBoost ? 3 : 2} color="#60a5fa" distance={5} decay={2} />
    </group>
  )
}

function GlassPanel({ position, title, subtitle, hover = false, scale = 1, children }) {
  return (
    <group position={position} scale={scale}>
      <mesh>
        <boxGeometry args={[2.2, 1.4, 0.06]} />
        <meshPhysicalMaterial
          color="#0f2847"
          transparent
          opacity={hover ? 0.58 : 0.45}
          roughness={0.08}
          transmission={0.55}
          thickness={0.3}
          clearcoat={1}
        />
      </mesh>
      <Line
        points={[
          new THREE.Vector3(-1.05, 0.65, 0.04),
          new THREE.Vector3(1.05, 0.65, 0.04),
          new THREE.Vector3(1.05, -0.65, 0.04),
          new THREE.Vector3(-1.05, -0.65, 0.04),
          new THREE.Vector3(-1.05, 0.65, 0.04),
        ]}
        color={hover ? '#22d3ee' : '#3b82f6'}
        lineWidth={1}
        transparent
        opacity={0.55}
      />
      <Html position={[0, 0.55, 0.1]} center transform distanceFactor={8} style={{ pointerEvents: 'none' }}>
        <div
          className={`px-2 py-0.5 rounded text-[10px] font-semibold whitespace-nowrap transition-colors ${
            hover ? 'text-cyan-200' : 'text-slate-300'
          }`}
        >
          {title}
        </div>
      </Html>
      {subtitle && (
        <Html position={[0, -0.15, 0.1]} center transform distanceFactor={8} style={{ pointerEvents: 'none' }}>
          <div className="text-[9px] text-slate-400 whitespace-nowrap">{subtitle}</div>
        </Html>
      )}
      {children}
    </group>
  )
}

export function TalentAcquisitionModule({ hover = false, position = [-2.2, 0.8, -0.5] }) {
  return (
    <GlassPanel
      position={position}
      title="Talent Acquisition"
      subtitle="Job A · 94% · Job B · 87%"
      hover={hover}
      scale={0.95}
    />
  )
}

export function EnterpriseAgileModule({ hover = false, position = [2.4, 1.1, -0.8] }) {
  const bars = [0.4, 0.7, 0.55, 0.85, 0.6]
  return (
    <group position={position}>
      <GlassPanel title="Enterprise Agile" subtitle="Scaling analytics" hover={hover} scale={0.9}>
        {bars.map((h, i) => (
          <mesh key={i} position={[-0.5 + i * 0.28, -0.15 + h * 0.35, 0.1]}>
            <boxGeometry args={[0.14, h * 0.5, 0.04]} />
            <meshStandardMaterial color="#22d3ee" emissive="#0891b2" emissiveIntensity={hover ? 0.9 : 0.5} />
          </mesh>
        ))}
      </GlassPanel>
    </group>
  )
}

export function PayrollVaultModule({ hover = false, position = [2.6, -0.6, 0.2] }) {
  const beltRef = useRef()

  useFrame((state) => {
    if (beltRef.current) beltRef.current.position.x = Math.sin(state.clock.elapsedTime * 1.2) * 0.08
  })

  return (
    <group position={position}>
      <GlassPanel title="Quantum Payroll" subtitle="$24,500 processed" hover={hover} scale={1} />
      <group ref={beltRef} position={[0, -0.95, 0.3]}>
        <mesh>
          <boxGeometry args={[1.6, 0.08, 0.3]} />
          <meshStandardMaterial color="#1e3a5f" emissive="#0ea5e9" emissiveIntensity={hover ? 0.5 : 0.3} />
        </mesh>
        {[0, 1, 2].map((i) => (
          <mesh key={i} position={[-0.5 + i * 0.5, 0.12, 0]}>
            <cylinderGeometry args={[0.08, 0.08, 0.04, 16]} />
            <meshStandardMaterial color="#fbbf24" emissive="#f59e0b" emissiveIntensity={hover ? 1.2 : 0.8} />
          </mesh>
        ))}
      </group>
    </group>
  )
}

export function TrainingModule({ position = [-1.8, -0.9, 0.4] }) {
  return <GlassPanel position={position} title="Training" subtitle="12 courses active" scale={0.85} />
}
