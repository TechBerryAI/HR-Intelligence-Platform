/**
 * Admin Developer Mode — full resume/JD parse step checklist with timings.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { FiActivity, FiCheck, FiMinus, FiRefreshCw, FiX } from 'react-icons/fi'
import HeadHrLayout from '@/features/organization/pages/head-hr/HeadHrLayout.jsx'
import { useToast } from '@/shared/components/Toast.jsx'
import { useDeveloperMode } from '@/features/admin/hooks/useDeveloperMode.js'
import {
  fetchPerformanceRecent,
  fetchPerformanceRequest,
} from '@/features/admin/services/developerPerformanceService.js'
import { DurationBadge } from '@/features/admin/components/PerformanceCharts.jsx'

/** Exact resume checklist — always shown for resume parses */
const RESUME_STEPS = [
  { key: 'cache', name: 'Cache Check' },
  { key: 'persist_raw', name: 'Store Raw File' },
  { key: 'text', name: 'Extract Text' },
  { key: 'layout', name: 'Layout Analysis' },
  { key: 'sections', name: 'Section Detection' },
  { key: 'deterministic', name: 'Deterministic Parse' },
  { key: 'semantic', name: 'Semantic Enrichment (LLM)' },
  { key: 'knowledge', name: 'Knowledge Enrichment' },
  { key: 'validate', name: 'Validation' },
  { key: 'persist', name: 'Save Parsed Result' },
]

/** Exact JD checklist — always shown for JD parses */
const JD_STEPS = [
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
]

const STEP_ALIASES = {
  extract_text: 'text',
  store_raw_file: 'persist_raw',
  enrich_resume_semantic: 'semantic',
  enrich_jd_semantic: 'semantic',
  _call_section_llm: 'semantic',
  parse_via_runtime: 'semantic',
}

