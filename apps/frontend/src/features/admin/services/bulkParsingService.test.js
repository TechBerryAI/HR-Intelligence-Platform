import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  ensureOutputWritable,
  fetchBulkResultBlob,
  loadBulkJobSession,
  saveBulkJobSession,
  writeBulkResultToOutput,
} from './bulkParsingService.js'

// Minimal valid ZIP/XLSX local-file-header signature + filler bytes.
const XLSX_BYTES = new Uint8Array([0x50, 0x4b, 0x03, 0x04, 1, 2, 3, 4])

describe('bulk Excel export', () => {
  let fetchMock

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns the workbook when the server sends a real xlsx', async () => {
    fetchMock.mockResolvedValue(
      new Response(XLSX_BYTES, {
        status: 200,
        headers: { 'Content-Disposition': 'attachment; filename="Parsed_Resumes.xlsx"' },
      })
    )
    const { blob, filename } = await fetchBulkResultBlob('job-1')
    expect(filename).toBe('Parsed_Resumes.xlsx')
    expect(blob.size).toBe(XLSX_BYTES.length)
  })

  it('refuses to hand back bytes that are not an xlsx (e.g. an HTML page)', async () => {
    fetchMock.mockResolvedValue(new Response('<!doctype html><html></html>', { status: 200 }))
    await expect(fetchBulkResultBlob('job-1')).rejects.toThrow(/valid Excel/)
  })

  it('writes the workbook into the file the save picker created', async () => {
    const written = []
    const writable = {
      write: vi.fn(async (b) => written.push(b)),
      close: vi.fn(async () => {}),
      abort: vi.fn(async () => {}),
    }
    const fileHandle = {
      name: 'Parsed_Resumes.xlsx',
      queryPermission: vi.fn(async () => 'granted'),
      createWritable: vi.fn(async () => writable),
    }
    const blob = new Blob([XLSX_BYTES])
    await expect(writeBulkResultToOutput(blob, { fileHandle })).resolves.toBe('Parsed_Resumes.xlsx')
    expect(written).toEqual([blob])
    expect(writable.close).toHaveBeenCalled()
  })

  it('aborts instead of leaving a half-written file when the write fails', async () => {
    const writable = {
      write: vi.fn(async () => {
        throw new Error('disk full')
      }),
      close: vi.fn(),
      abort: vi.fn(async () => {}),
    }
    const fileHandle = { name: 'x.xlsx', createWritable: vi.fn(async () => writable) }
    await expect(writeBulkResultToOutput(new Blob([XLSX_BYTES]), { fileHandle })).rejects.toThrow('disk full')
    expect(writable.abort).toHaveBeenCalled()
    expect(writable.close).not.toHaveBeenCalled()
  })
})

describe('output write permission after a reload', () => {
  const handleWith = (state, grant = 'granted') => ({
    name: 'Parsed_Resumes.xlsx',
    queryPermission: vi.fn(async () => state),
    requestPermission: vi.fn(async () => grant),
  })

  it('an automatic save never prompts — it reports PERMISSION_REQUIRED instead', async () => {
    const fileHandle = handleWith('prompt')
    await expect(ensureOutputWritable({ fileHandle }, { interactive: false })).rejects.toMatchObject({
      code: 'PERMISSION_REQUIRED',
    })
    expect(fileHandle.requestPermission).not.toHaveBeenCalled()
  })

  it('a click-driven save asks the browser for permission', async () => {
    const fileHandle = handleWith('prompt', 'granted')
    await expect(ensureOutputWritable({ fileHandle }, { interactive: true })).resolves.toBeUndefined()
    expect(fileHandle.requestPermission).toHaveBeenCalledWith({ mode: 'readwrite' })
  })

  it('reports a denied prompt', async () => {
    const dirHandle = handleWith('prompt', 'denied')
    await expect(ensureOutputWritable({ dirHandle })).rejects.toMatchObject({ code: 'PERMISSION_DENIED' })
  })

  it('Electron paths need no browser permission', async () => {
    await expect(ensureOutputWritable({ path: 'C:/out/Parsed_Resumes.xlsx' }, { interactive: false })).resolves.toBeUndefined()
  })
})

describe('active bulk job session', () => {
  afterEach(() => sessionStorage.clear())

  it('is restored for the account that started it', () => {
    saveBulkJobSession('job-1', 'hr-a')
    expect(loadBulkJobSession('hr-a')?.jobId).toBe('job-1')
  })

  it('is dropped when a different account logs in on the same tab', () => {
    saveBulkJobSession('job-1', 'hr-a')
    expect(loadBulkJobSession('hr-b')).toBeNull()
    expect(loadBulkJobSession('hr-a')).toBeNull()
  })
})
