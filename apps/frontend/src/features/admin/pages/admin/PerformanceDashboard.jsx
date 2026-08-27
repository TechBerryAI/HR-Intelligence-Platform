/**
 * Admin Developer Mode — parse step timings (resume / JD / bulk).
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Navigate } from 'react-router-dom'
import {
  FiActivity,
  FiCheck,
  FiChevronDown,
  FiClock,
  FiFileText,
  FiLayers,
  FiMinus,
  FiRefreshCw,
  FiTrash2,
  FiUpload,
  FiX,
} from 'react-icons/fi'
import HeadHrLayout from '@/features/organization/pages/head-hr/HeadHrLayout.jsx'
import { useToast } from '@/shared/components/Toast.jsx'
import { useDeveloperMode } from '@/features/admin/hooks/useDeveloperMode.js'
import {
  clearPerformanceRecent,
  fetchPerformanceRecent,
  fetchPerformanceRequest,
} from '@/features/admin/services/developerPerformanceService.js'
import { DurationBadge, formatDuration } from '@/features/admin/components/PerformanceCharts.jsx'

const RESUME_STEPS = [
  { key: 'upload', name: 'Receive Upload' },
  { key: 'client_wait', name: 'Wait for First Progress' },
  { key: 'cache', name: 'Cache Check' },
  { key: 'persist_raw', name: 'Store Raw File' },
  { key: 'text', name: 'Extract Text' },
  { key: 'layout', name: 'Layout Analysis' },
  { key: 'sections', name: 'Section Detection' },
  { key: 'deterministic', name: 'Deterministic Parse' },
  { key: 'coverage', name: 'Coverage Check' },
  { key: 'semantic', name: 'Semantic Enrichment (LLM)' },
  { key: 'knowledge', name: 'Knowledge Enrichment' },
  { key: 'validate', name: 'Validation' },
  { key: 'persist', name: 'Save Parsed Result' },
  { key: 'deliver', name: 'Send Result to Browser' },
  { key: 'autofill', name: 'Autofill Form' },
]

const JD_STEPS = [
  { key: 'upload', name: 'Receive Upload' },
  { key: 'client_wait', name: 'Wait for First Progress' },
  { key: 'cache', name: 'Cache Check' },
  { key: 'persist_raw', name: 'Store Raw File' },
  { key: 'text', name: 'Extract Text' },
  { key: 'layout', name: 'Layout Analysis' },
  { key: 'sections', name: 'Section Detection' },
  { key: 'deterministic', name: 'Deterministic Parse' },
  { key: 'knowledge', name: 'Knowledge Enrichment' },
  { key: 'coverage', name: 'Coverage Check' },
  { key: 'semantic', name: 'Semantic Enrichment (LLM)' },
  { key: 'validate', name: 'Validation' },
  { key: 'persist', name: 'Save Parsed Result' },
  { key: 'deliver', name: 'Send Result to Browser' },
  { key: 'autofill', name: 'Autofill Form' },
]

const BULK_STEPS = [
  { key: 'cache', name: 'Cache Check' },
  { key: 'persist_raw', name: 'Store Raw File' },
  { key: 'text', name: 'Extract Text' },
  { key: 'layout', name: 'Layout Analysis' },
  { key: 'sections', name: 'Section Detection' },
  { key: 'deterministic', name: 'Deterministic Parse' },
  { key: 'coverage', name: 'Coverage Check' },
  { key: 'semantic', name: 'Semantic Enrichment (LLM)' },
  { key: 'knowledge', name: 'Knowledge Enrichment' },
  { key: 'validate', name: 'Validation' },
  { key: 'persist', name: 'Save Parsed Result' },
]

const APPLY_STEPS = [
  { key: 'ats_match', name: 'ATS Matching' },
  { key: 'ats_score', name: 'ATS Score Computation' },
  { key: 'persist_application', name: 'Save Application' },
  { key: 'apply_submit', name: 'Submit Application' },
]

const STEP_ALIASES = {
  extract_text: 'text',
  store_raw_file: 'persist_raw',
  enrich_resume_semantic: 'semantic',
  enrich_jd_semantic: 'semantic',
  _call_section_llm: 'semantic',
  parse_via_runtime: 'semantic',
  match_candidate_to_job: 'ats_match',
  _internal_match: 'ats_score',
  _persist_application_atomic: 'persist_application',
  public_apply_to_job: 'apply_submit',
}

function formatTime(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function formatRelative(iso) {
  if (!iso) return ''
  try {
    const t = new Date(iso).getTime()
    const diff = Date.now() - t
    if (diff < 60_000) return 'Just now'
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`
    return formatTime(iso)
  } catch {
    return ''
  }
}

function pipelineTitle(kind, session) {
  if (kind === 'jd_parse') return 'JD Parsing'
  if (kind === 'apply') return 'Apply to Job'
  if (kind === 'ats') return 'ATS Matching'
  if (kind === 'bulk_parse') {
    const n = session?.resume_count
    if (n != null && n > 0) return `Bulk Parse · ${n} resume${n === 1 ? '' : 's'}`
    return 'Bulk Parse'
  }
  if (kind === 'resume_parse') return 'Resume Parsing'
  return 'Pipeline'
}

function kindMeta(kind) {
  if (kind === 'jd_parse') {
    return {
      label: 'JD',
      Icon: FiFileText,
      chip: 'bg-[rgba(39,109,255,0.18)] text-[#8EB6FF] ring-[rgba(39,109,255,0.35)]',
    }
  }
  if (kind === 'bulk_parse') {
    return {
      label: 'Bulk',
      Icon: FiLayers,
      chip: 'bg-[rgba(168,85,247,0.16)] text-[#D8B4FE] ring-[rgba(168,85,247,0.35)]',
    }
  }
  if (kind === 'apply' || kind === 'ats') {
    return {
      label: kind === 'ats' ? 'ATS' : 'Apply',
      Icon: FiUpload,
      chip: 'bg-[rgba(54,214,160,0.14)] text-[#67DFB4] ring-[rgba(54,214,160,0.3)]',
    }
  }
  return {
    label: 'Resume',
    Icon: FiFileText,
    chip: 'bg-[rgba(0,166,255,0.14)] text-[#7DD3FF] ring-[rgba(0,166,255,0.3)]',
  }
}

function detectKind(detail) {
  if (!detail) return null
  if (
    detail.kind === 'jd_parse' ||
    detail.kind === 'resume_parse' ||
    detail.kind === 'bulk_parse' ||
    detail.kind === 'apply' ||
    detail.kind === 'ats'
  ) {
    return detail.kind
  }
  const path = (detail.path || '').toLowerCase()
  if (path.includes('/bulk-parse') || path.includes('bulk-parse')) return 'bulk_parse'
  if (path.includes('/parse/jd')) return 'jd_parse'
  if (path.includes('/parse/resume')) return 'resume_parse'
  if (path.includes('/apply')) return 'apply'
  const fns = new Set((detail.events || []).map((e) => e.function))
  if (fns.has('public_apply_to_job') || fns.has('_persist_application_atomic')) return 'apply'
  if (fns.has('_run_jd') || fns.has('enrich_jd_semantic')) return 'jd_parse'
  if (
    fns.has('_run_resume') ||
    fns.has('enrich_resume_semantic') ||
    fns.has('text') ||
    fns.has('deterministic')
  ) {
    return 'resume_parse'
  }
  return detail.kind || null
}

function buildParseSteps(detail) {
  const kind = detectKind(detail)
  const template =
    kind === 'jd_parse'
      ? JD_STEPS
      : kind === 'apply' || kind === 'ats'
        ? APPLY_STEPS
        : kind === 'bulk_parse'
          ? BULK_STEPS
          : kind === 'resume_parse'
            ? RESUME_STEPS
            : null
  if (!template) return detail?.parse_steps || []

  const fromApi = Array.isArray(detail?.parse_steps) ? detail.parse_steps : []
  const byKey = new Map()
  for (const s of fromApi) {
    if (s?.key) byKey.set(s.key, s)
  }

  for (const e of detail?.events || []) {
    let key = e.function
    if (STEP_ALIASES[key]) key = STEP_ALIASES[key]
    const existing = byKey.get(key)
    const incomingMs = e.duration_ms
    const existingMs = existing?.duration_ms
    if (
      !existing ||
      (incomingMs != null && existingMs == null) ||
      (incomingMs != null && existingMs != null && incomingMs > existingMs)
    ) {
      const status = e.outcome || (e.success === false ? 'failed' : 'completed')
      byKey.set(key, {
        key,
        name: template.find((t) => t.key === key)?.name || e.stage || key,
        duration_ms: status === 'skipped' ? null : e.duration_ms,
        status,
        success: e.success,
        function: e.function,
      })
    }
  }

  const rows = template.map((t, idx) => {
    const hit = byKey.get(t.key)
    if (!hit) {
      return {
        step: idx + 1,
        key: t.key,
        name: t.name,
        duration_ms: null,
        status: 'not_run',
        success: null,
        function: t.key,
      }
    }
    const status = hit.status || 'completed'
    return {
      step: idx + 1,
      key: t.key,
      name: t.name,
      duration_ms: status === 'skipped' || status === 'not_run' ? null : hit.duration_ms,
      status,
      success: hit.success,
      function: hit.function || t.key,
    }
  })

  // If the pipeline clearly ran, treat idle steps as skipped (clearer than "Not run")
  const hasWork = rows.some((r) => r.status === 'completed' || r.status === 'failed')
  if (hasWork) {
    for (const r of rows) {
      if (r.status === 'not_run') r.status = 'skipped'
    }
  }

  const llm =
    (detail?.events || []).find((e) => e.function === 'parse_via_runtime') ||
    fromApi.find((s) => s.key === 'llm_inference')
  if (llm && llm.status !== 'skipped') {
    rows.push({
      step: null,
      key: 'llm_inference',
      name: 'LLM Inference (AI Runtime)',
      duration_ms: llm.duration_ms,
      status: llm.success === false ? 'failed' : llm.status || 'completed',
      success: llm.success !== false,
      function: 'parse_via_runtime',
      detail: true,
    })
  }
  return rows
}

function StepRow({ step, maxMs, isLast }) {
  const showTime =
    (step.status === 'completed' || step.status === 'failed') &&
    step.duration_ms != null &&
    Number.isFinite(Number(step.duration_ms))
  const pct = showTime ? Math.min(100, (step.duration_ms / maxMs) * 100) : 0
  const isIdle = step.status === 'skipped' || step.status === 'not_run'
  const n = step.step

  return (
    <li className={`relative flex gap-3 ${step.detail ? 'ml-5' : ''}`}>
      <div className="flex flex-col items-center w-7 shrink-0">
        <span
          className={`z-[1] flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-bold ${
            step.status === 'completed'
              ? 'bg-[var(--ei-btn-primary-from)] text-[var(--ei-btn-primary-text)] shadow-[0_0_0_3px_var(--ei-btn-primary-shadow)]'
              : step.status === 'failed'
                ? 'bg-rose-500 text-white'
                : isIdle
                  ? 'bg-transparent text-[var(--ei-text-muted)] ring-1 ring-[var(--ei-border-primary)]'
                  : 'bg-[var(--ei-surface-hover)] text-[var(--ei-text-muted)]'
          }`}
        >
          {step.detail ? '·' : step.status === 'completed' ? <FiCheck className="w-3.5 h-3.5" /> : n}
        </span>
        {!isLast ? (
          <span
            className={`w-px flex-1 min-h-[0.5rem] ${
              step.status === 'completed' ? 'bg-[var(--ei-btn-primary-from)]/35' : 'bg-[var(--ei-border-primary)]'
            }`}
            aria-hidden
          />
        ) : null}
      </div>

      <div
        className={`flex-1 min-w-0 mb-2 rounded-lg px-3 py-2.5 transition ${
          showTime
            ? 'bg-[var(--ei-surface-hover)] ring-1 ring-[var(--ei-border-primary)]'
            : step.status === 'failed'
              ? 'bg-[rgba(255,90,110,0.08)] ring-1 ring-[rgba(255,90,110,0.25)]'
              : 'bg-transparent'
        }`}
      >
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p
              className={`text-sm font-medium truncate ${
                isIdle ? 'text-[var(--ei-text-muted)]' : 'text-[var(--ei-text-primary)]'
              }`}
            >
              {step.name}
            </p>
            {step.status === 'failed' ? (
              <p className="text-[11px] text-rose-300 mt-0.5 flex items-center gap-1">
                <FiX className="w-3 h-3" /> Failed
              </p>
            ) : null}
          </div>
          <div className="shrink-0">
            {showTime ? (
              <DurationBadge ms={step.duration_ms} />
            ) : step.status === 'failed' ? (
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-rose-500/15 text-rose-300">
                Failed
              </span>
            ) : (
              <span className="text-[11px] font-medium px-2 py-0.5 rounded-md text-amber-300/90 bg-amber-500/10">
                Skipped
              </span>
            )}
          </div>
        </div>
        {showTime ? (
          <div className="mt-2 h-1 rounded-full bg-[var(--ei-bg-primary)]/80 overflow-hidden">
            <div
              className="h-full rounded-full bg-[var(--ei-btn-primary-from)]"
              style={{ width: `${Math.max(pct, 4)}%` }}
            />
          </div>
        ) : null}
      </div>
    </li>
  )
}

function BulkResumeAccordion({ file, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  const steps = useMemo(
    () =>
      buildParseSteps({
        kind: 'resume_parse',
        parse_steps: file?.parse_steps,
        events: [],
        total_duration_ms: file?.total_duration_ms,
      }),
    [file]
  )
  const maxMs = Math.max(
    ...steps.filter((s) => s.status === 'completed').map((s) => s.duration_ms || 0),
    1
  )
  const failed = file?.status === 'error'

  return (
    <li className="rounded-xl ring-1 ring-[var(--ei-border-primary)] bg-[var(--ei-bg-primary)]/40 overflow-hidden">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2.5 px-3 py-2.5 text-left hover:bg-[var(--ei-surface-hover)] transition"
      >
        <FiChevronDown
          className={`w-4 h-4 shrink-0 text-[var(--ei-text-muted)] transition ${open ? 'rotate-0' : '-rotate-90'}`}
        />
        <span className="min-w-0 flex-1 text-[12px] font-mono font-medium text-[var(--ei-text-primary)] truncate">
          {file?.filename || 'resume'}
        </span>
        <span className="shrink-0">
          {failed ? (
            <span className="text-[11px] text-rose-300 font-medium">Failed</span>
          ) : (
            <DurationBadge ms={file?.total_duration_ms} />
          )}
        </span>
      </button>
      {open ? (
        <div className="px-3 pb-3 pt-1 border-t border-[var(--ei-border-primary)]/60">
          <p className="text-[10px] uppercase tracking-wide text-[var(--ei-text-muted)] font-semibold mb-2">
            Pipeline steps
          </p>
          {steps.length ? (
            <ol className="space-y-0">
              {steps.map((step, idx) => (
                <StepRow
                  key={`${file?.request_id || file?.filename}-${step.key}-${idx}`}
                  step={step}
                  maxMs={maxMs}
                  isLast={idx === steps.length - 1}
                />
              ))}
            </ol>
          ) : (
            <p className="text-xs text-[var(--ei-text-muted)] py-2">No step timings for this file.</p>
          )}
        </div>
      ) : null}
    </li>
  )
}

function ParseStepsView({ steps, title, kind, totalMs, files, resumeCount }) {
  const maxMs = Math.max(
    ...steps.filter((s) => s.status === 'completed').map((s) => s.duration_ms || 0),
    1
  )
  const completed = steps.filter((s) => s.status === 'completed').length
  const skipped = steps.filter((s) => s.status === 'skipped' || s.status === 'not_run').length
  const failed = steps.filter((s) => s.status === 'failed').length
  const km = kindMeta(kind)
  const KindIcon = km.Icon
  const isBulk = kind === 'bulk_parse'

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={`inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-md ring-1 ${km.chip}`}
            >
              <KindIcon className="w-3 h-3" />
              {km.label}
            </span>
            {isBulk && resumeCount ? (
              <span className="text-xs text-[var(--ei-text-secondary)]">
                {resumeCount} resume{resumeCount === 1 ? '' : 's'}
              </span>
            ) : null}
          </div>
          <h4 className="text-lg font-semibold text-[var(--ei-text-primary)] mt-2">{title}</h4>
          <p className="text-xs text-[var(--ei-text-muted)] mt-0.5">
            {isBulk
              ? 'Expand each resume to see its pipeline steps'
              : 'From choosing the file until fields appear on the form. Total is that wait — not the sum of overlapping steps.'}
          </p>
        </div>
        <div className="text-right shrink-0 rounded-xl bg-[rgba(0,166,255,0.08)] ring-1 ring-[rgba(0,166,255,0.25)] px-3.5 py-2.5">
          <p className="text-[10px] uppercase tracking-wide text-[var(--ei-text-muted)] font-semibold">
            Upload → Autofill
          </p>
          <p className="text-xl font-bold tabular-nums text-[#00A6FF] leading-tight">
            {formatDuration(totalMs)}
          </p>
        </div>
      </div>

      {isBulk && Array.isArray(files) && files.length > 0 ? (
        <div className="flex-1 min-h-0 overflow-y-auto pr-1">
          <h5 className="text-xs font-semibold uppercase tracking-wide text-[var(--ei-text-muted)] mb-2">
            Resumes in this job
          </h5>
          <ul className="space-y-2">
            {files.map((f, i) => (
              <BulkResumeAccordion
                key={f.request_id || f.filename}
                file={f}
                defaultOpen={i === 0}
              />
            ))}
          </ul>
        </div>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap gap-2 text-[11px]">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[rgba(0,166,255,0.1)] text-[#7DD3FF]">
              <FiCheck className="w-3 h-3" /> {completed} timed
            </span>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-300">
              <FiMinus className="w-3 h-3" /> {skipped} skipped
            </span>
            {failed > 0 ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-rose-500/10 text-rose-300">
                <FiX className="w-3 h-3" /> {failed} failed
              </span>
            ) : null}
          </div>

          <ol className="flex-1 min-h-0 overflow-y-auto pr-1 space-y-0">
            {steps.map((step, idx) => (
              <StepRow key={`${step.key}-${idx}`} step={step} maxMs={maxMs} isLast={idx === steps.length - 1} />
            ))}
          </ol>
        </>
      )}
    </div>
  )
}

function PipelineView({ detail }) {
  const kind = detectKind(detail)
  const steps = useMemo(() => buildParseSteps(detail), [detail])
  const title = pipelineTitle(kind || detail?.kind, detail)

  if (!detail) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center px-6">
        <div className="w-12 h-12 rounded-2xl bg-[rgba(0,166,255,0.1)] flex items-center justify-center mb-3">
          <FiClock className="w-6 h-6 text-[#00A6FF]" />
        </div>
        <p className="text-sm font-medium text-[var(--ei-text-primary)]">Select a parse</p>
        <p className="text-xs text-[var(--ei-text-muted)] mt-1 max-w-xs">
          Choose a row on the left to see each pipeline step and how long it took.
        </p>
      </div>
    )
  }

  if (!steps.length) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center px-6">
        <p className="text-sm text-[var(--ei-text-muted)]">
          No step timings for this request. Run a parse with Developer Mode on, then refresh.
        </p>
      </div>
    )
  }

  return (
    <ParseStepsView
      steps={steps}
      title={title}
      kind={kind || detail?.kind}
      totalMs={detail.total_duration_ms}
      files={detail.files}
      resumeCount={detail.resume_count}
    />
  )
}

const FILTER_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'resume_parse', label: 'Resume' },
  { value: 'jd_parse', label: 'JD' },
  { value: 'apply', label: 'Apply' },
  { value: 'bulk_parse', label: 'Bulk' },
]

/** Single resume → Resume; bulk job group → Bulk; never mix the two. */
function matchesKindFilter(session, filter) {
  if (filter === 'all') return true
  const kind = session?.kind
  if (filter === 'bulk_parse') {
    return kind === 'bulk_parse' || session?.is_bulk_group === true
  }
  if (filter === 'resume_parse') {
    return kind === 'resume_parse' && !session?.is_bulk_group
  }
  if (filter === 'apply') {
    return kind === 'apply' || kind === 'ats'
  }
  return kind === filter
}

