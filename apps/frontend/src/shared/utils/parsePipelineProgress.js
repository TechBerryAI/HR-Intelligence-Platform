/**
 * Map Document Intelligence Engine stages onto the upload overlay steps.
 * Resume and JD pipelines emit stages in slightly different orders.
 */

export const RESUME_OVERLAY_STEPS = [
  { text: 'Reading Document', stages: ['upload', 'client_wait', 'cache', 'persist_raw', 'text', 'layout'] },
  { text: 'Detecting Sections', stages: ['sections', 'deterministic'] },
  { text: 'Knowledge & Semantics', stages: ['coverage', 'semantic', 'knowledge'] },
  { text: 'Validating & Autofill', stages: ['validate', 'persist', 'toon', 'deliver', 'autofill'] },
];

export const JD_OVERLAY_STEPS = [
  { text: 'Reading Job Description', stages: ['upload', 'client_wait', 'cache', 'persist_raw', 'text', 'layout'] },
  { text: 'Parsing Requirements', stages: ['sections', 'deterministic'] },
  { text: 'Knowledge & Semantics', stages: ['knowledge', 'coverage', 'semantic'] },
  { text: 'Preparing Form', stages: ['validate', 'persist', 'toon', 'deliver', 'autofill'] },
];

export const RESUME_STAGE_ORDER = [
  'cache',
  'persist_raw',
  'text',
  'layout',
  'sections',
  'deterministic',
  'coverage',
  'semantic',
  'knowledge',
  'validate',
  'persist',
];

export const JD_STAGE_ORDER = [
  'cache',
  'persist_raw',
  'text',
  'layout',
  'sections',
  'deterministic',
  'knowledge',
  'coverage',
  'semantic',
  'validate',
  'persist',
];

export const STAGE_HINTS = {
  upload: 'Uploading resume',
  client_wait: 'Waiting for parser',
  cache: 'Checking document cache',
  persist_raw: 'Saving original file',
  text: 'Extracting text',
  layout: 'Analyzing layout',
  sections: 'Detecting sections',
  deterministic: 'Reading structured fields',
  coverage: 'Recovering missing fields',
  semantic: 'Understanding content',
  knowledge: 'Normalizing knowledge',
  validate: 'Validating results',
  persist: 'Preparing form autofill',
  toon: 'Preparing form autofill',
  deliver: 'Sending result',
  autofill: 'Filling the form',
};

export function overlayStepsFor(type) {
  return type === 'jd' ? JD_OVERLAY_STEPS : RESUME_OVERLAY_STEPS;
}

export function overlayStepIndex(type, stage) {
  if (!stage) return -1;
  return overlayStepsFor(type).findIndex((s) => (s.stages || []).includes(stage));
}

export function progressPctForStage(type, stage) {
  const order = type === 'jd' ? JD_STAGE_ORDER : RESUME_STAGE_ORDER;
  const idx = order.indexOf(stage);
  if (idx < 0) return null;
  return Math.round(((idx + 1) / order.length) * 100);
}

export function hintForStage(stage, message) {
  const fallback = STAGE_HINTS[stage] || 'Live pipeline progress';
  return userFacingParseMessage(message, fallback);
}

/** Engine/cache version tags must never appear in candidate or recruiter UI. */
const INTERNAL_ENGINE_LABEL =
  /ai-runtime|canonical-v\d+|extract-shortlist|\+deterministic|\+hybrid|document-intelligence-v\d+|text-fallback/i;

export function isInternalEngineLabel(message) {
  return INTERNAL_ENGINE_LABEL.test(String(message || ''));
}

export function userFacingParseMessage(message, fallback = '') {
  const stripped = String(message || '')
    .replace(/\s*\((?:[^)]*(?:ai-runtime|canonical-v\d+|extract-shortlist|\+deterministic|\+hybrid)[^)]*)\)\s*/gi, ' ')
    .replace(/\s{2,}/g, ' ')
    .trim();
  if (!stripped || isInternalEngineLabel(stripped)) return fallback;
  return stripped;
}

export function isPipelineComplete(ev) {
  const stage = ev?.stage;
  return ev?.status === 'completed' && (stage === 'persist' || stage === 'toon');
}

/** Time to keep the overlay open so skipped steps can catch up visually. */
export function overlayCatchupMs(type, lastStage) {
  const lastIdx = overlayStepsFor(type).length - 1;
  const idx = overlayStepIndex(type, lastStage);
  const from = idx < 0 ? 0 : idx;
  return 500 + Math.max(0, lastIdx - from) * 600;
}

export const OVERLAY_STEP_DWELL_MS = 200;

/** Format overlay / dashboard step times. */
export function formatStepMs(ms) {
  const n = Number(ms)
  if (!Number.isFinite(n) || n < 0) return '—'
  if (n < 1000) return `${Math.round(n)} ms`
  if (n < 60_000) return `${(n / 1000).toFixed(n < 10_000 ? 1 : 0)} s`
  const m = Math.floor(n / 60_000)
  const s = Math.round((n % 60_000) / 1000)
  return `${m}m ${s}s`
}

/**
 * Track per-stage durations from SSE (prefers server duration_ms so buffered
 * streams still report the real extract/OCR time).
 */
export function createStageClock() {
  const starts = Object.create(null)
  const spans = []
  return {
    onEvent(ev) {
      const stage = ev?.stage
      if (!stage) return
      const status = String(ev.status || '').toLowerCase()
      const serverMs = Number(ev.duration_ms ?? ev.detail?.duration_ms)
      if (status === 'started') {
        starts[stage] = performance.now()
        return
      }
      if (!['completed', 'failed', 'skipped'].includes(status)) return
      const local = starts[stage] != null ? performance.now() - starts[stage] : 0
      delete starts[stage]
      const duration_ms = Math.max(Number.isFinite(serverMs) ? serverMs : 0, local)
      spans.push({ key: stage, duration_ms: Math.max(0, duration_ms), status })
    },
    getSpans() {
      return spans.slice()
    },
  }
}
