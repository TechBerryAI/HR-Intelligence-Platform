import { useState, useCallback, useRef } from 'react'

/**
 * Guards an async action: prevents running again while in progress, exposes loading state.
 * Use for buttons that trigger API calls so multiple clicks don't fire twice and the UI shows progress.
 * @returns {{ run: (fn: () => Promise<any>) => Promise<any>, loading: boolean }}
 */
export function useAsyncAction() {
  const [loading, setLoading] = useState(false)
  const busyRef = useRef(false)

  const run = useCallback(async (asyncFn) => {
    if (busyRef.current) return
    busyRef.current = true
    setLoading(true)
    try {
      return await (typeof asyncFn === 'function' ? asyncFn() : asyncFn)
    } finally {
      busyRef.current = false
      setLoading(false)
    }
  }, [])

  return { run, loading }
}
