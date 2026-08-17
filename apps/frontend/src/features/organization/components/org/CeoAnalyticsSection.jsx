import React, { useMemo } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { FiBarChart2, FiTarget } from 'react-icons/fi'
import {
  PIPELINE_EXITS,
  PIPELINE_STAGES,
  VERDICT_KEYS,
} from '@/features/organization/utils/executiveAnalytics.js'

const OUTCOME_COLORS = {
  shortlisted: 'var(--ei-accent-green)',
  notShortlisted: 'var(--ei-accent-blue)',
  rejected: 'var(--ei-accent-red)',
  withdrawn: 'var(--ei-accent-purple)',
}

const VERDICT_COLORS = {
  strong: 'var(--ei-accent-green)',
  potential: 'var(--ei-tone-warning)',
  notMatch: 'var(--ei-accent-red)',
  unknown: 'var(--ei-text-muted)',
}

const SCORE_COLORS = {
  low: 'var(--ei-accent-red)',
  medium: 'var(--ei-tone-warning)',
  high: 'var(--ei-accent-green)',
}

function pct(count, total) {
  if (!total) return 0
  return Math.round((count / total) * 100)
}

function MetricRing({ value, color, label, caption, empty = false, size = 120 }) {
  const display = empty || value == null ? 0 : Math.min(100, Math.max(0, Number(value) || 0))
  const stroke = 8
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const offset = c - (display / 100) * c
  return (
    <div className="flex flex-col items-center text-center min-w-0">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90" aria-hidden>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="var(--ei-border-primary)"
            strokeWidth={stroke}
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={c}
            strokeDashoffset={empty ? c : offset}
            style={{ transition: 'stroke-dashoffset 500ms ease' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[22px] font-bold tabular-nums text-[var(--ei-text-primary)] leading-none">
            {empty || value == null
              ? '—'
              : `${Number.isInteger(Number(value)) ? Math.round(Number(value)) : Number(value)}%`}
          </span>
        </div>
      </div>
      <p className="mt-3 text-xs font-semibold uppercase tracking-[0.1em] text-[var(--ei-text-muted)]">{label}</p>
      {caption ? <p className="mt-0.5 text-xs text-[var(--ei-text-secondary)]">{caption}</p> : null}
    </div>
  )
}

function OutcomeDonut({ segments, total, size = 188 }) {
  const stroke = 22
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const active = segments.filter((s) => s.count > 0)
  const gap = active.length > 1 ? c * 0.018 : 0
  let acc = 0

  return (
    <div
      className="relative flex-shrink-0"
      style={{ width: size, height: size }}
      aria-label={`${total} applications by selection outcome`}
    >
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--ei-border-primary)"
          strokeWidth={stroke}
        />
        {active.map((s) => {
          const slice = (s.count / total) * c
          const len = Math.max(0, slice - gap)
          const el = (
            <circle
              key={s.key}
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              stroke={s.color}
              strokeWidth={stroke}
              strokeDasharray={`${len} ${c}`}
              strokeDashoffset={-acc}
              style={{ transition: 'stroke-dasharray 500ms ease, stroke-dashoffset 500ms ease' }}
            />
          )
          acc += slice
          return el
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
        <span className="text-3xl font-bold tabular-nums text-[var(--ei-text-primary)] leading-none">{total}</span>
        <span className="mt-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--ei-text-muted)]">
          Applications
        </span>
      </div>
    </div>
  )
}

function CountBar({ label, count, total, color }) {
  const width = pct(count, total)
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm text-[var(--ei-text-secondary)]">{label}</span>
        <span className="text-sm tabular-nums text-[var(--ei-text-primary)]">
          <span className="font-semibold">{count}</span>
          <span className="text-[var(--ei-text-muted)] ml-1.5">{total ? `${width}%` : '—'}</span>
        </span>
      </div>
      <div className="h-2 rounded-full bg-[var(--ei-surface-hover)] overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${width}%`, background: color, minWidth: count > 0 ? 6 : 0 }}
        />
      </div>
    </div>
  )
}

function PipelineFunnel({ byPipeline, total }) {
  const max = Math.max(1, ...PIPELINE_STAGES.map((s) => byPipeline[s.key] || 0))
  const exits = PIPELINE_EXITS.filter((s) => (byPipeline[s.key] || 0) > 0)

  return (
    <div>
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 sm:gap-3">
        {PIPELINE_STAGES.map((stage) => {
          const count = byPipeline[stage.key] || 0
          const height = 28 + Math.round((count / max) * 72)
          const muted = count === 0
          const advanced = stage.key === 'shortlisted' || stage.key === 'interview' || stage.key === 'offer' || stage.key === 'hired'
          return (
            <div key={stage.key} className="flex flex-col items-center min-w-0">
              <div className="w-full flex items-end h-[100px]">
                <div
                  className="w-full rounded-xl border transition-all duration-500"
                  style={{
                    height: `${height}px`,
                    background: muted
                      ? 'var(--ei-surface-hover)'
                      : advanced
                        ? 'var(--ei-tone-success-bg)'
                        : 'var(--ei-tone-info-bg)',
                    borderColor: muted
                      ? 'var(--ei-border-primary)'
                      : advanced
                        ? 'var(--ei-tone-success-border)'
                        : 'var(--ei-tone-info-border)',
                    opacity: muted ? 0.55 : 1,
                  }}
                >
                  <div className="h-full flex items-center justify-center">
                    <span className="text-lg font-bold tabular-nums text-[var(--ei-text-primary)]">{count}</span>
                  </div>
                </div>
              </div>
              <p className="mt-2 text-[11px] font-medium text-center text-[var(--ei-text-secondary)] truncate w-full">
                {stage.label}
              </p>
              <p className="text-[10px] tabular-nums text-[var(--ei-text-muted)]">{total ? `${pct(count, total)}%` : '—'}</p>
            </div>
          )
        })}
      </div>
      {exits.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {exits.map((stage) => (
            <span
              key={stage.key}
              className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs"
              style={{
                borderColor: stage.key === 'rejected' ? 'var(--ei-tone-danger-border)' : 'var(--ei-tone-info-border)',
                background: stage.key === 'rejected' ? 'var(--ei-tone-danger-bg)' : 'var(--ei-tone-info-bg)',
                color: stage.key === 'rejected' ? 'var(--ei-tone-danger)' : 'var(--ei-text-secondary)',
              }}
            >
              {stage.label}
              <span className="font-semibold tabular-nums text-[var(--ei-text-primary)]">{byPipeline[stage.key]}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function JobConversionRow({ job, onOpen }) {
  const parts = [
    { key: 'shortlisted', n: job.shortlisted, color: OUTCOME_COLORS.shortlisted },
    { key: 'notShortlisted', n: job.notShortlisted, color: OUTCOME_COLORS.notShortlisted },
    { key: 'rejected', n: job.rejected, color: OUTCOME_COLORS.rejected },
    { key: 'withdrawn', n: job.withdrawn, color: OUTCOME_COLORS.withdrawn },
  ].filter((p) => p.n > 0)

  return (
    <button
      type="button"
      onClick={() => onOpen(job.id)}
      className="w-full text-left rounded-xl border border-[var(--ei-border-primary)] bg-[var(--ei-surface-hover)] px-3.5 py-3 hover:border-[var(--ei-border-hover)] transition-all duration-[180ms]"
    >
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 mb-2">
        <span className="text-sm font-medium text-[var(--ei-text-primary)] truncate min-w-0 flex-1">{job.title || job.id}</span>
        <span className="text-xs font-semibold tabular-nums text-[var(--ei-accent-green)]">{job.conversion}% shortlisted</span>
      </div>
      <div className="h-2 rounded-full overflow-hidden flex bg-[var(--ei-border-primary)]">
        {parts.map((p) => (
          <div
            key={p.key}
            style={{ width: `${pct(p.n, job.count)}%`, background: p.color }}
            className="h-full"
          />
        ))}
      </div>
      <p className="mt-2 text-xs text-[var(--ei-text-secondary)] tabular-nums">
        <span className="text-[var(--ei-text-label)]">{job.count}</span> applied
        {job.shortlisted > 0 && (
          <span className="ml-2" style={{ color: 'var(--ei-accent-green)' }}>{job.shortlisted} shortlisted</span>
        )}
        {job.notShortlisted > 0 && (
          <span className="ml-2" style={{ color: 'var(--ei-accent-blue)' }}>{job.notShortlisted} not shortlisted</span>
        )}
        {job.rejected > 0 && (
          <span className="ml-2" style={{ color: 'var(--ei-accent-red)' }}>{job.rejected} rejected</span>
        )}
        {job.avgScore != null && (
          <span className="ml-2" style={{ color: 'var(--ei-accent-purple)' }}>avg {job.avgScore}% match</span>
        )}
      </p>
    </button>
  )
}

export default function CeoAnalyticsSection({ analytics, onOpenJob }) {
  const reduceMotion = useReducedMotion()
  const fade = reduceMotion
    ? {}
    : { initial: { opacity: 0, y: 12 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.4, ease: 'easeOut' } }

  const outcomeSegments = useMemo(() => {
    const o = analytics.byOutcome
    const items = [
      { key: 'shortlisted', label: 'Shortlisted', count: o.shortlisted, color: OUTCOME_COLORS.shortlisted },
      { key: 'notShortlisted', label: 'Not shortlisted', count: o.notShortlisted, color: OUTCOME_COLORS.notShortlisted },
    ]
    if (o.rejected > 0) {
      items.push({ key: 'rejected', label: 'Rejected', count: o.rejected, color: OUTCOME_COLORS.rejected })
    }
    if (o.withdrawn > 0) {
      items.push({ key: 'withdrawn', label: 'Withdrawn', count: o.withdrawn, color: OUTCOME_COLORS.withdrawn })
    }
    return items
  }, [analytics.byOutcome])

  const caption = analytics.total
    ? `${analytics.shortlistedCount} of ${analytics.total} shortlisted · ${analytics.notShortlistedCount} not shortlisted${
        analytics.rejectedCount ? ` · ${analytics.rejectedCount} rejected` : ''
      }`
    : 'No applications yet'

  const scoreRows = [
    { key: 'low', label: 'Low (<30%)', count: analytics.scoreBuckets.low, color: SCORE_COLORS.low },
    { key: 'medium', label: 'Medium (30–60%)', count: analytics.scoreBuckets.medium, color: SCORE_COLORS.medium },
    { key: 'high', label: 'High (60%+)', count: analytics.scoreBuckets.high, color: SCORE_COLORS.high },
  ]

  const verdictRows = VERDICT_KEYS.filter((row) => row.key !== 'unknown' || analytics.byVerdict.unknown > 0)

  return (
    <motion.div className="mt-10 space-y-5" {...fade}>
      <div>
        <h2 className="text-lg font-semibold text-[var(--ei-text-primary)] flex items-center gap-2">
          <FiBarChart2 className="w-5 h-5 text-[var(--ei-accent-teal)]" />
          Analytics
        </h2>
        <p className="mt-1 text-sm text-[var(--ei-text-secondary)]">
          Selection outcome, match quality, and hiring pipeline. Not shortlisted stays in the talent pool until a recruiter rejects.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <section className="org-glass-panel p-5 sm:p-6">
          <h3 className="text-sm font-semibold text-[var(--ei-text-label)] mb-1">Selection outcome</h3>
          <p className="text-xs text-[var(--ei-text-muted)] mb-5">{caption}</p>
          {analytics.total === 0 ? (
            <p className="text-sm text-[var(--ei-text-muted)] py-10 text-center">No applications yet</p>
          ) : (
            <div className="flex flex-col sm:flex-row items-center gap-6">
              <OutcomeDonut segments={outcomeSegments} total={analytics.total} />
              <ul className="w-full space-y-3 min-w-0">
                {outcomeSegments.map((s) => (
                  <li key={s.key} className="flex items-center gap-3">
                    <span className="h-2.5 w-2.5 rounded-full flex-shrink-0" style={{ background: s.color }} />
                    <span className="text-sm text-[var(--ei-text-secondary)] flex-1">{s.label}</span>
                    <span className="text-sm font-semibold tabular-nums text-[var(--ei-text-primary)]">{s.count}</span>
                    <span className="text-xs tabular-nums text-[var(--ei-text-muted)] w-10 text-right">
                      {pct(s.count, analytics.total)}%
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>

        <section className="org-glass-panel p-5 sm:p-6">
          <h3 className="text-sm font-semibold text-[var(--ei-text-label)] mb-5 flex items-center gap-2">
            <FiTarget className="w-4 h-4 text-[var(--ei-accent-teal)]" />
            Match quality
          </h3>
          <div className="flex justify-around gap-4 mb-6">
            <MetricRing
              value={analytics.avgScore}
              empty={analytics.avgScore == null}
              color="var(--ei-accent-teal)"
              label="Avg. match"
              caption={analytics.scoreCount ? `${analytics.scoreCount} scored` : 'No scores yet'}
            />
            <MetricRing
              value={analytics.shortlistRate}
              empty={analytics.total === 0}
              color="var(--ei-accent-green)"
              label="Shortlist rate"
              caption="of applications"
            />
          </div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--ei-text-muted)] mb-3">
            Score distribution
          </p>
          <div className="space-y-3">
            {scoreRows.map((row) => (
              <CountBar
                key={row.key}
                label={row.label}
                count={row.count}
                total={analytics.scoreCount}
                color={row.color}
              />
            ))}
          </div>
        </section>
      </div>

      <section className="org-glass-panel p-5 sm:p-6">
        <h3 className="text-sm font-semibold text-[var(--ei-text-label)] mb-1">ATS verdict</h3>
        <p className="text-xs text-[var(--ei-text-muted)] mb-4">Why candidates were or were not shortlisted</p>
        {analytics.total === 0 ? (
          <p className="text-sm text-[var(--ei-text-muted)] py-4">No applications yet</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {verdictRows.map((row) => (
              <CountBar
                key={row.key}
                label={row.label}
                count={analytics.byVerdict[row.key] || 0}
                total={analytics.total}
                color={VERDICT_COLORS[row.key]}
              />
            ))}
          </div>
        )}
      </section>

      <section className="org-glass-panel p-5 sm:p-6">
        <h3 className="text-sm font-semibold text-[var(--ei-text-label)] mb-1">Hiring pipeline</h3>
        <p className="text-xs text-[var(--ei-text-muted)] mb-5">Live workflow stages. Applied is still in the talent pool.</p>
        {analytics.total === 0 ? (
          <p className="text-sm text-[var(--ei-text-muted)] py-4">No applications yet</p>
        ) : (
          <PipelineFunnel byPipeline={analytics.byPipeline} total={analytics.total} />
        )}
      </section>

      <section className="org-glass-panel p-5 sm:p-6">
        <h3 className="text-sm font-semibold text-[var(--ei-text-label)] mb-1">Job-level conversion</h3>
        <p className="text-xs text-[var(--ei-text-muted)] mb-4">Shortlist rate per role, with outcome mix</p>
        {analytics.topJobs.length > 0 ? (
          <div className="space-y-2">
            {analytics.topJobs.map((job) => (
              <JobConversionRow key={job.id} job={job} onOpen={onOpenJob} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-[var(--ei-text-muted)] py-4">No applications yet</p>
        )}
      </section>
    </motion.div>
  )
}