function formatTime(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function formatMs(ms) {
  if (ms == null || Number.isNaN(Number(ms))) return '—'
  const n = Number(ms)
  if (n >= 1000) return `${(n / 1000).toFixed(2)} s`
  return `${Math.round(n)} ms`
}

function pipelineTitle(kind) {
  if (kind === 'jd_parse') return 'JD Parsing'
  if (kind === 'ats') return 'ATS Matching'
  if (kind === 'apply') return 'Apply'
  if (kind === 'resume_parse') return 'Resume Parsing'
  return 'Pipeline'
}

function detectKind(detail) {
  if (!detail) return null
  if (detail.kind === 'jd_parse' || detail.kind === 'resume_parse') return detail.kind
  const path = (detail.path || '').toLowerCase()
  if (path.includes('/parse/jd')) return 'jd_parse'
  if (path.includes('/parse/resume')) return 'resume_parse'
  const fns = new Set((detail.events || []).map((e) => e.function))
  if (fns.has('coverage') || fns.has('_run_jd') || fns.has('enrich_jd_semantic')) return 'jd_parse'
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

function statusMeta(status) {
  if (status === 'completed') {
    return {
      label: 'Completed',
      icon: FiCheck,
      className: 'text-emerald-400',
      badge: 'bg-emerald-500/15 text-emerald-400',
    }
  }
  if (status === 'skipped') {
    return {
      label: 'Skipped',
      icon: FiMinus,
      className: 'text-amber-300',
      badge: 'bg-amber-500/15 text-amber-300',
    }
  }
  if (status === 'failed') {
    return {
      label: 'Failed',
      icon: FiX,
      className: 'text-rose-300',
      badge: 'bg-rose-500/15 text-rose-300',
    }
  }
  return {
    label: 'Not run',
    icon: FiMinus,
    className: 'text-[var(--ei-text-muted)]',
    badge: 'bg-[var(--ei-surface-hover)] text-[var(--ei-text-muted)]',
  }
}

/** Merge API parse_steps with the exact template so resume always lists all 10 steps. */
function buildParseSteps(detail) {
  const kind = detectKind(detail)
  const template = kind === 'jd_parse' ? JD_STEPS : kind === 'resume_parse' ? RESUME_STEPS : null
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
    if (!existing || (e.duration_ms != null && existing.duration_ms == null)) {
      byKey.set(key, {
        key,
        name: template.find((t) => t.key === key)?.name || e.stage || key,
        duration_ms: e.duration_ms,
        status: e.outcome || (e.success === false ? 'failed' : 'completed'),
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
    return {
      step: idx + 1,
      key: t.key,
      name: t.name,
      duration_ms: hit.duration_ms,
      status: hit.status || 'completed',
      success: hit.success,
      function: hit.function || t.key,
    }
  })

  const llm =
    (detail?.events || []).find((e) => e.function === 'parse_via_runtime') ||
    fromApi.find((s) => s.key === 'llm_inference')
  if (llm) {
    rows.push({
      step: null,
      key: 'llm_inference',
      name: '↳ LLM Inference (AI Runtime)',
      duration_ms: llm.duration_ms,
      status: llm.success === false ? 'failed' : llm.status || 'completed',
      success: llm.success !== false,
      function: 'parse_via_runtime',
      detail: true,
    })
  }
  return rows
}

function ParseStepsView({ steps, title, totalMs, path }) {
  const maxMs = Math.max(...steps.map((s) => s.duration_ms || 0), 1)

  return (
    <div>
      <div className="mb-5">
        <h4 className="text-lg font-semibold text-[var(--ei-text-primary)]">{title}</h4>
        <p className="text-xs text-[var(--ei-text-muted)] mt-1">Time for every pipeline step</p>
        {path ? (
          <p className="text-[11px] text-[var(--ei-text-secondary)] mt-2 font-mono truncate">{path}</p>
        ) : null}
      </div>

      <ol className="space-y-0">
        {steps.map((step, idx) => {
          const meta = statusMeta(step.status)
          const Icon = meta.icon
          const isDetail = Boolean(step.detail)
          const n = step.step ?? idx + 1
          const pct =
            step.duration_ms != null ? Math.min(100, (step.duration_ms / maxMs) * 100) : 0
          return (
            <li key={`${step.key}-${idx}`} className={`relative flex gap-3 ${isDetail ? 'ml-6' : ''}`}>
              <div className="flex flex-col items-center w-8 shrink-0">
                <span
                  className={`z-[1] flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold ring-2 ring-[var(--ei-surface-card)] ${
                    step.status === 'completed'
                      ? 'bg-[#00A6FF] text-white'
                      : step.status === 'failed'
                        ? 'bg-rose-500 text-white'
                        : step.status === 'skipped'
                          ? 'bg-amber-500/80 text-white'
                          : 'bg-[var(--ei-surface-hover)] text-[var(--ei-text-muted)]'
                  }`}
                >
                  {isDetail ? '↳' : n}
                </span>
                {idx < steps.length - 1 ? (
                  <span className="w-px flex-1 min-h-[0.75rem] bg-[var(--ei-border-primary)]" aria-hidden />
                ) : null}
              </div>

              <div className="flex-1 min-w-0 pb-3">
                <div className="rounded-xl border border-[var(--ei-border-primary)] bg-[var(--ei-surface-hover)]/45 px-3.5 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-[var(--ei-text-primary)]">{step.name}</p>
                      <p className={`mt-1 text-[11px] flex items-center gap-1 ${meta.className}`}>
                        <Icon className="w-3 h-3" />
                        {meta.label}
                      </p>
                    </div>
                    <div className="text-right shrink-0">
                      {step.duration_ms != null ? (
                        <>
                          <DurationBadge ms={step.duration_ms} />
                          <p className="text-[10px] text-[var(--ei-text-muted)] tabular-nums mt-1">
                            {Number(step.duration_ms).toFixed(2)} ms
                          </p>
                        </>
                      ) : (
                        <span className={`text-xs font-semibold px-2 py-0.5 rounded-md ${meta.badge}`}>
                          —
                        </span>
                      )}
                    </div>
                  </div>
                  {step.duration_ms != null && step.status === 'completed' ? (
                    <div className="mt-2.5 h-1.5 rounded-full bg-[var(--ei-bg-primary)] overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-[#00A6FF] to-[#276DFF]"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  ) : null}
                </div>
              </div>
            </li>
          )
        })}
      </ol>

      <div className="mt-2 rounded-xl border border-[rgba(0,166,255,0.35)] bg-[rgba(0,166,255,0.08)] px-4 py-3.5 flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[var(--ei-text-primary)]">Overall pipeline</p>
          <p className="text-xs text-[var(--ei-text-muted)] mt-0.5">Total time for {title}</p>
        </div>
        <span className="text-base font-bold tabular-nums text-[#00A6FF]">{formatMs(totalMs)}</span>
      </div>
    </div>
  )
}

function PipelineView({ detail }) {
  const kind = detectKind(detail)
  const steps = useMemo(() => buildParseSteps(detail), [detail])
  const title = pipelineTitle(kind || detail?.kind)

  if (!detail) {
    return (
      <p className="text-sm text-[var(--ei-text-muted)] py-12 text-center">
        Select a parse on the left to see every step’s timing.
      </p>
    )
  }

  if (steps.length) {
    return (
      <ParseStepsView
        steps={steps}
        title={title}
        totalMs={detail.total_duration_ms}
        path={detail.path}
      />
    )
  }

  return (
    <p className="text-sm text-[var(--ei-text-muted)] py-12 text-center">
      No parse step timings yet. Parse a resume or JD, then refresh.
    </p>
  )
}

function DashboardBody() {
  const toast = useToast()
  const [sessions, setSessions] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const recent = await fetchPerformanceRecent({ limit: 50 })
      const list = recent?.sessions || []
      setSessions(list)
      setSelectedId((prev) => {
        if (prev && list.some((s) => s.request_id === prev)) return prev
        return list[0]?.request_id || null
      })
    } catch (err) {
      toast.error(err?.message || 'Failed to load performance data')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
  }, [load])

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
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="flex items-start gap-3 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-[rgba(0,166,255,0.14)] flex items-center justify-center ring-1 ring-[rgba(0,166,255,0.25)] shrink-0">
            <FiActivity className="w-5 h-5 text-[#00A6FF]" />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--ei-text-muted)]">
              Developer Mode
            </p>
            <h1 className="text-2xl font-bold text-[var(--ei-text-primary)]">Parse Step Timings</h1>
            <p className="text-sm text-[var(--ei-text-secondary)]">
              Resume &amp; JD — every pipeline step with duration
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={load}
          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#00A6FF] text-white text-sm font-medium hover:bg-[#0090e0] self-start"
        >
          <FiRefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
        <div className="xl:col-span-2 rounded-xl border border-[var(--ei-border-primary)] bg-[var(--ei-surface-card)] overflow-hidden">
          <div className="px-4 py-3 border-b border-[var(--ei-border-primary)]">
            <h3 className="text-sm font-semibold text-[var(--ei-text-primary)]">Recent parses</h3>
          </div>
          <div className="overflow-x-auto max-h-[calc(100vh-16rem)] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-[var(--ei-surface-card)] z-[1]">
                <tr className="text-left text-xs uppercase tracking-wide text-[var(--ei-text-muted)] border-b border-[var(--ei-border-primary)]">
                  <th className="px-4 py-2 font-semibold">Time</th>
                  <th className="px-4 py-2 font-semibold">Type</th>
                  <th className="px-4 py-2 font-semibold">Total</th>
                </tr>
              </thead>
              <tbody>
                {loading && !sessions.length ? (
                  <tr>
                    <td colSpan={3} className="px-4 py-8 text-center text-[var(--ei-text-muted)]">
                      Loading…
                    </td>
                  </tr>
                ) : null}
                {!loading && !sessions.length ? (
                  <tr>
                    <td colSpan={3} className="px-4 py-8 text-center text-[var(--ei-text-muted)]">
                      No parses yet. Parse a resume or JD, then refresh.
                    </td>
                  </tr>
                ) : null}
                {sessions.map((s) => {
                  const active = s.request_id === selectedId
                  return (
                    <tr
                      key={s.request_id}
                      onClick={() => setSelectedId(s.request_id)}
                      className={`cursor-pointer border-b border-[var(--ei-border-primary)]/60 hover:bg-[var(--ei-surface-hover)] ${
                        active ? 'bg-[rgba(0,166,255,0.08)]' : ''
                      }`}
                    >
                      <td className="px-4 py-2.5 whitespace-nowrap text-[var(--ei-text-secondary)]">
                        {formatTime(s.started_at)}
                      </td>
                      <td className="px-4 py-2.5 text-[var(--ei-text-primary)] font-medium">
                        {pipelineTitle(s.kind)}
                      </td>
                      <td className="px-4 py-2.5">
                        <DurationBadge ms={s.total_duration_ms} />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        <div className="xl:col-span-3 rounded-xl border border-[var(--ei-border-primary)] bg-[var(--ei-surface-card)] p-5 sm:p-6">
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
