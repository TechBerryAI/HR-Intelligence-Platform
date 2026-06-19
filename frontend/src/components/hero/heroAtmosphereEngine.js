/**
 * Cinematic atmosphere overlay — cursor glow, film grain, vignette, dust particles.
 * Composited over the illustration canvas with screen blend for premium polish.
 */

export function createHeroAtmosphereEngine() {
  let W = 900
  let H = 580
  let t = 0
  let timeScale = 1
  let smoothMouse = { x: 0.5, y: 0.5 }
  let targetMouse = { x: 0.5, y: 0.5 }
  let scrollProgress = 0
  let quality = 'high'
  let landingMode = false

  const intensity = () => (landingMode ? 0.35 : 1)

  const dustParticles = Array.from({ length: 48 }, (_, i) => ({
    seed: i * 1.618,
    size: 0.6 + (i % 5) * 0.3,
  }))

  function drawVignette(ctx) {
    const k = intensity()
    const vignette = ctx.createRadialGradient(W * 0.5, H * 0.5, H * 0.12, W * 0.5, H * 0.5, H * 0.75)
    vignette.addColorStop(0, 'rgba(0,0,0,0)')
    vignette.addColorStop(0.65, `rgba(0,0,0,${0.08 * k})`)
    vignette.addColorStop(1, `rgba(0,0,0,${0.48 * k})`)
    ctx.fillStyle = vignette
    ctx.fillRect(0, 0, W, H)
  }

  function drawCursorGlow(ctx) {
    const gx = smoothMouse.x * W
    const gy = smoothMouse.y * H
    const radius = quality === 'high' ? 200 : 130
    const glow = ctx.createRadialGradient(gx, gy, 0, gx, gy, radius)
    glow.addColorStop(0, `rgba(59,130,246,${0.14 * intensity()})`)
    glow.addColorStop(0.35, `rgba(14,165,233,${0.06 * intensity()})`)
    glow.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.fillStyle = glow
    ctx.fillRect(0, 0, W, H)
  }

  function drawDust(ctx) {
    if (quality === 'low') return
    dustParticles.forEach((p) => {
      const px = ((p.seed * 137) % 1) * W
      const py = ((p.seed * 251) % 1) * H
      const driftX = Math.sin(t * 0.5 + p.seed) * 16 + (smoothMouse.x - 0.5) * 24
      const driftY = Math.cos(t * 0.35 + p.seed * 1.3) * 12 + (smoothMouse.y - 0.5) * 18
      const alpha = 0.1 + Math.sin(t * 1.2 + p.seed) * 0.07
      ctx.beginPath()
      ctx.arc(px + driftX, py + driftY, p.size, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(120,200,255,${alpha})`
      ctx.fill()
    })
  }

  function drawFilmGrain(ctx) {
    if (quality === 'low') return
    const dots = 100
    const seed = Math.floor(t * 1000) % 9973
    for (let i = 0; i < dots; i++) {
      const x = ((seed + i * 7919) % 10000) / 10000 * W
      const y = ((seed + i * 6271) % 10000) / 10000 * H
      const alpha = ((seed + i * 3571) % 100) / 100 * 0.045
      ctx.fillStyle = `rgba(180,210,255,${alpha})`
      ctx.fillRect(x, y, 1, 1)
    }
  }

  function drawScanline(ctx) {
    if (quality === 'low') return
    const y = ((t * 35) % (H + 80)) - 40
    const scan = ctx.createLinearGradient(0, y - 40, 0, y + 40)
    scan.addColorStop(0, 'rgba(0,180,255,0)')
    scan.addColorStop(0.5, 'rgba(0,180,255,0.022)')
    scan.addColorStop(1, 'rgba(0,180,255,0)')
    ctx.fillStyle = scan
    ctx.fillRect(0, 0, W, H)
  }

  function drawEdgeGlow(ctx) {
    const edge = ctx.createLinearGradient(0, 0, W, 0)
    edge.addColorStop(0, 'rgba(0,100,255,0.07)')
    edge.addColorStop(0.5, 'rgba(0,0,0,0)')
    edge.addColorStop(1, 'rgba(0,200,120,0.06)')
    ctx.fillStyle = edge
    ctx.fillRect(0, 0, W, H)
  }

  function drawBloomHotspots(ctx) {
    if (quality === 'low') return
    const k = intensity()
    const hotspots = [
      { x: W * 0.38, y: H * 0.36, r: 80, a: 0.08 },
      { x: W * 0.6, y: H * 0.5, r: 120, a: 0.06 },
      { x: W * 0.75, y: H * 0.65, r: 70, a: 0.05 },
    ]
    hotspots.forEach((h) => {
      const g = ctx.createRadialGradient(h.x, h.y, 0, h.x, h.y, h.r)
      g.addColorStop(0, `rgba(0,150,255,${h.a * k})`)
      g.addColorStop(1, 'rgba(0,0,0,0)')
      ctx.fillStyle = g
      ctx.fillRect(0, 0, W, H)
    })
  }

  function render(ctx) {
    smoothMouse.x += (targetMouse.x - smoothMouse.x) * 0.055
    smoothMouse.y += (targetMouse.y - smoothMouse.y) * 0.055

    const scrollBoost = 0.9 + scrollProgress * 0.2
    t += 0.006 * timeScale * scrollBoost

    ctx.clearRect(0, 0, W, H)
    drawEdgeGlow(ctx)
    drawBloomHotspots(ctx)
    drawDust(ctx)
    drawCursorGlow(ctx)
    drawScanline(ctx)
    drawVignette(ctx)
    drawFilmGrain(ctx)
  }

  return {
    resize(width, height) {
      W = width
      H = height
    },
    setMouse(x, y) {
      targetMouse.x = x
      targetMouse.y = y
    },
    setScrollProgress(p) {
      scrollProgress = Math.max(0, Math.min(1, p))
    },
    setTimeScale(scale) {
      timeScale = scale
    },
    setQuality(q) {
      quality = q
    },
    setLandingMode(mode) {
      landingMode = mode
    },
    render,
  }
}
