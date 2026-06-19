/**
 * Full-fidelity HRMS AI hero illustration — ported from hrms_ai_hero_illustration.html
 * with mouse parallax, scroll progression, and quality tiers.
 */

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r)
  ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r)
  ctx.arcTo(x, y, x + w, y, r)
  ctx.closePath()
}

function glassPanelRounded(ctx, x, y, w, h, r, alpha = 0.18, border = 'rgba(80,160,255,0.35)') {
  ctx.save()
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r)
  ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r)
  ctx.arcTo(x, y, x + w, y, r)
  ctx.closePath()
  const g = ctx.createLinearGradient(x, y, x, y + h)
  g.addColorStop(0, `rgba(20,80,180,${alpha + 0.06})`)
  g.addColorStop(1, `rgba(5,30,80,${alpha})`)
  ctx.fillStyle = g
  ctx.fill()
  ctx.strokeStyle = border
  ctx.lineWidth = 1
  ctx.stroke()
  ctx.beginPath()
  ctx.moveTo(x + r, y + 1)
  ctx.lineTo(x + w - r, y + 1)
  ctx.strokeStyle = 'rgba(180,220,255,0.22)'
  ctx.lineWidth = 1
  ctx.stroke()
  ctx.restore()
}

// Deterministic calendar cell visibility (reference used Math.random — caused flicker)
const LEAVE_GRID = [
  [1, 1, 1, 0, 1],
  [1, 1, 1, 1, 1],
  [1, 0, 1, 1, 1],
]

const LANDING_TEXT_COL = 0.42

