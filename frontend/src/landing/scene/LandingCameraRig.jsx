import { useRef, useEffect } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'

export default function LandingCameraRig({
  mouse,
  scrollProgress = 0,
  reducedMotion = false,
  hoverBoost = false,
  cameraRef,
  transitionActive = false,
}) {
  const { camera } = useThree()
  const lookAt = useRef(new THREE.Vector3(0, 0.1, 0))

  useEffect(() => {
    if (cameraRef) {
      cameraRef.current = camera
    }
  }, [camera, cameraRef])

  useFrame(() => {
    if (transitionActive) return

    const mx = (mouse.x - 0.5) * (reducedMotion ? 0.15 : 0.45)
    const my = (mouse.y - 0.5) * (reducedMotion ? 0.1 : 0.28)
    const scrollPull = scrollProgress * 1.2
    const hoverZ = hoverBoost ? -0.35 : 0

    const desiredX = mx * 0.7
    const desiredY = 0.15 - my * 0.45 + scrollPull * 0.2
    const desiredZ = 8 - scrollPull * 1.5 + hoverZ

    camera.position.x = THREE.MathUtils.lerp(camera.position.x, desiredX, 0.04)
    camera.position.y = THREE.MathUtils.lerp(camera.position.y, desiredY, 0.04)
    camera.position.z = THREE.MathUtils.lerp(camera.position.z, desiredZ, 0.035)

    lookAt.current.set(mx * 0.2, 0.1 - my * 0.15 + scrollPull * 0.05, 0)
    camera.lookAt(lookAt.current)
  })

  return null
}
