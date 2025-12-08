import React, { useMemo } from 'react'
import { getAvatarGradient } from '../utils/avatarColor'

// Helper function to get score color and label
const getScoreInfo = (score) => {
  if (score >= 80) return { color: 'text-green-400', bgColor: 'bg-green-900/30', ringColor: 'ring-green-700', label: 'Excellent Match' }
  if (score >= 70) return { color: 'text-emerald-400', bgColor: 'bg-emerald-900/30', ringColor: 'ring-emerald-700', label: 'Great Match' }
  if (score >= 60) return { color: 'text-blue-400', bgColor: 'bg-blue-900/30', ringColor: 'ring-blue-700', label: 'Good Match' }
  if (score >= 50) return { color: 'text-cyan-400', bgColor: 'bg-cyan-900/30', ringColor: 'ring-cyan-700', label: 'Fair Match' }
  if (score >= 40) return { color: 'text-yellow-400', bgColor: 'bg-yellow-900/30', ringColor: 'ring-yellow-700', label: 'Moderate Match' }
  if (score >= 30) return { color: 'text-orange-400', bgColor: 'bg-orange-900/30', ringColor: 'ring-orange-700', label: 'Low Match' }
  return { color: 'text-red-400', bgColor: 'bg-red-900/30', ringColor: 'ring-red-700', label: 'Poor Match' }
}

// Helper function to format date
const formatDate = (dateString) => {
  if (!dateString) return 'N/A'
  try {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
  } catch {
    return dateString
  }
}