export function createHeroIllustrationEngine() {
  let W = 900
  let H = 580
  let t = 0
  let timeScale = 1
  let quality = 'high'
  let smoothMouse = { x: 0.5, y: 0.5 }
  let targetMouse = { x: 0.5, y: 0.5 }
  let scrollProgress = 0
  let hoverBoost = false
  let showLeftDecor = true
  let landingMode = false

  function px(nx) {
    return landingMode ? W * (LANDING_TEXT_COL + nx * (1 - LANDING_TEXT_COL)) : W * nx
  }

  function py(ny) {
    return H * ny
  }

  function gAlpha(base) {
    return landingMode ? Math.min(base + 0.14, 0.55) : base
  }

  function parallax(depth) {
    const mx = (smoothMouse.x - 0.5) * depth
    const my = (smoothMouse.y - 0.5) * depth
    const scrollShift = scrollProgress * depth * 0.2
    return { x: mx, y: my + scrollShift * 0.08 }
  }

  function drawBG(ctx) {
    if (landingMode) {
      const bg = ctx.createLinearGradient(0, 0, W, H)
      bg.addColorStop(0, '#040c1e')
      bg.addColorStop(0.5, '#061428')
      bg.addColorStop(1, '#040c1e')
      ctx.fillStyle = bg
      ctx.fillRect(0, 0, W, H)
    } else {
      const bg = ctx.createLinearGradient(0, 0, W, H)
      bg.addColorStop(0, 'rgba(4,12,30,0.55)')
      bg.addColorStop(0.5, 'rgba(7,20,40,0.45)')
      bg.addColorStop(1, 'rgba(4,16,31,0.55)')
      ctx.fillStyle = bg
      ctx.fillRect(0, 0, W, H)
    }

    if (quality === 'high' || landingMode) {
      ctx.strokeStyle = landingMode ? 'rgba(30,80,160,0.14)' : 'rgba(30,80,160,0.10)'
      ctx.lineWidth = 0.5
      const gsize = landingMode ? 48 : 40
      for (let x = 0; x < W; x += gsize) {
        ctx.beginPath()
        ctx.moveTo(x, 0)
        ctx.lineTo(x, H)
        ctx.stroke()
      }
      for (let y = 0; y < H; y += gsize) {
        ctx.beginPath()
        ctx.moveTo(0, y)
        ctx.lineTo(W, y)
        ctx.stroke()
      }
    }

    const poolX = landingMode ? 0.72 : 0.62
    const pool = ctx.createRadialGradient(px(poolX), H * 0.5, 0, px(poolX), H * 0.5, 320)
    pool.addColorStop(0, landingMode ? 'rgba(0,120,255,0.18)' : 'rgba(0,120,255,0.12)')
    pool.addColorStop(0.5, 'rgba(0,80,200,0.08)')
    pool.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.fillStyle = pool
    ctx.fillRect(0, 0, W, H)

    const pool2 = ctx.createRadialGradient(px(0.75), H * 0.65, 0, px(0.75), H * 0.65, 200)
    pool2.addColorStop(0, landingMode ? 'rgba(0,220,120,0.12)' : 'rgba(0,220,120,0.07)')
    pool2.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.fillStyle = pool2
    ctx.fillRect(0, 0, W, H)
  }

  function drawOrbits(ctx) {
    const p = parallax(8)
    const cx = px(0.6) + p.x
    const cy = H * 0.5 + p.y
    const orbits = [
      { r: 175, speed: 0.18, dash: [6, 12] },
      { r: 240, speed: 0.1, dash: [3, 18] },
    ]
    orbits.forEach((o) => {
      ctx.save()
      ctx.translate(cx, cy)
      ctx.rotate(t * o.speed)
      ctx.beginPath()
      ctx.ellipse(0, 0, o.r, o.r * 0.38, 0, 0, Math.PI * 2)
      ctx.strokeStyle = 'rgba(40,100,200,0.2)'
      ctx.lineWidth = 1
      ctx.setLineDash(o.dash)
      ctx.stroke()
      ctx.setLineDash([])
      ctx.restore()
    })
  }

  function drawDashboard(ctx) {
    const p = parallax(14)
    const cx = px(0.6) + p.x
    const cy = H * 0.5 + p.y
    const dw = landingMode ? W * 0.34 : 320
    const dh = landingMode ? H * 0.38 : 220
    const dx = cx - dw / 2
    const dy = cy - dh / 2

    const og = ctx.createRadialGradient(cx, cy, 0, cx, cy, 240)
    og.addColorStop(0, landingMode ? 'rgba(0,100,255,0.2)' : 'rgba(0,100,255,0.12)')
    og.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.fillStyle = og
    ctx.fillRect(0, 0, W, H)

    glassPanelRounded(ctx, dx, dy, dw, dh, 18, gAlpha(0.22), 'rgba(80,160,255,0.55)')
    glassPanelRounded(ctx, dx + 8, dy + 8, dw - 16, 32, 8, gAlpha(0.28), 'rgba(80,160,255,0.6)')

    ctx.fillStyle = landingMode ? 'rgba(200,230,255,0.95)' : 'rgba(160,210,255,0.75)'
    ctx.font = 'bold 11px "SF Pro Display", "Segoe UI", system-ui, sans-serif'
    ctx.fillText('Workforce Analytics', dx + 44, dy + 28)

    for (let i = 0; i < 3; i++) {
      ctx.beginPath()
      ctx.arc(dx + 24 + i * 16, dy + 24, 4, 0, Math.PI * 2)
      ctx.fillStyle = ['rgba(255,100,80,0.8)', 'rgba(255,200,50,0.8)', 'rgba(50,220,100,0.8)'][i]
      ctx.fill()
    }

    const bars = [0.55, 0.8, 0.45, 0.9, 0.65, 0.75, 0.5]
    bars.forEach((v, i) => {
      const bx = dx + 20 + i * 40
      const bh2 = v * 80
      const by2 = dy + dh - 30 - bh2
      const barG = ctx.createLinearGradient(bx, by2 + bh2, bx, by2)
      barG.addColorStop(0, 'rgba(0,120,255,0.9)')
      barG.addColorStop(0.5, 'rgba(0,200,255,0.8)')
      barG.addColorStop(1, 'rgba(100,255,200,0.6)')
      ctx.fillStyle = barG
      roundRect(ctx, bx, by2, 22, bh2, 4)
      ctx.fill()
      ctx.fillStyle = 'rgba(100,220,255,0.3)'
      roundRect(ctx, bx + 2, by2, 18, 6, 3)
      ctx.fill()
    })

    ctx.beginPath()
    ctx.moveTo(dx + 18, dy + dh - 70)
    ctx.bezierCurveTo(dx + 70, dy + dh - 120, dx + 160, dy + dh - 90, dx + dw - 20, dy + dh - 140)
    ctx.strokeStyle = 'rgba(0,220,180,0.85)'
    ctx.lineWidth = 2
    ctx.stroke()
    ctx.shadowBlur = 8
    ctx.shadowColor = 'rgba(0,220,180,0.6)'
    ctx.stroke()
    ctx.shadowBlur = 0

    ctx.beginPath()
    ctx.arc(dx + dw - 20, dy + dh - 140, 5, 0, Math.PI * 2)
    ctx.fillStyle = 'rgba(0,220,180,1)'
    ctx.fill()

    const px2 = dx + dw - 52
    const py2 = dy + 68
    const pr = 22
    const slices = [
      { a: 0, end: 1.4, c: 'rgba(0,180,255,0.9)' },
      { a: 1.4, end: 2.6, c: 'rgba(50,230,120,0.9)' },
      { a: 2.6, end: Math.PI * 2, c: 'rgba(100,100,220,0.8)' },
    ]
    slices.forEach((s) => {
      ctx.beginPath()
      ctx.moveTo(px2, py2)
      ctx.arc(px2, py2, pr, s.a, s.end)
      ctx.closePath()
      ctx.fillStyle = s.c
      ctx.fill()
    })

    const chips = [
      { l: '92%', s: 'Hire Rate', c: 'rgba(0,180,255,0.85)' },
      { l: '4.2K', s: 'Employees', c: 'rgba(50,220,120,0.85)' },
    ]
    chips.forEach((ch, i) => {
      const cx2 = dx + 24 + i * 110
      const cy2 = dy + 62
      glassPanelRounded(ctx, cx2, cy2, 95, 44, 8, gAlpha(0.32), 'rgba(80,160,255,0.5)')
      ctx.fillStyle = ch.c
      ctx.font = 'bold 16px "SF Pro Display", "Segoe UI", system-ui, sans-serif'
      ctx.fillText(ch.l, cx2 + 10, cy2 + 18)
      ctx.fillStyle = 'rgba(160,200,255,0.7)'
      ctx.font = '10px "SF Pro Display", "Segoe UI", system-ui, sans-serif'
      ctx.fillText(ch.s, cx2 + 10, cy2 + 34)
    })
  }

  function drawTalentAcquisition(ctx) {
    const p = parallax(14)
    const bx = px(0.48) + p.x
    const by = py(0.14) + p.y + Math.sin(t * 0.9) * 5
    const bw = landingMode ? W * 0.2 : 140
    const bh = landingMode ? H * 0.2 : 105

    glassPanelRounded(ctx, bx, by, bw, bh, 12, gAlpha(0.3), 'rgba(140,80,255,0.55)')

    ctx.fillStyle = 'rgba(210,190,255,0.98)'
    ctx.font = 'bold 11px "SF Pro Display", "Segoe UI", system-ui, sans-serif'
    ctx.fillText('Talent Acquisition', bx + 12, by + 20)

    const stages = [0.92, 0.72, 0.52, 0.34]
    stages.forEach((sw, i) => {
      const fw = bw * sw * 0.65
      const fx = bx + (bw - fw) / 2
      const fy = by + 30 + i * 15
      roundRect(ctx, fx, fy, fw, 11, 4)
      ctx.fillStyle = `rgba(140,90,255,${0.35 + i * 0.12})`
      ctx.fill()
    })

    ctx.fillStyle = 'rgba(180,220,255,0.95)'
    ctx.font = 'bold 16px system-ui, sans-serif'
    ctx.fillText('248', bx + 12, by + bh - 16)
    ctx.fillStyle = 'rgba(170,190,255,0.8)'
    ctx.font = '9px system-ui, sans-serif'
    ctx.fillText('Active Candidates', bx + 50, by + bh - 16)

    for (let i = 0; i < 4; i++) {
      const dotX = bx + bw - 20
      const dotY = by + 36 + i * 14
      ctx.beginPath()
      ctx.arc(dotX, dotY, 3, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(${100 + i * 30},180,255,0.9)`
      ctx.fill()
    }
  }

  function drawAICore(ctx) {
    const p = parallax(22)
    const cx = px(0.38) + p.x
    const cy = py(0.36) + p.y
    const boost = hoverBoost ? 6 : 0
    const r = 38 + Math.sin(t * 2) * 2 + boost

    for (let i = 3; i > 0; i--) {
      ctx.beginPath()
      ctx.arc(cx, cy, r + i * 18, 0, Math.PI * 2)
      ctx.strokeStyle = `rgba(0,150,255,${0.06 * i + (hoverBoost ? 0.02 : 0)})`
      ctx.lineWidth = i * 3
      ctx.stroke()
    }

    for (let a = 0; a < 3; a++) {
      ctx.save()
      ctx.translate(cx, cy)
      ctx.rotate(t * (0.8 + a * 0.3) + (a * Math.PI * 2) / 3)
      ctx.beginPath()
      ctx.arc(0, 0, r + 6, 0, Math.PI * 0.7)
      ctx.strokeStyle = `rgba(${a === 0 ? '0,200,255' : a === 1 ? '80,255,180' : '160,100,255'},${hoverBoost ? 1 : 0.8})`
      ctx.lineWidth = 2
      ctx.stroke()
      ctx.restore()
    }

    const cg = ctx.createRadialGradient(cx, cy, 0, cx, cy, r)
    cg.addColorStop(0, 'rgba(30,120,255,0.95)')
    cg.addColorStop(0.4, 'rgba(0,80,220,0.85)')
    cg.addColorStop(0.7, 'rgba(0,40,120,0.7)')
    cg.addColorStop(1, 'rgba(0,20,60,0.5)')
    ctx.beginPath()
    ctx.arc(cx, cy, r, 0, Math.PI * 2)
    ctx.fillStyle = cg
    ctx.fill()
    ctx.strokeStyle = 'rgba(80,180,255,0.7)'
    ctx.lineWidth = 1.5
    ctx.stroke()

    const nodes = []
    for (let n = 0; n < 8; n++) {
      const ang = (n / 8) * Math.PI * 2 + t * 0.3
      const nr = r * 0.55
      const nx = cx + Math.cos(ang) * nr
      const ny = cy + Math.sin(ang) * nr
      nodes.push({ x: nx, y: ny })
      ctx.beginPath()
      ctx.arc(nx, ny, 3, 0, Math.PI * 2)
      ctx.fillStyle = 'rgba(160,220,255,0.9)'
      ctx.fill()
    }

    for (let n = 0; n < nodes.length; n += 2) {
      ctx.beginPath()
      ctx.moveTo(nodes[n].x, nodes[n].y)
      ctx.lineTo(nodes[(n + 3) % nodes.length].x, nodes[(n + 3) % nodes.length].y)
      ctx.strokeStyle = 'rgba(0,200,255,0.2)'
      ctx.lineWidth = 0.8
      ctx.stroke()
    }

    const pulseR = (((t * 60) % 100) / 100) * 60 + r
    ctx.beginPath()
    ctx.arc(cx, cy, pulseR, 0, Math.PI * 2)
    ctx.strokeStyle = `rgba(0,180,255,${0.4 * (1 - (pulseR - r) / 60) * (hoverBoost ? 1.4 : 1)})`
    ctx.lineWidth = 1.5
    ctx.stroke()

    ctx.fillStyle = 'rgba(160,220,255,0.85)'
    ctx.font = 'bold 10px "SF Pro Display", "Segoe UI", system-ui, sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText('AI ENGINE', cx, cy + r + 16)
    ctx.textAlign = 'left'

    const tcx = px(0.6) + parallax(14).x
    const tcy = H * 0.5 + parallax(14).y
    ctx.beginPath()
    ctx.moveTo(cx + r, cy)
    ctx.bezierCurveTo(cx + r + 40, cy, tcx - 80, tcy - 40, tcx - 160, tcy - 20)
    const streamG = ctx.createLinearGradient(cx, cy, tcx, tcy)
    streamG.addColorStop(0, 'rgba(0,200,255,0.6)')
    streamG.addColorStop(1, 'rgba(0,200,255,0.0)')
    ctx.strokeStyle = streamG
    ctx.lineWidth = 1.5
    ctx.setLineDash([4, 6])
    ctx.stroke()
    ctx.setLineDash([])
  }

  function drawResumeCards(ctx) {
    const cards = [
      { nx: 0.18, ny: 0.48, amp: 6, spd: 1.2, score: 92, color: '#00B4FF' },
      { nx: 0.24, ny: 0.28, amp: 7, spd: 0.9, score: 87, color: '#00E87E' },
      { nx: 0.46, ny: 0.22, amp: 5, spd: 1.5, score: 94, color: '#8B5CF6' },
    ]
    cards.forEach((c, i) => {
      const p = parallax(18 + i * 4)
      const y = py(c.ny) + Math.sin(t * c.spd + i) * c.amp + p.y
      const x = px(c.nx) + Math.cos(t * c.spd * 0.7 + i) * 4 + p.x
      glassPanelRounded(ctx, x, y, 110, 68, 10, gAlpha(0.24), `${c.color}66`)

      ctx.beginPath()
      ctx.arc(x + 20, y + 20, 11, 0, Math.PI * 2)
      const avG = ctx.createRadialGradient(x + 20, y + 20, 0, x + 20, y + 20, 11)
      avG.addColorStop(0, 'rgba(80,160,255,0.8)')
      avG.addColorStop(1, 'rgba(20,60,180,0.6)')
      ctx.fillStyle = avG
      ctx.fill()
      ctx.strokeStyle = 'rgba(120,200,255,0.5)'
      ctx.lineWidth = 1
      ctx.stroke()

      for (let b = 0; b < 3; b++) {
        const bw = [45, 30, 38][b]
        const bc = x + 36
        const bcy = y + 8 + b * 18
        roundRect(ctx, bc, bcy, bw, 10, 5)
        ctx.fillStyle = `rgba(${i === 0 ? '0,140,255' : i === 1 ? '0,180,100' : '120,80,220'},0.5)`
        ctx.fill()
      }

      glassPanelRounded(ctx, x + 74, y + 8, 30, 18, 5, 0.4, `${c.color}88`)
      ctx.fillStyle = c.color
      ctx.font = 'bold 10px "SF Pro Display", "Segoe UI", system-ui, sans-serif'
      ctx.fillText(`${c.score}%`, x + 78, y + 21)
      ctx.fillStyle = 'rgba(160,220,255,0.5)'
      ctx.font = '9px "SF Pro Display", "Segoe UI", system-ui, sans-serif'
      ctx.fillText('AI Match', x + 8, y + 58)

      ctx.beginPath()
      ctx.moveTo(x + 10, y + 1)
      ctx.lineTo(x + 100, y + 1)
      ctx.strokeStyle = `${c.color}88`
      ctx.lineWidth = 1.5
      ctx.stroke()
    })
  }

  function drawPayroll(ctx) {
    const p = parallax(16)
    const px0 = px(0.7) + p.x
    const py0 = py(0.12) + p.y + Math.sin(t * 0.8) * 5
    const w = landingMode ? W * 0.19 : 130
    const h = landingMode ? H * 0.17 : 88

    glassPanelRounded(ctx, px0, py0, w, h, 12, gAlpha(0.32), 'rgba(50,220,130,0.5)')

    const rcx = px0 + w / 2
    const rcy = py0 + h / 2 + 10
    for (let i = 0; i < 3; i++) {
      ctx.beginPath()
      ctx.ellipse(rcx, rcy, 26 + i * 9, 11 + i * 4, t * 0.5 + i * 0.8, 0, Math.PI * 2)
      ctx.strokeStyle = `rgba(0,255,200,${0.35 - i * 0.08})`
      ctx.lineWidth = 1.2
      ctx.stroke()
    }

    ctx.fillStyle = 'rgba(210,255,235,0.98)'
    ctx.font = 'bold 10px "SF Pro Display", system-ui, sans-serif'
    ctx.fillText('Quantum Payroll', px0 + 10, py0 + 18)
    ctx.fillStyle = 'rgba(50,255,160,0.98)'
    ctx.font = 'bold 17px system-ui, sans-serif'
    ctx.fillText('$24,500', px0 + 10, py0 + 42)

    ;['USD', 'EUR', 'INR'].forEach((cur, i) => {
      glassPanelRounded(ctx, px0 + 8 + i * 34, py0 + h - 30, 30, 18, 4, gAlpha(0.35), 'rgba(50,220,130,0.55)')
      ctx.fillStyle = 'rgba(160,255,210,0.95)'
      ctx.font = '8px system-ui, sans-serif'
      ctx.fillText(cur, px0 + 14 + i * 34, py0 + h - 16)
    })

    const px1 = px0 + 6
    const py1 = py0 + h + 10 + Math.sin(t * 0.6) * 4
    const w2 = w - 12
    const h2 = h * 0.58
    glassPanelRounded(ctx, px1, py1, w2, h2, 10, gAlpha(0.28), 'rgba(0,160,255,0.45)')
    ctx.fillStyle = 'rgba(0,210,255,0.95)'
    ctx.font = 'bold 14px system-ui, sans-serif'
    ctx.fillText('₹1.2M', px1 + 10, py1 + 24)
    ctx.fillStyle = 'rgba(160,220,255,0.8)'
    ctx.font = '9px system-ui, sans-serif'
    ctx.fillText('Multi-Entity', px1 + 10, py1 + 40)

    for (let b = 0; b < 5; b++) {
      const bh3 = 8 + ((b * 7 + 3) % 18)
      const bg2 = ctx.createLinearGradient(0, py1 + h2 - 6 - bh3, 0, py1 + h2 - 6)
      bg2.addColorStop(0, 'rgba(50,220,130,0.8)')
      bg2.addColorStop(1, 'rgba(0,120,80,0.4)')
      ctx.fillStyle = bg2
      roundRect(ctx, px1 + 10 + b * 14, py1 + h2 - 6 - bh3, 9, bh3, 2)
      ctx.fill()
    }
  }

  function drawLeave(ctx) {
    const p = parallax(15)
    const lx = px(0.74) + p.x
    const ly = py(0.5) + p.y
    const drift2 = Math.sin(t * 1.0 + 1) * 6
    glassPanelRounded(ctx, lx, ly + drift2, 120, 100, 10, gAlpha(0.28), 'rgba(120,80,255,0.5)')

    ctx.fillStyle = 'rgba(190,170,255,0.95)'
    ctx.font = 'bold 10px system-ui, sans-serif'
    ctx.fillText('Leave Management', lx + 12, ly + drift2 + 18)
    ctx.fillStyle = 'rgba(160,180,255,0.65)'
    ctx.font = '8px system-ui, sans-serif'
    ctx.fillText('JUNE 2025', lx + 12, ly + drift2 + 30)

    const days = ['M', 'T', 'W', 'T', 'F']
    days.forEach((d, i) => {
      ctx.fillStyle = 'rgba(160,180,255,0.5)'
      ctx.font = '8px system-ui, sans-serif'
      ctx.fillText(d, lx + 10 + i * 20, ly + drift2 + 42)
    })

    const colors = [
      'rgba(50,220,120,0.85)',
      'rgba(0,160,255,0.7)',
      'rgba(255,200,50,0.7)',
      'rgba(80,80,200,0.6)',
      'rgba(50,220,120,0.85)',
    ]
    for (let r = 0; r < 3; r++) {
      for (let c = 0; c < 5; c++) {
        if (LEAVE_GRID[r][c]) {
          const bc = r === 1 && c === 2 ? 'rgba(255,100,80,0.8)' : colors[c]
          roundRect(ctx, lx + 8 + c * 20, ly + drift2 + 50 + r * 16, 14, 10, 3)
          ctx.fillStyle = bc
          ctx.fill()
        }
      }
    }

    ctx.fillStyle = 'rgba(50,220,120,0.9)'
    ctx.font = 'bold 13px system-ui, sans-serif'
    ctx.fillText('✓ Approved', lx + 10, ly + drift2 + 98)
  }

  function drawPipeline(ctx) {
    const p = parallax(10)
    const stages = ['Applied', 'Screen', 'Interview', 'Offer', 'Hired']
    const py2 = py(0.82) + p.y
    const startX = px(0.28) + p.x
    const endX = px(0.92) + p.x
    const step = (endX - startX) / 4

    const pathG = ctx.createLinearGradient(startX, 0, endX, 0)
    pathG.addColorStop(0, 'rgba(0,100,255,0.5)')
    pathG.addColorStop(0.5, 'rgba(0,180,255,0.7)')
    pathG.addColorStop(1, 'rgba(50,220,120,0.8)')
    ctx.beginPath()
    ctx.moveTo(startX, py2)
    ctx.bezierCurveTo(startX + 50, py2 - 10, endX - 50, py2 - 10, endX, py2)
    ctx.strokeStyle = pathG
    ctx.lineWidth = 3
    ctx.shadowBlur = 10
    ctx.shadowColor = 'rgba(0,150,255,0.6)'
    ctx.stroke()
    ctx.shadowBlur = 0

    ctx.beginPath()
    ctx.moveTo(startX, py2)
    ctx.bezierCurveTo(startX + 50, py2 - 10, endX - 50, py2 - 10, endX, py2)
    ctx.strokeStyle = 'rgba(0,150,255,0.15)'
    ctx.lineWidth = 14
    ctx.stroke()

    stages.forEach((s, i) => {
      const sx = startX + i * step
      const isHired = i === 4
      const isActive = i === 2
      if (isHired || isActive) {
        const ng = ctx.createRadialGradient(sx, py2, 0, sx, py2, 22)
        ng.addColorStop(0, isHired ? 'rgba(50,220,120,0.4)' : 'rgba(0,180,255,0.3)')
        ng.addColorStop(1, 'rgba(0,0,0,0)')
        ctx.fillStyle = ng
        ctx.beginPath()
        ctx.arc(sx, py2, 22, 0, Math.PI * 2)
        ctx.fill()
      }
      ctx.beginPath()
      ctx.arc(sx, py2, isHired ? 13 : 10, 0, Math.PI * 2)
      ctx.fillStyle = isHired
        ? 'rgba(50,220,120,0.95)'
        : isActive
          ? 'rgba(0,200,255,0.95)'
          : 'rgba(20,80,180,0.8)'
      ctx.fill()
      ctx.strokeStyle = isHired ? 'rgba(100,255,160,0.8)' : 'rgba(80,160,255,0.6)'
      ctx.lineWidth = 1.5
      ctx.stroke()
      ctx.fillStyle = isHired ? 'rgba(100,255,160,0.95)' : 'rgba(160,210,255,0.85)'
      ctx.font = `${isHired ? 'bold ' : ''}10px "SF Pro Display", "Segoe UI", system-ui, sans-serif`
      ctx.textAlign = 'center'
      ctx.fillText(s, sx, py2 + 26)
      if (i < 4) {
        const prog = (t * 0.4 + i * 0.25) % 1.0
        const dx2 = sx + prog * step
        const dy2 = py2 - Math.sin(prog * Math.PI) * 10
        ctx.beginPath()
        ctx.arc(dx2, dy2, 5, 0, Math.PI * 2)
        const candG = ctx.createRadialGradient(dx2, dy2, 0, dx2, dy2, 5)
        candG.addColorStop(0, 'rgba(255,220,80,1)')
        candG.addColorStop(1, 'rgba(255,160,20,0.7)')
        ctx.fillStyle = candG
        ctx.fill()
        ctx.strokeStyle = 'rgba(255,200,50,0.8)'
        ctx.lineWidth = 1
        ctx.stroke()
      }
    })
    ctx.textAlign = 'left'
  }

  function drawStreams(ctx) {
    const acx = px(0.38) + parallax(22).x
    const acy = py(0.36) + parallax(22).y
    const targets = [
      { x: px(0.18) + parallax(18).x, y: py(0.48) + parallax(18).y },
      { x: px(0.28) + parallax(20).x, y: py(0.3) + parallax(20).y },
      { x: px(0.75) + parallax(16).x, y: py(0.26) + parallax(16).y },
      { x: px(0.76) + parallax(15).x, y: py(0.54) + parallax(15).y },
    ]
    targets.forEach((tgt) => {
      ctx.beginPath()
      const mx = (acx + tgt.x) / 2
      const my = (acy + tgt.y) / 2 - 30
      ctx.moveTo(acx, acy)
      ctx.quadraticCurveTo(mx, my, tgt.x, tgt.y)
      const sg = ctx.createLinearGradient(acx, acy, tgt.x, tgt.y)
      sg.addColorStop(0, 'rgba(0,180,255,0.7)')
      sg.addColorStop(1, 'rgba(0,180,255,0.0)')
      ctx.strokeStyle = sg
      ctx.lineWidth = 1
      ctx.setLineDash([3, 7])
      ctx.stroke()
      ctx.setLineDash([])
      const prog = (t * 0.5) % 1
      const px2 = acx * (1 - prog) * (1 - prog) + 2 * mx * prog * (1 - prog) + tgt.x * prog * prog
      const py2 = acy * (1 - prog) * (1 - prog) + 2 * my * prog * (1 - prog) + tgt.y * prog * prog
      ctx.beginPath()
      ctx.arc(px2, py2, 3, 0, Math.PI * 2)
      ctx.fillStyle = 'rgba(100,220,255,0.9)'
      ctx.fill()
    })
  }

  function draw3DChart(ctx) {
    const p = parallax(12)
    const cx = px(0.55) + p.x
    const cy = py(0.68) + p.y
    const bars = [0.6, 0.85, 0.45, 0.9, 0.7]
    const barW = Math.max(12, W * 0.02)
    const gap = Math.max(4, W * 0.009)
    const maxBarH = H * 0.09
    const totalW = bars.length * (barW + gap)
    const startBx = cx - totalW / 2
    bars.forEach((v, i) => {
      const bx = startBx + i * (barW + gap)
      const bh2 = v * maxBarH
      const by2 = cy - bh2
      ctx.beginPath()
      ctx.moveTo(bx, by2)
      ctx.lineTo(bx + barW, by2)
      ctx.lineTo(bx + barW + 8, by2 - 8)
      ctx.lineTo(bx + 8, by2 - 8)
      ctx.closePath()
      ctx.fillStyle = `rgba(0,${140 + i * 20},255,0.8)`
      ctx.fill()
      ctx.beginPath()
      ctx.moveTo(bx + barW, by2)
      ctx.lineTo(bx + barW + 8, by2 - 8)
      ctx.lineTo(bx + barW + 8, cy - 8)
      ctx.lineTo(bx + barW, cy)
      ctx.closePath()
      ctx.fillStyle = `rgba(0,${80 + i * 15},180,0.6)`
      ctx.fill()
      const fg3 = ctx.createLinearGradient(bx, by2, bx, cy)
      fg3.addColorStop(0, `rgba(0,${160 + i * 15},255,0.9)`)
      fg3.addColorStop(1, `rgba(0,${60 + i * 15},180,0.6)`)
      ctx.fillStyle = fg3
      ctx.fillRect(bx, by2, barW, bh2)
      ctx.beginPath()
      ctx.moveTo(bx, by2)
      ctx.lineTo(bx + barW, by2)
      ctx.strokeStyle = 'rgba(100,220,255,0.9)'
      ctx.lineWidth = 1.5
      ctx.stroke()
    })
    ctx.fillStyle = 'rgba(120,200,255,0.6)'
    ctx.font = '9px system-ui, sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText('Growth Analytics', cx, cy + 14)
    ctx.textAlign = 'left'
  }

  function drawLeftDecor(ctx) {
    const p = parallax(6)
    const lx = 32 + p.x
    const ly = H * 0.22 + p.y
    ctx.fillStyle = 'rgba(40,100,200,0.3)'
    ctx.font = 'bold 28px "SF Pro Display", "Segoe UI", system-ui, sans-serif'
    ctx.fillText('HRMS', lx, ly)
    ctx.font = '13px "SF Pro Display", "Segoe UI", system-ui, sans-serif'
    ctx.fillStyle = 'rgba(80,150,255,0.3)'
    ctx.fillText('AI-Powered Workforce Platform', lx, ly + 24)
    ctx.beginPath()
    ctx.moveTo(lx - 8, ly - 36)
    ctx.lineTo(lx - 8, ly + 60)
    ctx.strokeStyle = 'rgba(0,120,255,0.3)'
    ctx.lineWidth = 2
    ctx.stroke()
    const stats = [
      { l: '98% Accuracy', y: 0 },
      { l: '2.4s Parse Time', y: 28 },
      { l: '500+ Integrations', y: 56 },
    ]
    stats.forEach((s, i) => {
      const sw = 130
      glassPanelRounded(ctx, lx, ly + 60 + s.y, sw, 22, 11, 0.15, 'rgba(40,100,200,0.3)')
      const dot_c = ['rgba(0,220,120,0.9)', 'rgba(0,180,255,0.9)', 'rgba(180,100,255,0.9)'][i]
      ctx.beginPath()
      ctx.arc(lx + 12, ly + 60 + s.y + 11, 4, 0, Math.PI * 2)
      ctx.fillStyle = dot_c
      ctx.fill()
      ctx.fillStyle = 'rgba(140,190,255,0.6)'
      ctx.font = '9px system-ui, sans-serif'
      ctx.fillText(s.l, lx + 22, ly + 60 + s.y + 14)
    })
  }

  function render(ctx) {
    smoothMouse.x += (targetMouse.x - smoothMouse.x) * 0.055
    smoothMouse.y += (targetMouse.y - smoothMouse.y) * 0.055

    const scrollBoost = 0.9 + scrollProgress * 0.2
    t += 0.008 * timeScale * scrollBoost

    ctx.clearRect(0, 0, W, H)
    drawBG(ctx)
    drawOrbits(ctx)
    drawStreams(ctx)
    drawDashboard(ctx)
    drawTalentAcquisition(ctx)
    drawAICore(ctx)
    drawResumeCards(ctx)
    drawPayroll(ctx)
    drawLeave(ctx)
    if (landingMode || quality === 'high') draw3DChart(ctx)
    drawPipeline(ctx)
    if (quality === 'high' && showLeftDecor) drawLeftDecor(ctx)
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
    setHoverBoost(boost) {
      hoverBoost = boost
    },
    setShowLeftDecor(show) {
      showLeftDecor = show
    },
    setLandingMode(mode) {
      landingMode = mode
    },
    hitTestAICore(normX, normY) {
      const cx = 0.38
      const cy = 0.36
      const dx = normX - cx
      const dy = normY - cy
      return dx * dx + dy * dy < 0.014
    },
    render,
  }
}