function KindFilterDropdown({ value, onChange }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)
  const selected = FILTER_OPTIONS.find((o) => o.value === value) || FILTER_OPTIONS[0]

  useEffect(() => {
    if (!open) return undefined
    const onDoc = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false)
    }
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div className="relative shrink-0 z-20" ref={rootRef}>
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className={`inline-flex items-center gap-1.5 text-xs font-semibold rounded-lg px-2.5 py-1.5 transition ${
          open
            ? 'bg-[var(--ei-bg-secondary)] text-[var(--ei-text-primary)] ring-1 ring-[#00A6FF]/55'
            : 'bg-[var(--ei-bg-primary)] text-[var(--ei-text-primary)] ring-1 ring-[var(--ei-border-primary)] hover:ring-[#00A6FF]/40'
        }`}
      >
        {selected.label}
        <FiChevronDown className={`w-3.5 h-3.5 text-[var(--ei-text-muted)] transition ${open ? 'rotate-180' : ''}`} />
      </button>
      {open ? (
        <ul
          role="listbox"
          className="absolute right-0 z-50 mt-1.5 min-w-[9rem] rounded-xl border border-[var(--ei-border-primary)] bg-[var(--ei-bg-secondary)] py-1 shadow-[0_16px_40px_rgba(0,0,0,0.45)] isolate"
        >
          {FILTER_OPTIONS.map((opt) => {
            const active = opt.value === value
            return (
              <li key={opt.value} role="option" aria-selected={active}>
                <button
                  type="button"
                  onClick={() => {
                    onChange(opt.value)
                    setOpen(false)
                  }}
                  className={`w-full text-left px-3 py-2 text-xs font-semibold flex items-center justify-between gap-2 transition ${
                    active
                      ? 'bg-[var(--ei-tone-info-bg)] text-[var(--ei-accent-blue)]'
                      : 'text-[var(--ei-text-primary)] hover:bg-[var(--ei-surface-hover)]'
                  }`}
                >
                  {opt.label}
                  {active ? <FiCheck className="w-3.5 h-3.5 shrink-0" /> : null}
                </button>
              </li>
            )
          })}
        </ul>
      ) : null}
    </div>
  )
}

