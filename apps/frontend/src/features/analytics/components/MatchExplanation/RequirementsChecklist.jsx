import React from 'react'

/**
 * Structured matched/missing mandatory + preferred skills checklist.
 * Premium side-by-side table when possible; chips as fallback.
 * @param {'default' | 'enterprise'} theme
 */
export default function RequirementsChecklist({
  requirementAnalysis,
  theme = 'default',
  mandatoryPct,
}) {
  const mandatory = Array.isArray(requirementAnalysis?.mandatory) ? requirementAnalysis.mandatory : []
  const preferred = Array.isArray(requirementAnalysis?.preferred) ? requirementAnalysis.preferred : []
  const gate = requirementAnalysis?.gate

  if (!mandatory.length && !preferred.length) return null

  const enterprise = theme === 'enterprise'
  const labelClass = enterprise
    ? 'text-[11px] font-semibold uppercase tracking-[0.1em] text-[#83909C]'
    : 'text-xs font-semibold uppercase tracking-[0.08em] text-slate-500 dark:text-slate-400'
  const bodyClass = enterprise ? 'text-[#C5CED8]' : 'text-slate-700 dark:text-slate-300'
  const mutedClass = enterprise ? 'text-[#8796A5]' : 'text-slate-500 dark:text-slate-400'
  const titleClass = enterprise ? 'text-[#F2F5F8]' : 'text-slate-900 dark:text-white'
  const panelBg = enterprise
    ? 'border-white/[0.08] bg-gradient-to-br from-white/[0.04] to-white/[0.015]'
    : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900/40'
  const rowBorder = enterprise ? 'border-white/[0.06]' : 'border-slate-100 dark:border-slate-800'

  const resultTone = (matched) => {
    if (enterprise) {
      return matched
        ? 'bg-[rgba(55,214,160,0.12)] text-[#67DFB4] border-[rgba(55,214,160,0.22)]'
        : 'bg-[rgba(255,93,115,0.12)] text-[#FF788B] border-[rgba(255,93,115,0.22)]'
    }
    return matched
      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
      : 'bg-red-50 text-red-700 border-red-200'
  }

  const renderTable = (title, rows, subtitle) => {
    if (!rows.length) return null
    const matched = rows.filter((r) => r.status === 'matched').length
    const missing = rows.length - matched
    return (
      <div className={`rounded-[14px] border overflow-hidden ${panelBg}`}>
        <div className={`px-4 py-3 border-b ${enterprise ? 'border-white/[0.08]' : 'border-slate-200 dark:border-slate-700'}`}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className={`text-sm font-semibold ${titleClass}`}>{title}</p>
              {subtitle && <p className={`mt-0.5 text-xs ${mutedClass}`}>{subtitle}</p>}
            </div>
            <div className="flex flex-wrap gap-1.5">
              <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold border ${resultTone(true)}`}>
                {matched} matched
              </span>
              {missing > 0 && (
                <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold border ${resultTone(false)}`}>
                  {missing} missing
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[420px] text-left text-sm">
            <thead>
              <tr className={`text-[10px] uppercase tracking-[0.08em] ${mutedClass}`}>
                <th className="px-4 py-2.5 font-semibold w-[40%]">Skill needed</th>
                <th className="px-4 py-2.5 font-semibold w-[30%]">On resume</th>
                <th className="px-4 py-2.5 font-semibold w-[30%]">Result</th>
              </tr>
            </thead>
            <tbody className={bodyClass}>
              {rows.map((r, i) => {
                const ok = r.status === 'matched'
                return (
                  <tr key={`${r.skill}-${i}`} className={`border-t ${rowBorder}`}>
                    <td className={`px-4 py-2.5 font-medium ${titleClass}`}>{r.skill}</td>
                    <td className="px-4 py-2.5">{ok ? r.skill : '—'}</td>
                    <td className="px-4 py-2.5">
                      <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-[0.05em] border ${resultTone(ok)}`}>
                        <span aria-hidden>{ok ? '✓' : '✕'}</span>
                        {ok ? 'Matched' : 'Not matched'}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  const pct = mandatoryPct ?? gate?.mandatory_pct

  return (
    <div className="space-y-3.5">
      <div>
        <h3 className={labelClass}>Requirements checklist</h3>
        <p className={`mt-1 text-xs ${mutedClass}`}>
          Skill-by-skill: role requirement vs resume evidence
          {pct != null ? ` · Mandatory match ${Number(pct)}%` : ''}
          {gate && gate.threshold != null ? ` (gate ${gate.threshold}%)` : ''}
        </p>
      </div>
      {renderTable('Mandatory skills', mandatory, 'Drives the 60% skills gate')}
      {renderTable('Preferred skills', preferred, 'Nice-to-have · does not drive the gate')}
    </div>
  )
}
