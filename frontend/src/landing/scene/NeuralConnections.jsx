import React, { useMemo } from 'react'
import { Line } from '@react-three/drei'
import * as THREE from 'three'
import { COLORS } from '../../components/hero/scene/materials.js'

const NODE_POSITIONS = [
  [2.0, 0.4, -0.8],
  [-1.8, 0.6, -1.2],
  [1.2, -0.5, -1.5],
  [-2.2, -0.3, -0.5],
  [0.5, 1.0, -2.0],
  [-0.8, -0.9, -1.8],
]

export default function NeuralConnections({ quality = 'high' }) {
  const lines = useMemo(() => {
    const core = new THREE.Vector3(0, 0.1, 0)
    const segments = []
    NODE_POSITIONS.forEach((pos) => {
      segments.push([
        core.clone(),
        new THREE.Vector3(pos[0], pos[1], pos[2]),
      ])
    })
    for (let i = 0; i < NODE_POSITIONS.length - 1; i++) {
      const a = NODE_POSITIONS[i]
      const b = NODE_POSITIONS[(i + 2) % NODE_POSITIONS.length]
      segments.push([
        new THREE.Vector3(a[0], a[1], a[2]),
        new THREE.Vector3(b[0], b[1], b[2]),
      ])
    }
    return segments
  }, [])

  if (quality === 'low') return null

  return (
    <group>
      {lines.map((pts, i) => (
        <Line
          key={i}
          points={pts}
          color={COLORS.blue}
          lineWidth={0.5}
          transparent
          opacity={quality === 'high' ? 0.15 : 0.08}
          dashed
          dashScale={2}
          dashSize={0.08}
          gapSize={0.2}
        />
      ))}
    </group>
  )
}
