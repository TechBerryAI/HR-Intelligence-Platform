/**
 * Video-accurate hero background — reference MP4 is the source of truth.
 * @see /demo/landing-hero.mp4 (make_it_look_as_a_website_so_t.mp4)
 */
export const VIDEO_HERO_SRC = '/demo/landing-hero.mp4'

export const VIDEO_MODULES = [
  {
    id: 'talent_acquisition',
    title: 'Talent Acquisition',
    nx: 0.48,
    ny: 0.14,
    drawFn: 'drawTalentAcquisition',
    status: 'implemented',
  },
  {
    id: 'quantum_payroll',
    title: 'Quantum Payroll',
    nx: 0.7,
    ny: 0.12,
    drawFn: 'drawPayroll',
    status: 'implemented',
  },
  {
    id: 'workforce_analytics',
    title: 'Workforce Analytics',
    nx: 0.6,
    ny: 0.5,
    drawFn: 'drawDashboard',
    status: 'implemented',
  },
  {
    id: 'ai_engine',
    title: 'AI ENGINE',
    nx: 0.38,
    ny: 0.36,
    drawFn: 'drawAICore',
    status: 'implemented',
  },
  {
    id: 'ai_match_cards',
    title: 'AI Match',
    nx: 0.24,
    ny: 0.28,
    drawFn: 'drawResumeCards',
    status: 'implemented',
  },
  {
    id: 'leave_management',
    title: 'Leave Management',
    nx: 0.74,
    ny: 0.5,
    drawFn: 'drawLeave',
    status: 'implemented',
  },
  {
    id: 'growth_analytics',
    title: 'Growth Analytics',
    nx: 0.55,
    ny: 0.68,
    drawFn: 'draw3DChart',
    status: 'implemented',
  },
  {
    id: 'recruitment_pipeline',
    title: 'Recruitment Pipeline',
    nx: 0.6,
    ny: 0.82,
    drawFn: 'drawPipeline',
    status: 'implemented',
  },
]

export const LANDING_RENDER_ORDER = [
  'drawBG',
  'drawOrbits',
  'drawStreams',
  'drawDashboard',
  'drawTalentAcquisition',
  'drawAICore',
  'drawResumeCards',
  'drawPayroll',
  'drawLeave',
  'draw3DChart',
  'drawPipeline',
]
