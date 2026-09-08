import React, { useEffect, useRef, useState } from 'react'

/**
 * Renders a local PDF as canvases so Chrome CSP cannot block the built-in viewer.
 */
export default function ResumePdfPages({ file }) {
  const hostRef = useRef(null)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState('')

  useEffect(() => {
    const host = hostRef.current
    if (!file || !host) return undefined

    let cancelled = false
    let pdfDoc = null

    const render = async () => {
      setStatus('loading')
      setError('')
      host.replaceChildren()
      try {
        const pdfjs = await import('pdfjs-dist')
        const workerMod = await import('pdfjs-dist/build/pdf.worker.min.mjs?url')
        pdfjs.GlobalWorkerOptions.workerSrc = workerMod.default
        const data = new Uint8Array(await file.arrayBuffer())
        pdfDoc = await pdfjs.getDocument({ data }).promise
        if (cancelled) return

        const cssWidth = Math.max(320, host.clientWidth || 800)
        const dpr = window.devicePixelRatio || 1
        for (let i = 1; i <= pdfDoc.numPages; i += 1) {
          const page = await pdfDoc.getPage(i)
          if (cancelled) return
          const base = page.getViewport({ scale: 1 })
          const cssScale = Math.min(2, Math.max(0.75, (cssWidth - 8) / base.width))
          const viewport = page.getViewport({ scale: cssScale * dpr })
          const canvas = document.createElement('canvas')
          canvas.width = Math.floor(viewport.width)
          canvas.height = Math.floor(viewport.height)
          canvas.style.width = `${Math.floor(viewport.width / dpr)}px`
          canvas.style.height = `${Math.floor(viewport.height / dpr)}px`
          canvas.className = 'mx-auto mb-3 block max-w-full bg-white shadow-md'
          canvas.setAttribute('aria-label', `Page ${i}`)
          const ctx = canvas.getContext('2d', { alpha: false })
          await page.render({ canvasContext: ctx, viewport }).promise
          if (cancelled) return
          host.appendChild(canvas)
        }
        setStatus('ready')
      } catch (err) {
        if (!cancelled) {
          setStatus('error')
          setError('Could not display this PDF.')
        }
      }
    }

    render()
    return () => {
      cancelled = true
      try {
        pdfDoc?.destroy()
      } catch {
        /* ignore */
      }
      host.replaceChildren()
    }
  }, [file])

  return (
    <div className="relative h-full overflow-auto bg-slate-200/90 p-3">
      {status === 'loading' ? (
        <div className="absolute inset-0 z-10 flex items-center justify-center text-sm text-slate-600">
          Loading preview…
        </div>
      ) : null}
      {status === 'error' ? (
        <div className="flex h-full items-center justify-center text-sm text-slate-700">{error}</div>
      ) : null}
      <div ref={hostRef} className={status === 'ready' ? '' : 'min-h-[40vh]'} />
    </div>
  )
}