function SessionRow({ session, active, onSelect }) {
  const kind = session.kind
  const km = kindMeta(kind)
  const KindIcon = km.Icon
  const isBulk = kind === 'bulk_parse'
  const fileList = Array.isArray(session.files) ? session.files : []
  const [filesOpen, setFilesOpen] = useState(false)

  return (
    <div
      className={`border-b border-[var(--ei-border-primary)]/50 ${
        active
          ? 'bg-[rgba(0,166,255,0.1)] border-l-2 border-l-[#00A6FF]'
          : 'hover:bg-[var(--ei-surface-hover)] border-l-2 border-l-transparent'
      }`}
    >
      <div className="flex items-stretch">
        <button
          type="button"
          onClick={() => onSelect(session.request_id)}
          className="flex-1 min-w-0 text-left px-3.5 py-3 transition"
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span
                  className={`inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded ring-1 ${km.chip}`}
                >
                  <KindIcon className="w-2.5 h-2.5" />
                  {km.label}
                </span>
                {isBulk && session.resume_count ? (
                  <span className="text-[11px] text-[var(--ei-text-secondary)]">
                    {session.resume_count} files
                  </span>
                ) : null}
              </div>
              <p className="text-sm font-medium text-[var(--ei-text-primary)] mt-1.5 truncate">
                {pipelineTitle(kind, session)}
              </p>
              <p className="text-[11px] text-[var(--ei-text-muted)] mt-0.5" title={formatTime(session.started_at)}>
                {formatRelative(session.started_at)}
              </p>
            </div>
            <DurationBadge ms={session.total_duration_ms} className="shrink-0" />
          </div>
        </button>
        {isBulk && fileList.length > 0 ? (
          <button
            type="button"
            aria-label={filesOpen ? 'Hide resumes' : 'Show resumes'}
            aria-expanded={filesOpen}
            title="Show resumes in this bulk job"
            onClick={(e) => {
              e.stopPropagation()
              setFilesOpen((v) => !v)
              onSelect(session.request_id)
            }}
            className="shrink-0 px-2.5 flex items-center justify-center border-l border-[var(--ei-border-primary)]/40 text-[var(--ei-text-muted)] hover:text-[var(--ei-text-primary)] hover:bg-[var(--ei-surface-hover)] transition"
          >
            <FiChevronDown className={`w-4 h-4 transition ${filesOpen ? 'rotate-0' : '-rotate-90'}`} />
          </button>
        ) : null}
      </div>
      {isBulk && filesOpen && fileList.length > 0 ? (
        <ul className="px-3 pb-3 space-y-1">
          {fileList.map((f) => (
            <li
              key={f.request_id || f.filename}
              className="flex items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 bg-[var(--ei-bg-primary)]/50 ring-1 ring-[var(--ei-border-primary)]/60"
            >
              <span className="text-[11px] font-mono text-[var(--ei-text-primary)] truncate">
                {f.filename}
              </span>
              {f.status === 'error' ? (
                <span className="text-[10px] text-rose-300 font-medium shrink-0">Failed</span>
              ) : (
                <DurationBadge ms={f.total_duration_ms} className="shrink-0 scale-90 origin-right" />
              )}
            </li>
          ))}
          <li className="pt-1">
            <button
              type="button"
              onClick={() => onSelect(session.request_id)}
              className="text-[11px] font-semibold text-[#00A6FF] hover:underline"
            >
              Open step details →
            </button>
          </li>
        </ul>
      ) : null}
    </div>
  )
}

