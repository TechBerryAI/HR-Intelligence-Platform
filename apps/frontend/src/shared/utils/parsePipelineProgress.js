/**
 * Map Document Intelligence Engine stages onto the upload overlay steps.
 * Resume and JD pipelines emit stages in slightly different orders.
 */

export const RESUME_OVERLAY_STEPS = [
  { text: 'Reading Document', stages: ['cache', 'persist_raw', 'text', 'layout'] },
  { text: 'Detecting Sections', stages: ['sections', 'deterministic'] },
  { text: 'Knowledge & Semantics', stages: ['coverage', 'semantic', 'knowledge'] },
  { text: 'Validating & Autofill', stages: ['validate', 'persist', 'toon'] },
];

export const JD_OVERLAY_STEPS = [
  { text: 'Reading Job Description', stages: ['cache', 'persist_raw', 'text', 'layout'] },
  { text: 'Parsing Requirements', stages: ['sections', 'deterministic'] },
  { text: 'Knowledge & Semantics', stages: ['knowledge', 'coverage', 'semantic'] },
  { text: 'Preparing Form', stages: ['validate', 'persist', 'toon'] },
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
  const msg = String(message || '').trim();
  if (msg) return msg;
  return STAGE_HINTS[stage] || 'Live pipeline progress';
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

export const OVERLAY_STEP_DWELL_MS = 550;
