/** Landing / home hero video — streamed from MEDIA_ROOT via API (or CDN override). */
export const HERO_VIDEO_SRC =
  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_HERO_VIDEO_URL) ||
  '/api/media/public/hero-video'

/** One cache-bust retry URL for transient 404 / proxy misses. */
export function heroVideoRetrySrc(base = HERO_VIDEO_SRC) {
  const sep = String(base).includes('?') ? '&' : '?'
  return `${base}${sep}t=${Date.now()}`
}
