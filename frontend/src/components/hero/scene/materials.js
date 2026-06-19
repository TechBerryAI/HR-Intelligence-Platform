import * as THREE from 'three'

export const COLORS = {
  bg: '#040c1e',
  blue: '#3b82f6',
  cyan: '#22d3ee',
  emerald: '#34d399',
  violet: '#8b5cf6',
  glassBorder: '#5090ff',
  glassFill: '#1450b4',
}

export function createGlassMaterial({ quality = 'high', color = COLORS.glassFill, opacity = 0.35 } = {}) {
  if (quality === 'low') {
    return new THREE.MeshPhysicalMaterial({
      color,
      transparent: true,
      opacity,
      roughness: 0.15,
      metalness: 0.1,
      clearcoat: 1,
      clearcoatRoughness: 0.1,
      side: THREE.DoubleSide,
    })
  }
  return new THREE.MeshPhysicalMaterial({
    color,
    transparent: true,
    opacity: Math.min(opacity + 0.15, 0.55),
    roughness: 0.05,
    metalness: 0.2,
    transmission: 0.6,
    thickness: 0.4,
    ior: 1.45,
    clearcoat: 1,
    clearcoatRoughness: 0.05,
    envMapIntensity: 0.8,
    side: THREE.DoubleSide,
  })
}

export function createEmissiveEdgeMaterial(color = COLORS.cyan, intensity = 1.2) {
  return new THREE.MeshStandardMaterial({
    color,
    emissive: color,
    emissiveIntensity: intensity,
    transparent: true,
    opacity: 0.85,
    toneMapped: false,
  })
}

export function createGlowSpriteMaterial(color = COLORS.blue) {
  const canvas = document.createElement('canvas')
  canvas.width = 64
  canvas.height = 64
  const ctx = canvas.getContext('2d')
  const grad = ctx.createRadialGradient(32, 32, 0, 32, 32, 32)
  grad.addColorStop(0, color)
  grad.addColorStop(0.4, `${color}88`)
  grad.addColorStop(1, 'transparent')
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, 64, 64)
  const tex = new THREE.CanvasTexture(canvas)
  return new THREE.SpriteMaterial({
    map: tex,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    toneMapped: false,
  })
}
