import React from 'react'
import { getComparisonBoard, asStringList } from './matchAnalysisUtils'

/**
 * Premium Detailed Analysis: side-by-side needed vs present for every category.
 * @param {'default' | 'enterprise'} variant
 */
export default function DetailedAnalysisPanel({
  jsonOut,
  score,
  variant = 'enterprise',
}) {
  const board = getComparisonBoard(jsonOut || {}, { score })
  const explanation = board?.explanation
  if (!explanation) return null

  const whatHappened = asStringList(explanation.what_happened)
  const rulesApplied = asStringList(explanation.rules_applied)

  const enterprise = variant === 'enterprise'
  const labelClass = enterprise
    ? 'text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--ei-text-muted)]'
    : 'text-xs font-semibold uppercase tracking-[0.08em] text-slate-500 dark:text-slate-400'
  const bodyClass = enterprise ? 'text-[var(--ei-text-secondary)]' : 'text-slate-700 dark:text-slate-300'
  const mutedClass = enterprise ? 'text-[var(--ei-text-muted)]' : 'text-slate-500 dark:text-slate-400'
  const borderClass = enterprise ? 'border-[var(--ei-border-primary)]' : 'border-slate-200 dark:border-slate-700'
  const titleClass = enterprise ? 'text-[var(--ei-text-primary)]' : 'text-slate-900 dark:text-white'
  const panelBg = enterprise
    ? 'border-[var(--ei-border-primary)] bg-[var(--ei-surface-hover)]'
    : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900/40'
  const tableHead = enterprise ? 'text-[var(--ei-text-label)]' : 'text-slate-500 dark:text-slate-400'
  const ruleCardClass = enterprise
    ? 'border-[var(--ei-border-primary)] bg-[rgba(255,255,255,0.06)]'
    : 'border-slate-100 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/60'
  const rowBorder = enterprise ? 'border-[var(--ei-border-primary)]' : 'border-slate-100 dark:border-slate-800'

  const outcomeTone =
    explanation.outcome === 'shortlist'
      ? enterprise
        ? 'bg-[var(--ei-tone-success-bg)] text-[var(--ei-tone-success)] border-[var(--ei-tone-success-border)]'
        : 'bg-emerald-50 text-emerald-700 border-emerald-200'
      : explanation.outcome === 'review'
        ? enterprise
          ? 'bg-[var(--ei-tone-info-bg)] text-[var(--ei-tone-info)] border-[var(--ei-tone-info-border)]'
          : 'bg-sky-50 text-sky-700 border-sky-200'
        : enterprise
          ? 'bg-[var(--ei-tone-danger-bg)] text-[var(--ei-tone-danger)] border-[var(--ei-tone-danger-border)]'
          : 'bg-red-50 text-red-700 border-red-200'

  const resultTone = (result) => {
    if (result === 'match') {
      return enterprise
        ? 'bg-[var(--ei-tone-success-bg)] text-[var(--ei-tone-success)] border-[var(--ei-tone-success-border)]'
        : 'bg-emerald-50 text-emerald-700 border-emerald-200'
    }
    if (result === 'partial') {
      return enterprise
        ? 'bg-[var(--ei-tone-warning-bg)] text-[var(--ei-tone-warning)] border-[var(--ei-tone-warning-border)]'
        : 'bg-amber-50 text-amber-700 border-amber-200'
    }
    if (result === 'unclear') {
      return enterprise
        ? 'bg-[var(--ei-surface-hover)] text-[var(--ei-text-secondary)] border-[var(--ei-border-primary)]'
        : 'bg-slate-100 text-slate-600 border-slate-200'
    }
    return enterprise
      ? 'bg-[var(--ei-tone-danger-bg)] text-[var(--ei-tone-danger)] border-[var(--ei-tone-danger-border)]'
      : 'bg-red-50 text-red-700 border-red-200'
  }

  const statusIcon = (status) => {
    if (status === 'match') {
      return (
        <span
          className={`inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${
            enterprise
              ? 'bg-[var(--ei-tone-success-bg)] text-[var(--ei-tone-success)]'
              : 'bg-emerald-100 text-emerald-700'
          }`}
          aria-hidden
        >
          ✓
        </span>
      )
    }
    if (status === 'partial') {
      return (
        <span
          className={`inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${
            enterprise
              ? 'bg-[var(--ei-tone-warning-bg)] text-[var(--ei-tone-warning)]'
              : 'bg-amber-100 text-amber-700'
          }`}
          aria-hidden
        >
          ~
        </span>
      )
    }
    return (
      <span
        className={`inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${
          enterprise
            ? 'bg-[var(--ei-tone-danger-bg)] text-[var(--ei-tone-danger)]'
            : 'bg-red-100 text-red-700'
        }`}
        aria-hidden
      >
        ✕
      </span>
    )
  }

  const ComparisonTable = ({ rows, emptyLabel }) => {
    if (!rows?.length) {
      return <p className={`mt-3 text-xs ${mutedClass}`}>{emptyLabel}</p>
    }
    return (
      <div className="mt-3 overflow-x-auto rounded-[10px] border border-inherit">
        <table className="w-full min-w-[480px] text-left text-sm">
          <thead>
            <tr className={`${tableHead} text-[10px] uppercase tracking-[0.08em]`}>
              <th className="px-3 py-2.5 font-semibold w-[38%]">Role asked for</th>
              <th className="px-3 py-2.5 font-semibold w-[38%]">On this resume</th>
              <th className="px-3 py-2.5 font-semibold w-[24%]">Result</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={`${row.needed}-${i}`} className={`border-t ${rowBorder}`}>
                <td className={`px-3 py-2.5 align-top ${titleClass}`}>
                  <span className="font-medium leading-snug">{row.needed}</span>
                </td>
                <td className={`px-3 py-2.5 align-top ${bodyClass}`}>
                  <span className="leading-snug">{row.present}</span>
                </td>
                <td className="px-3 py-2.5 align-top">
                  <div className="flex items-center gap-2">
                    {statusIcon(row.status)}
                    <span className={`inline-flex px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-[0.05em] border ${resultTone(row.status === 'missing' ? 'not_match' : row.status)}`}>
                      {row.label || statusLabelFallback(row.status)}
                    </span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  const CategoryBoard = ({
    title,
    section,
    accent,
    emptyLabel,
    footer,
  }) => {
    if (!section) return null
    return (
      <article className={`rounded-[14px] border overflow-hidden ${panelBg}`}>
        <div
          className={`px-4 py-3.5 border-b ${borderClass}`}
          style={enterprise ? {
            background: `linear-gradient(105deg, ${accent}14 0%, transparent 55%)`,
          } : undefined}
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2.5 min-w-0">
              <span
                className="h-2 w-2 rounded-full shrink-0"
                style={{ background: accent, boxShadow: `0 0 10px ${accent}66` }}
                aria-hidden
              />
              <h4 className={`text-sm font-semibold ${titleClass}`}>{title}</h4>
              <span className={`inline-flex px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-[0.06em] border ${resultTone(section.result)}`}>
                {section.result_label || section.result}
              </span>
            </div>
            <div className="flex items-baseline gap-1.5">
              <span className={`text-2xl font-bold tabular-nums tracking-tight ${titleClass}`}>
                {section.score != null ? Number(section.score) : '—'}
              </span>
              <span className={`text-xs font-medium ${mutedClass}`}>%</span>
            </div>
          </div>
          {section.reason && (
            <p className={`mt-2.5 text-sm leading-relaxed ${bodyClass}`}>{section.reason}</p>
          )}
          {footer}
        </div>
        <div className={`px-3 pb-3 ${borderClass}`}>
          <ComparisonTable rows={section.rows} emptyLabel={emptyLabel} />
        </div>
      </article>
    )
  }

  const skills = board.skills || {}
  const gate = skills.gate || {}
  const gatePct = gate.mandatory_pct
  const gateThreshold = gate.threshold || 40

  return (
    <div className={`space-y-5 text-sm ${bodyClass}`}>
      <section
        className={`relative overflow-hidden rounded-[16px] border p-4 sm:p-5 ${
          enterprise
            ? 'border-[var(--ei-border-primary)] bg-[var(--ei-surface-hover)]'
            : 'border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50'
        }`}
      >
        <div className="flex flex-wrap items-center gap-2.5 mb-3">
          <p className={labelClass}>Decision</p>
          <span className={`inline-flex px-3 py-1 rounded-full text-xs font-semibold border ${outcomeTone}`}>
            {explanation.outcome_label || explanation.verdict || '—'}
          </span>
        </div>
        <p className={`text-base sm:text-[17px] leading-snug font-semibold ${titleClass}`}>
          {explanation.primary_reason}
        </p>
        {whatHappened.length > 0 && (
          <ul className={`mt-3.5 space-y-2 ${mutedClass}`}>
            {whatHappened.map((line, i) => (
              <li key={i} className="flex gap-2.5 leading-relaxed">
                <span className={`mt-2 h-1 w-1 shrink-0 rounded-full ${enterprise ? 'bg-[var(--ei-tone-info)]' : 'bg-sky-500'}`} />
                <span>{line}</span>
              </li>
            ))}
          </ul>
        )}
        {explanation.reconciliation && (
          <p className={`mt-3.5 rounded-[10px] border px-3.5 py-2.5 text-sm leading-relaxed ${enterprise ? 'border-[var(--ei-border-primary)] bg-[var(--ei-surface-hover)]' : 'border-slate-200 bg-white/60'} ${mutedClass}`}>
            {explanation.reconciliation}
          </p>
        )}
        {explanation.next_step && (
          <p className="mt-3.5 text-sm">
            <span className={labelClass}>Next step · </span>
            <span className={bodyClass}>{explanation.next_step}</span>
          </p>
        )}
        {board.scoreReconciliation?.note && (
          <p className={`mt-3.5 text-xs leading-relaxed ${mutedClass}`}>
            {board.scoreReconciliation.note}
          </p>
        )}
      </section>

      <section>
        <div className="mb-3">
          <p className={labelClass}>Requirement comparison</p>
          <p className={`mt-1 text-xs ${mutedClass}`}>
            Side-by-side: what the role asked for versus what this resume shows.
          </p>
        </div>
        <div className="space-y-3.5">
          <CategoryBoard
            title="Core skills"
            section={skills}
            accent="#00A6FF"
            emptyLabel="No clean skill-by-skill checklist was available. Re-parse the JD or re-apply to refresh requirements."
            footer={(
              <div className="mt-3 flex flex-wrap gap-2">
                {skills.matchedCount != null && skills.rows?.length > 0 && (
                  <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${enterprise ? 'border-[var(--ei-tone-success-border)] text-[var(--ei-tone-success)] bg-[var(--ei-tone-success-bg)]' : 'border-emerald-200 text-emerald-700 bg-emerald-50'}`}>
                    <span aria-hidden>✓</span> {skills.matchedCount} matched
                  </span>
                )}
                {skills.missingCount > 0 && (
                  <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${enterprise ? 'border-[var(--ei-tone-danger-border)] text-[var(--ei-tone-danger)] bg-[var(--ei-tone-danger-bg)]' : 'border-red-200 text-red-700 bg-red-50'}`}>
                    <span aria-hidden>✕</span> {skills.missingCount} missing
                  </span>
                )}
                {gatePct != null && skills.rows?.length > 0 && (
                  <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${
                    skills.gateFailed
                      ? (enterprise ? 'border-[var(--ei-tone-danger-border)] text-[var(--ei-tone-danger)] bg-[var(--ei-tone-danger-bg)]' : 'border-red-200 text-red-700 bg-red-50')
                      : (enterprise ? 'border-[var(--ei-tone-success-border)] text-[var(--ei-tone-success)] bg-[var(--ei-tone-success-bg)]' : 'border-emerald-200 text-emerald-700 bg-emerald-50')
                  }`}>
                    Gate {Number(gatePct)}% / {gateThreshold}%
                  </span>
                )}
              </div>
            )}
          />

          {skills.preferredRows?.length > 0 && (
            <article className={`rounded-[14px] border overflow-hidden ${panelBg}`}>
              <div className={`px-4 py-3 border-b ${borderClass}`}>
                <div className="flex items-center gap-2">
                  <span className={`h-2 w-2 rounded-full ${enterprise ? 'bg-[var(--ei-accent-purple)]' : 'bg-violet-500'}`} aria-hidden />
                  <h4 className={`text-sm font-semibold ${titleClass}`}>Preferred skills</h4>
                  <span className={`text-xs ${mutedClass}`}>Nice-to-have · does not drive the gate</span>
                </div>
              </div>
              <div className="px-3 pb-3">
                <ComparisonTable
                  rows={skills.preferredRows}
                  emptyLabel="No preferred skills listed."
                />
              </div>
            </article>
          )}

          <CategoryBoard
            title="Experience"
            section={board.experience}
            accent="#37D6A0"
            emptyLabel="No experience comparison available."
          />
          <CategoryBoard
            title="Education"
            section={board.education}
            accent="#F5B94C"
            emptyLabel="No education comparison available."
          />
          <CategoryBoard
            title="Location"
            section={board.location}
            accent="#5CBCFF"
            emptyLabel="No location comparison available."
          />
        </div>
      </section>

      {rulesApplied.length > 0 && (
        <section className={`rounded-[14px] border p-4 ${panelBg}`}>
          <p className={labelClass}>How we decide</p>
          <ul className="mt-3 grid gap-2 sm:grid-cols-2 text-xs">
            {rulesApplied.map((rule, i) => (
              <li
                key={i}
                className={`flex gap-2 rounded-[10px] border px-3 py-2.5 leading-relaxed ${ruleCardClass}`}
              >
                <span className={`shrink-0 font-semibold tabular-nums ${enterprise ? 'text-[var(--ei-tone-info)]' : 'text-sky-600 dark:text-sky-400'}`}>
                  {String(i + 1).padStart(2, '0')}
                </span>
                <span className={bodyClass}>{rule}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

function statusLabelFallback(status) {
  if (status === 'match') return 'Matched'
  if (status === 'partial') return 'Partial'
  return 'Not matched'
}
