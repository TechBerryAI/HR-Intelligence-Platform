/** Map normalized design coords (0–1) to viewport pixels; landing shifts visuals right of hero text */
export const LANDING_TEXT_COL = 0.42

export function lp(nx, ny, W, H, landingMode = false) {
  if (!landingMode) return { x: nx * W, y: ny * H }
  return {
    x: W * (LANDING_TEXT_COL + nx * (1 - LANDING_TEXT_COL)),
    y: ny * H,
  }
}

export function lSize(nw, nh, W, H, landingMode = false) {
  if (!landingMode) return { w: nw * W, h: nh * H }
  return {
    w: nw * W * (1 - LANDING_TEXT_COL),
    h: nh * H,
  }
}

export function glassAlpha(base, landingMode) {
  return landingMode ? Math.min(base + 0.14, 0.55) : base
}