function DashboardBody() {
  const toast = useToast()
  const [sessions, setSessions] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [clearing, setClearing] = useState(false)
  const [kindFilter, setKindFilter] = useState('all')

  const filteredSessions = useMemo(() => {
    if (kindFilter === 'all') return sessions
    return sessions.filter((s) => matchesKindFilter(s, kindFilter))
  }, [sessions, kindFilter])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const recent = await fetchPerformanceRecent({ limit: 50 })
      const list = recent?.sessions || []
      setSessions(list)
    } catch (err) {
      toast.error(err?.message || 'Failed to load performance data')
    } finally {
      setLoading(false)
    }
    // toast methods are stable; omit from deps to avoid remount refetch races
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const clearRecent = useCallback(async () => {
    if (
      !window.confirm(
        'Clear all recent parse timings from this server? This cannot be undone until new parses run.'
      )
    ) {
      return
    }
    setClearing(true)
    try {
      const result = await clearPerformanceRecent()
      // Confirm from server so UI matches the wiped buffer
      const recent = await fetchPerformanceRecent({ limit: 50 })
      const list = recent?.sessions || []
      setSessions(list)
      setSelectedId(null)
      setDetail(null)
      const removed = typeof result?.removed === 'number' ? result.removed : null
      toast.success(
        removed != null
          ? `Cleared ${removed} timing session${removed === 1 ? '' : 's'}`
          : 'Recent parse timings cleared'
      )
    } catch (err) {
      const status = err?.status
      toast.error(
        status === 404
          ? 'Clear API not found — restart the backend so the new route is loaded, then try again.'
          : err?.message || 'Failed to clear timings'
      )
    } finally {
      setClearing(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

  // Keep selection inside the active filter
  useEffect(() => {
    if (!filteredSessions.length) {
      setSelectedId(null)
      return
    }
    setSelectedId((prev) => {
      if (prev && filteredSessions.some((s) => s.request_id === prev)) return prev
      return filteredSessions[0].request_id
    })
  }, [filteredSessions])

  useEffect(() => {
    if (!selectedId) {
      setDetail(null)
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        const data = await fetchPerformanceRequest(selectedId)
        if (!cancelled) setDetail(data)
      } catch {
        if (!cancelled) setDetail(null)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [selectedId])

  return (
    <div className="space-y-5 h-full flex flex-col min-h-0">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 shrink-0">
        <div className="flex items-start gap-3 min-w-0">
          <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-[rgba(0,166,255,0.2)] to-[rgba(39,109,255,0.15)] flex items-center justify-center ring-1 ring-[rgba(0,166,255,0.3)] shrink-0">
            <FiActivity className="w-5 h-5 text-[#00A6FF]" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--ei-text-muted)]">
              Developer Mode
            </p>
            <h1 className="text-2xl font-bold text-[var(--ei-text-primary)] tracking-tight">
              Parse Step Timings
            </h1>
            <p className="text-sm text-[var(--ei-text-secondary)] mt-0.5">
              See where time goes — resume, JD, and bulk parse
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 self-start">
          <button
            type="button"
            onClick={clearRecent}
            disabled={clearing || loading || (!sessions.length && !clearing)}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-sm font-semibold ring-1 ring-[var(--ei-border-primary)] bg-[var(--ei-bg-secondary)] text-[var(--ei-text-primary)] hover:ring-[var(--ei-tone-danger-border)] hover:text-[var(--ei-tone-danger)] disabled:opacity-50 disabled:pointer-events-none transition"
          >
            <FiTrash2 className={`w-4 h-4 ${clearing ? 'animate-pulse' : ''}`} />
            Clean
          </button>
          <button
            type="button"
            onClick={load}
            disabled={loading || clearing}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-[var(--ei-btn-primary-from)] text-[var(--ei-btn-primary-text)] text-sm font-semibold hover:brightness-105 shadow-[0_8px_20px_var(--ei-btn-primary-shadow)] disabled:opacity-60"
          >
            <FiRefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4 flex-1 min-h-0">
        <div className="xl:col-span-2 rounded-2xl ring-1 ring-[var(--ei-border-primary)] bg-[var(--ei-bg-secondary)] overflow-hidden flex flex-col min-h-[22rem] max-h-[calc(100vh-14rem)]">
          <div className="relative z-10 px-4 py-3 border-b border-[var(--ei-border-primary)] flex items-center justify-between gap-3 shrink-0 bg-[var(--ei-bg-secondary)]">
            <div className="min-w-0">
              <h3 className="text-sm font-semibold text-[var(--ei-text-primary)]">Recent parses</h3>
              <p className="text-[11px] text-[var(--ei-text-muted)] mt-0.5">
                {filteredSessions.length
                  ? `${filteredSessions.length} recorded${
                      kindFilter !== 'all' ? ` · ${FILTER_OPTIONS.find((o) => o.value === kindFilter)?.label}` : ''
                    }`
                  : 'Waiting for activity'}
              </p>
            </div>
            <KindFilterDropdown value={kindFilter} onChange={setKindFilter} />
          </div>
          <div className="flex-1 overflow-y-auto min-h-0">
            {loading && !sessions.length ? (
              <p className="px-4 py-10 text-center text-sm text-[var(--ei-text-muted)]">Loading…</p>
            ) : null}
            {!loading && !sessions.length ? (
              <div className="px-6 py-12 text-center">
                <p className="text-sm font-medium text-[var(--ei-text-primary)]">No parses yet</p>
                <p className="text-xs text-[var(--ei-text-muted)] mt-1.5 leading-relaxed">
                  Parse a resume or JD, or run bulk parsing, then hit Refresh.
                </p>
              </div>
            ) : null}
            {!loading && sessions.length > 0 && !filteredSessions.length ? (
              <div className="px-6 py-12 text-center">
                <p className="text-sm font-medium text-[var(--ei-text-primary)]">No matches</p>
                <p className="text-xs text-[var(--ei-text-muted)] mt-1.5 leading-relaxed">
                  Nothing in this filter. Try All or another type.
                </p>
              </div>
            ) : null}
            {filteredSessions.map((s) => (
              <SessionRow
                key={s.request_id}
                session={s}
                active={s.request_id === selectedId}
                onSelect={setSelectedId}
              />
            ))}
          </div>
        </div>

        <div className="xl:col-span-3 rounded-2xl ring-1 ring-[var(--ei-border-primary)] bg-[var(--ei-bg-secondary)] p-5 sm:p-6 overflow-y-auto min-h-[22rem] max-h-[calc(100vh-14rem)]">
          <PipelineView detail={detail} />
        </div>
      </div>
    </div>
  )
}

export default function PerformanceDashboard() {
  const { enabled, loading, isAdmin } = useDeveloperMode()

  if (!isAdmin) {
    return <Navigate to="/login/admin" replace />
  }

  if (loading) {
    return (
      <HeadHrLayout>
        <div className="p-8 text-[var(--ei-text-muted)]">Checking Developer Mode…</div>
      </HeadHrLayout>
    )
  }

  if (!enabled) {
    return <Navigate to="/head-hr/settings" replace />
  }

  return (
    <HeadHrLayout>
      <div className="p-4 sm:p-6 lg:p-8 overflow-y-auto h-full">
        <DashboardBody />
      </div>
    </HeadHrLayout>
  )
}
