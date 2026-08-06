/** Landing / home hero video — API or CDN; never a repo-local asset path. */
export const HERO_VIDEO_SRC =
  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_HERO_VIDEO_URL) ||
  '/api/media/public/hero-video'