export default function CandidateCard({ candidate, onViewDetails }) {
  // Ensure score is a number and round it for display
  const rawScore = candidate.matchScore || candidate.score || 0
  const score = Math.round(Number(rawScore))
  const scoreInfo = getScoreInfo(score)
  const avatarGradient = useMemo(() => {
    const key =
      candidate.email ||
      candidate.fullName ||
      candidate.name ||
      candidate.candidateId ||
      candidate.id ||
      ''
    return getAvatarGradient(key)
  }, [candidate])
  
  return (
    <div className="group relative rounded-xl bg-zinc-800/50 ring-1 ring-zinc-700/50 p-5 transition-all duration-300 hover:bg-zinc-800 hover:ring-zinc-600 hover:shadow-lg hover:-translate-y-0.5">
      {/* Score Badge - Top Right */}
      <div className="absolute top-4 right-4 flex flex-col items-end gap-1">
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full ${scoreInfo.bgColor} ring-1 ${scoreInfo.ringColor}`}>
          <div className="flex items-center gap-1.5">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className={`w-4 h-4 ${scoreInfo.color}`}>
              <path fillRule="evenodd" d="M10.788 3.21c.448-1.077 1.976-1.077 2.424 0l2.082 5.006 5.404.434c1.164.093 1.636 1.545.749 2.305l-4.117 3.527 1.257 5.273c.271 1.136-.964 2.033-1.96 1.425L12 18.354 7.373 21.18c-.996.608-2.231-.29-1.96-1.425l1.257-5.273-4.117-3.527c-.887-.76-.415-2.212.749-2.305l5.404-.434 2.082-5.005Z" clipRule="evenodd" />
            </svg>
            <span className={`text-lg font-bold ${scoreInfo.color}`}>{score}%</span>
          </div>
        </div>
        <span className={`text-[9px] font-semibold tracking-wide ${scoreInfo.color}`}>{scoreInfo.label}</span>
      </div>

      {/* Candidate Info */}
      <div className="pr-24">
        <div className="flex items-start gap-3">
          {/* Avatar */}
          <div
            className="flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center text-white font-semibold text-lg ring-2 ring-zinc-700"
            style={{ backgroundImage: avatarGradient }}
          >
            {candidate.fullName?.charAt(0)?.toUpperCase() || candidate.name?.charAt(0)?.toUpperCase() || 'C'}
          </div>
          
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold text-white truncate">{candidate.fullName || candidate.name || 'Unknown Candidate'}</h3>
            <div className="mt-1 flex items-center gap-2 text-sm text-zinc-400">
              <span className="inline-flex items-center gap-1">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
                  <path d="M1.5 8.67v8.58a3 3 0 0 0 3 3h15a3 3 0 0 0 3-3V8.67l-8.928 5.493a3 3 0 0 1-3.144 0L1.5 8.67Z" />
                  <path d="M22.5 6.908V6.75a3 3 0 0 0-3-3h-15a3 3 0 0 0-3 3v.158l9.714 5.978a1.5 1.5 0 0 0 1.572 0L22.5 6.908Z" />
                </svg>
                {candidate.email || 'N/A'}
              </span>
            </div>
          </div>
        </div>

        {/* Details Grid */}
        <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
          {/* Phone */}
          {candidate.phone && (
            <div className="flex items-center gap-2 text-zinc-300">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 text-zinc-500">
                <path fillRule="evenodd" d="M1.5 4.5a3 3 0 0 1 3-3h1.372c.86 0 1.61.586 1.819 1.42l1.105 4.423a1.875 1.875 0 0 1-.694 1.955l-1.293.97c-.135.101-.164.249-.126.352a11.285 11.285 0 0 0 6.697 6.697c.103.038.25.009.352-.126l.97-1.293a1.875 1.875 0 0 1 1.955-.694l4.423 1.105c.834.209 1.42.959 1.42 1.82V19.5a3 3 0 0 1-3 3h-2.25C8.552 22.5 1.5 15.448 1.5 6.75V4.5Z" clipRule="evenodd" />
              </svg>
              <span>{candidate.phone}</span>
            </div>
          )}

          {/* Location */}
          {candidate.currentLocation && (
            <div className="flex items-center gap-2 text-zinc-300">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 text-zinc-500">
                <path fillRule="evenodd" d="m11.54 22.351.07.04.028.016a.76.76 0 0 0 .723 0l.028-.015.071-.041a16.975 16.975 0 0 0 1.144-.742 19.58 19.58 0 0 0 2.683-2.282c1.944-1.99 3.963-4.98 3.963-8.827a8.25 8.25 0 0 0-16.5 0c0 3.846 2.02 6.837 3.963 8.827a19.58 19.58 0 0 0 2.682 2.282 16.975 16.975 0 0 0 1.145.742ZM12 13.5a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" clipRule="evenodd" />
              </svg>
              <span className="truncate">{candidate.currentLocation}</span>
            </div>
          )}

          {/* Experience Level */}
          {candidate.experienceLevel && (
            <div className="flex items-center gap-2 text-zinc-300">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 text-zinc-500">
                <path fillRule="evenodd" d="M7.5 5.25a3 3 0 0 1 3-3h3a3 3 0 0 1 3 3V8.25a.75.75 0 0 1-1.5 0V5.25a1.5 1.5 0 0 0-1.5-1.5h-3a1.5 1.5 0 0 0-1.5 1.5v3a.75.75 0 0 1-1.5 0V5.25Zm-1.5 3.75A2.25 2.25 0 0 0 3.75 11.25v8.25A2.25 2.25 0 0 0 6 21.75h12a2.25 2.25 0 0 0 2.25-2.25v-8.25A2.25 2.25 0 0 0 18 9H6Z" clipRule="evenodd" />
              </svg>
              <span className="capitalize">{candidate.experienceLevel}</span>
            </div>
          )}

          {/* Notice Period */}
          {candidate.noticePeriod && (
            <div className="flex items-center gap-2 text-zinc-300">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 text-zinc-500">
                <path fillRule="evenodd" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25ZM12.75 6a.75.75 0 0 0-1.5 0v6c0 .414.336.75.75.75h4.5a.75.75 0 0 0 0-1.5h-3.75V6Z" clipRule="evenodd" />
              </svg>
              <span>{candidate.noticePeriod}</span>
            </div>
          )}

          {/* Applied Date */}
          {candidate.appliedAt && (
            <div className="flex items-center gap-2 text-zinc-400 col-span-2">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 text-zinc-500">
                <path d="M12.75 12.75a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0ZM7.5 15.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5ZM8.25 17.25a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0ZM9.75 15.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5ZM10.5 17.25a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0ZM12 15.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5ZM12.75 17.25a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0ZM14.25 15.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5ZM15 17.25a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0ZM16.5 15.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5ZM15 12.75a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0ZM16.5 13.5a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Z" />
                <path fillRule="evenodd" d="M6.75 2.25A.75.75 0 0 1 7.5 3v1.5h9V3A.75.75 0 0 1 18 3v1.5h.75a3 3 0 0 1 3 3v11.25a3 3 0 0 1-3 3H5.25a3 3 0 0 1-3-3V7.5a3 3 0 0 1 3-3H6V3a.75.75 0 0 1 .75-.75Zm13.5 9a1.5 1.5 0 0 0-1.5-1.5H5.25a1.5 1.5 0 0 0-1.5 1.5v7.5a1.5 1.5 0 0 0 1.5 1.5h13.5a1.5 1.5 0 0 0 1.5-1.5v-7.5Z" clipRule="evenodd" />
              </svg>
              <span className="text-xs">Applied on {formatDate(candidate.appliedAt)}</span>
            </div>
          )}
        </div>

        {/* Skills/Education Preview */}
        {candidate.education && candidate.education.length > 0 && (
          <div className="mt-3 pt-3 border-t border-zinc-700/50">
            <div className="flex items-center gap-2 text-xs text-zinc-400">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
                <path d="M11.7 2.805a.75.75 0 0 1 .6 0A60.65 60.65 0 0 1 22.83 8.72a.75.75 0 0 1-.231 1.337 49.948 49.948 0 0 0-9.902 3.912l-.003.002c-.114.06-.227.119-.34.18a.75.75 0 0 1-.707 0A50.88 50.88 0 0 0 7.5 12.173v-.224c0-.131.067-.248.172-.311a54.615 54.615 0 0 1 4.653-2.52.75.75 0 0 0-.65-1.352 56.123 56.123 0 0 0-4.78 2.589 1.858 1.858 0 0 0-.859 1.228 49.803 49.803 0 0 0-4.634-1.527.75.75 0 0 1-.231-1.337A60.653 60.653 0 0 1 11.7 2.805Z" />
                <path d="M13.06 15.473a48.45 48.45 0 0 1 7.666-3.282c.134 1.414.22 2.843.255 4.284a.75.75 0 0 1-.46.711 47.87 47.87 0 0 0-8.105 4.342.75.75 0 0 1-.832 0 47.87 47.87 0 0 0-8.104-4.342.75.75 0 0 1-.461-.71c.035-1.442.121-2.87.255-4.286.921.304 1.83.634 2.726.99v1.27a1.5 1.5 0 0 0-.14 2.508c-.09.38-.222.753-.397 1.11.452.213.901.434 1.346.66a6.727 6.727 0 0 0 .551-1.607 1.5 1.5 0 0 0 .14-2.67v-.645a48.549 48.549 0 0 1 3.44 1.667 2.25 2.25 0 0 0 2.12 0Z" />
              </svg>
              <span className="truncate">{candidate.education[0].degree} - {candidate.education[0].institution}</span>
            </div>
          </div>
        )}

        {/* Action Button */}
        <div className="mt-4 pt-4 border-t border-zinc-700/50">
          <button
            onClick={() => onViewDetails && onViewDetails(candidate)}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-white/5 hover:bg-white/10 text-white font-medium text-sm transition-all duration-200 ring-1 ring-white/10 hover:ring-white/20 group-hover:bg-white/10"
          >
            <span>View Full Profile</span>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 transition-transform group-hover:translate-x-0.5">
              <path fillRule="evenodd" d="M16.28 11.47a.75.75 0 0 1 0 1.06l-7.5 7.5a.75.75 0 0 1-1.06-1.06L14.69 12 7.72 5.03a.75.75 0 0 1 1.06-1.06l7.5 7.5Z" clipRule="evenodd" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}
