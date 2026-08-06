/** Landing / home hero video — streamed from Postgres via API (or CDN override). */
export const HERO_VIDEO_SRC =
  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_HERO_VIDEO_URL) ||
  '/api/media/public/hero-video'
