import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { bookSlot, fetchBooking } from '@/features/interview/services/bookingApi.js'

const IST = 'Asia/Kolkata'

function formatSlot(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return String(iso)
  return d.toLocaleString('en-IN', {
    timeZone: IST,
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
}

export default function BookInterview() {
  const { token } = useParams()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [payload, setPayload] = useState(null)
  const [selected, setSelected] = useState('')
  const [booking, setBooking] = useState(false)
  const [confirmed, setConfirmed] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchBooking(token)
      setPayload(data)
      if (data?.status === 'scheduled') {
        setConfirmed(data)
      }
    } catch (e) {
      setError(e.message || 'Unable to load booking')
      setPayload(e.data || null)
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    load()
  }, [load])

  const slots = useMemo(() => payload?.slots || [], [payload])

  async function onConfirm() {
    if (!selected) return
    setBooking(true)
    setError('')
    try {
      const data = await bookSlot(token, selected)
      setConfirmed(data)
      setPayload({ ...payload, status: 'scheduled', ...data })
    } catch (e) {
      setError(e.message || 'Booking failed')
      if (e.data?.slots) {
        setPayload((prev) => ({ ...(prev || {}), slots: e.data.slots }))
        setSelected('')
      }
    } finally {
      setBooking(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <div className="mx-auto max-w-lg px-4 py-12">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">HR Intelligence</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">Interview booking</h1>

        {loading && <p className="mt-8 text-slate-600">Loading available times…</p>}

        {!loading && error && !confirmed && (
          <p className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
        )}

        {!loading && confirmed && (
          <div className="mt-8 rounded-xl border border-emerald-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-emerald-800">Interview confirmed</h2>
            <p className="mt-2 text-sm text-slate-600">
              {formatSlot(confirmed.scheduledAt || confirmed.scheduled_at)}
            </p>
            {(confirmed.meetLink || confirmed.meet_link) && (
              <a
                href={confirmed.meetLink || confirmed.meet_link}
                target="_blank"
                rel="noreferrer"
                className="mt-4 inline-flex text-sm font-medium text-sky-700 underline"
              >
                Join Google Meet
              </a>
            )}
          </div>
        )}

        {!loading && !confirmed && payload?.status === 'invited' && (
          <div className="mt-8 space-y-4">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-sm text-slate-500">Role</p>
              <p className="font-medium text-slate-900">{payload.jobTitle || '—'}</p>
              <p className="mt-3 text-sm text-slate-500">Company</p>
              <p className="font-medium text-slate-900">{payload.companyName || '—'}</p>
              {payload.recruiterName ? (
                <>
                  <p className="mt-3 text-sm text-slate-500">Recruiter</p>
                  <p className="font-medium text-slate-900">{payload.recruiterName}</p>
                </>
              ) : null}
              <p className="mt-3 text-xs text-slate-500">
                Duration: {payload.durationMinutes || 30} minutes
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-sm font-semibold text-slate-900">Choose a slot</h2>
              {slots.length === 0 ? (
                <p className="mt-3 text-sm text-slate-600">No slots are available right now.</p>
              ) : (
                <ul className="mt-3 max-h-80 space-y-2 overflow-y-auto">
                  {slots.map((slot) => (
                    <li key={slot.id}>
                      <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-slate-200 px-3 py-2 hover:bg-slate-50">
                        <input
                          type="radio"
                          name="slot"
                          value={slot.id}
                          checked={selected === slot.id}
                          onChange={() => setSelected(slot.id)}
                        />
                        <span className="text-sm text-slate-800">{formatSlot(slot.startTime)}</span>
                      </label>
                    </li>
                  ))}
                </ul>
              )}
              <button
                type="button"
                disabled={!selected || booking || slots.length === 0}
                onClick={onConfirm}
                className="mt-4 w-full rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                {booking ? 'Confirming…' : 'Confirm interview'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
