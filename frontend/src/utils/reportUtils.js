/**
 * Report generation utilities for Super Admin.
 * Produces formatted .xlsx files using SheetJS (xlsx).
 *
 * Layout of every report sheet:
 *   Row 1  — Portal name + Report title
 *   Row 2  — Generated date | Total records
 *   Row 3  — (empty separator)
 *   Row 4  — Column headers
 *   Row 5+ — Data rows
 *   Last-1 — (empty)
 *   Last   — Footer note
 */
import * as XLSX from 'xlsx'

// ─── Helpers ────────────────────────────────────────────────────────────────

export function todayStr() {
  return new Date().toISOString().split('T')[0]
}

export function fmtDate(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function nowLabel() {
  return new Date().toLocaleString('en-US', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

// ─── Column definitions ──────────────────────────────────────────────────────

export const ADMIN_COLUMNS = [
  { label: 'HR ID',       key: 'hrid',       width: 12 },
  { label: 'Full Name',   key: 'full_name',   width: 24 },
  { label: 'Email',       key: 'email',       width: 32 },
  { label: 'Company',     key: 'company',     width: 24 },
  { label: 'Joined',      key: 'created_at',  width: 24, format: fmtDate },
]

export const CANDIDATE_COLUMNS = [
  { label: 'Candidate ID',       key: 'cid',              width: 14 },
  { label: 'Name',               key: 'name',             width: 22 },
  { label: 'Email',              key: 'email',            width: 32 },
  { label: 'Full Name (Profile)',key: 'full_name',         width: 22 },
  { label: 'Phone',              key: 'phone',            width: 16 },
  { label: 'Experience Level',   key: 'experience_level', width: 18 },
  { label: 'Current Location',   key: 'current_location', width: 26 },
  { label: 'Profile Complete',   key: 'completed',        width: 16, format: (v) => (v ? 'Yes' : 'No') },
  { label: 'Joined',             key: 'created_at',       width: 24, format: fmtDate },
]

export const JOB_COLUMNS = [
  { label: 'Job ID',          key: 'jdid',            width: 12 },
  { label: 'Title',           key: 'title',           width: 30 },
  { label: 'Company',         key: 'company',         width: 22 },
  { label: 'Location',        key: 'location',        width: 24 },
  { label: 'Salary',          key: 'salary',          width: 18 },
  { label: 'Experience',      key: 'experience',      width: 16 },
  { label: 'Status',          key: 'enabled',         width: 12, format: (v) => (v ? 'Active' : 'Disabled') },
  { label: 'Posted By',       key: 'posted_by_name',  width: 22 },
  { label: 'Posted By Email', key: 'posted_by_email', width: 30 },
  { label: 'Posted On',       key: 'posted_on',       width: 24, format: fmtDate },
]

export const APPLICATION_COLUMNS = [
  { label: 'App #',             key: 'id',               width: 8 },
  { label: 'Candidate ID',      key: 'candidate_id',     width: 14 },
  { label: 'Candidate Name',    key: 'candidate_name',   width: 22 },
  { label: 'Candidate Email',   key: 'candidate_email',  width: 30 },
  { label: 'Job ID',            key: 'job_id',           width: 10 },
  { label: 'Job Title',         key: 'job_title',        width: 28 },
  { label: 'Company',           key: 'job_company',      width: 22 },
  { label: 'HR Admin',          key: 'hr_name',          width: 20 },
  { label: 'Match Score (%)',   key: 'match_score',      width: 16, format: (v) => (v != null ? Math.round(v) : '') },
  { label: 'Shortlisted',       key: 'shortlisted',      width: 12, format: (v) => (v ? 'Yes' : 'No') },
  { label: 'Status',            key: 'status',           width: 14 },
  { label: 'Applied At',        key: 'applied_at',       width: 24, format: fmtDate },
]

// ─── Core builder ────────────────────────────────────────────────────────────

/**
 * Build a formatted worksheet (AOA = array of arrays) and return it.
 * @param {string} reportTitle  e.g. "HR Admins Report"
 * @param {Array}  rows         Raw data rows (array of objects)
 * @param {Array}  columns      Column definition array (see above)
 */
function buildWorksheet(reportTitle, rows, columns) {
  const totalCols = columns.length
  const colLetterEnd = String.fromCharCode(64 + totalCols) // 'E', 'J', etc.

  // ── Header block ──────────────────────────────────────────────────────────
  const titleRow    = [`HR Job Portal  —  ${reportTitle}`]
  const metaRow     = [`Generated: ${nowLabel()}   |   Total Records: ${rows.length}`]
  const emptyRow    = []
  const headerRow   = columns.map((c) => c.label)

  // ── Data rows ─────────────────────────────────────────────────────────────
  const dataRows = rows.map((row) =>
    columns.map((c) => {
      const raw = row[c.key]
      return c.format ? c.format(raw, row) : (raw ?? '')
    }),
  )

  // ── Summary block ─────────────────────────────────────────────────────────
  const summaryRows = buildSummary(reportTitle, rows, columns)

  // ── Combine ───────────────────────────────────────────────────────────────
  const aoa = [
    titleRow,
    metaRow,
    emptyRow,
    headerRow,
    ...dataRows,
    emptyRow,
    ...summaryRows,
    [],
    [`— End of ${reportTitle} —`],
  ]

  const ws = XLSX.utils.aoa_to_sheet(aoa)

  // ── Column widths ─────────────────────────────────────────────────────────
  ws['!cols'] = columns.map((c) => ({ wch: c.width || 20 }))

  // ── Merge title cell across all columns ───────────────────────────────────
  ws['!merges'] = [
    { s: { r: 0, c: 0 }, e: { r: 0, c: totalCols - 1 } },  // Title row
    { s: { r: 1, c: 0 }, e: { r: 1, c: totalCols - 1 } },  // Meta row
  ]

  return ws
}

/** Build entity-specific summary stats at the bottom of the sheet */
function buildSummary(reportTitle, rows, columns) {
  if (!rows.length) return [['No data available for this report.']]

  const summaryLines = [['── Summary ──']]

  if (reportTitle.includes('Admin')) {
    const companies = [...new Set(rows.map((r) => r.company).filter(Boolean))]
    summaryLines.push([`Total HR Admins: ${rows.length}`])
    summaryLines.push([`Unique Companies: ${companies.length}`])
    if (companies.length) summaryLines.push([`Companies: ${companies.join(', ')}`])
  }

  if (reportTitle.includes('Candidate')) {
    const complete   = rows.filter((r) => r.completed).length
    const incomplete = rows.length - complete
    const locations  = [...new Set(rows.map((r) => r.current_location).filter(Boolean))]
    summaryLines.push([`Total Candidates: ${rows.length}`])
    summaryLines.push([`Profile Complete: ${complete}   |   Incomplete: ${incomplete}`])
    if (locations.length) summaryLines.push([`Unique Locations: ${locations.length}`])
  }

  if (reportTitle.includes('Job')) {
    const active   = rows.filter((r) => r.enabled).length
    const disabled = rows.length - active
    const companies = [...new Set(rows.map((r) => r.company).filter(Boolean))]
    summaryLines.push([`Total Jobs: ${rows.length}`])
    summaryLines.push([`Active: ${active}   |   Disabled: ${disabled}`])
    summaryLines.push([`Companies Hiring: ${companies.length}`])
  }

  if (reportTitle.includes('Application')) {
    const shortlisted = rows.filter((r) => r.shortlisted).length
    const pending     = rows.filter((r) => r.status === 'pending').length
    const rejected    = rows.filter((r) => r.status === 'rejected').length
    const scores      = rows.map((r) => r.match_score).filter((v) => v != null)
    const avgScore    = scores.length ? (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1) : 'N/A'
    summaryLines.push([`Total Applications: ${rows.length}`])
    summaryLines.push([`Shortlisted: ${shortlisted}   |   Pending: ${pending}   |   Rejected: ${rejected}`])
    summaryLines.push([`Average Match Score: ${avgScore}%`])
  }

  return summaryLines
}

// ─── Public API ──────────────────────────────────────────────────────────────

/**
 * Build and download a formatted .xlsx file for a single entity type.
 * @param {string} filename   e.g. "admins-report-2026-03-09.xlsx"
 * @param {string} sheetName  e.g. "HR Admins"
 * @param {string} title      e.g. "HR Admins Report"
 * @param {Array}  rows       Data rows
 * @param {Array}  columns    Column definitions
 */
export function downloadReport(filename, sheetName, title, rows, columns) {
  const wb = XLSX.utils.book_new()
  const ws = buildWorksheet(title, rows, columns)
  XLSX.utils.book_append_sheet(wb, ws, sheetName)
  XLSX.writeFile(wb, filename)
}

/**
 * Download a combined workbook with all 4 reports on separate sheets.
 * @param {object} allData  { admins, candidates, jobs, applications }
 */
export function downloadFullReport(allData) {
  const wb = XLSX.utils.book_new()

  const sheets = [
    { key: 'admins',       sheetName: 'HR Admins',     title: 'HR Admins Report',       cols: ADMIN_COLUMNS },
    { key: 'candidates',   sheetName: 'Candidates',    title: 'Candidates Report',      cols: CANDIDATE_COLUMNS },
    { key: 'jobs',         sheetName: 'Jobs',          title: 'Jobs Report',            cols: JOB_COLUMNS },
    { key: 'applications', sheetName: 'Applications',  title: 'Applications Report',    cols: APPLICATION_COLUMNS },
  ]

  for (const { key, sheetName, title, cols } of sheets) {
    const ws = buildWorksheet(title, allData[key] || [], cols)
    XLSX.utils.book_append_sheet(wb, ws, sheetName)
  }

  XLSX.writeFile(wb, `hr-portal-full-report-${todayStr()}.xlsx`)
}

// ─── Legacy CSV kept for backwards compat (unused) ───────────────────────────
export function downloadCsv(filename, rows, columns) {
  downloadReport(
    filename.replace('.csv', '.xlsx'),
    'Report',
    'Report',
    rows,
    columns,
  )
}
