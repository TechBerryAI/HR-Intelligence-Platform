import React from 'react'

// Helper function to format date for display
const formatDisplayDate = (dateString) => {
  if (!dateString) return ''
  try {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
  } catch {
    return dateString
  }
}

export default function JobCard({ job, onApply, isApplied = false, isSaved = false, onToggleSave, isAdmin = false }) {
  const isDisabled = job.enabled === false
  return (
    <div className={`group rounded-xl shadow-sm ring-1 p-5 transition transform duration-200 ease-out hover:-translate-y-0.5 hover:shadow-lg ${
      isDisabled
        ? 'bg-zinc-800 ring-zinc-700 opacity-60 pointer-events-none'
        : 'bg-zinc-800 ring-zinc-700 hover:shadow-md'
    }`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className={`text-lg font-semibold transition ${isDisabled ? 'text-zinc-400' : 'text-white'}`}>{job.title}</h3>
            {isApplied && (
              <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-green-900/30 text-green-300 ring-1 ring-green-700">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-3 h-3"><path fillRule="evenodd" d="M2.25 12a9.75 9.75 0 1 1 19.5 0 9.75 9.75 0 0 1-19.5 0Zm13.36-2.56a.75.75 0 1 0-1.06-1.06L10.5 12.44l-1.49-1.49a.75.75 0 1 0-1.06 1.06l2.02 2.02c.3.3.79.3 1.09 0l4.14-4.59Z" clipRule="evenodd"/></svg>
                Applied
              </span>
            )}
            {!isApplied && isSaved && (
              <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-blue-900/30 text-blue-300 ring-1 ring-blue-700">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-3 h-3"><path d="M6.32 2.577A2.25 2.25 0 0 1 8.06 2.25h7.88a2.25 2.25 0 0 1 2.25 2.25V20.1a.75.75 0 0 1-1.133.64l-6.057-3.63a1.5 1.5 0 0 0-1.56 0l-6.057 3.63A.75.75 0 0 1 2.25 20.1V4.5a2.25 2.25 0 0 1 2.25-2.25h1.82Z"/></svg>
                Saved
              </span>
            )}
          </div>
          <div className={`mt-1 text-sm ${isDisabled ? 'text-zinc-400' : 'text-zinc-300'}`}>{job.company}</div>
          <div className={`mt-2 flex items-center gap-4 text-sm ${isDisabled ? 'text-zinc-500' : 'text-zinc-400'}`}>
            <span className="inline-flex items-center gap-1">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M11.54 22.351l-.002.001C8.25 19.52 3 14.706 3 10.5 3 6.358 6.358 3 10.5 3S18 6.358 18 10.5c0 4.206-5.25 9.02-8.458 11.851l-.002-.001a.75.75 0 0 1-1.001 0zM10.5 12.75a2.25 2.25 0 1 0 0-4.5 2.25 2.25 0 0 0 0 4.5z"/></svg>
              {job.location}
            </span>
            {job.salary ? (
              <span className="inline-flex items-center gap-1">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M12 2.25a9.75 9.75 0 1 0 9.75 9.75A9.76 9.76 0 0 0 12 2.25Zm.75 15.5v1a.75.75 0 0 1-1.5 0v-1a4.251 4.251 0 0 1-3.75-4.206.75.75 0 0 1 1.5 0 2.75 2.75 0 1 0 2.75-2.75H10a.75.75 0 0 1 0-1.5h1.25v-1a.75.75 0 0 1 1.5 0v1a4.25 4.25 0 0 1 3.75 4.25.75.75 0 0 1-1.5 0 2.75 2.75 0 1 0-2.75 2.75h.25a.75.75 0 0 1 0 1.5h-.25a.75.75 0 0 1 0 1.5h.25Z"/></svg>
                {job.salary}
              </span>
            ) : null}
            {job.experienceFrom || job.experienceTo ? (
              <span className="inline-flex items-center gap-1">
                {(job.experienceFrom ?? '')}{(job.experienceFrom || job.experienceTo) ? '-' : ''}{(job.experienceTo ?? '')} yrs
              </span>
            ) : null}
          </div>
          {job.postedOn && (
            <div className={`mt-2 text-xs ${isDisabled ? 'text-zinc-500' : 'text-zinc-400'}`}>
              <span className="inline-flex items-center gap-1">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-3 h-3"><path d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25ZM12.75 6a.75.75 0 0 0-1.5 0v6c0 .414.336.75.75.75h4.5a.75.75 0 0 0 0-1.5h-3.75V6Z"/></svg>
                Posted on {formatDisplayDate(job.postedOn)}
              </span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!isAdmin && (
            <button
              disabled={isDisabled || isApplied}
              onClick={onApply}
              className={`text-sm font-medium px-4 py-2 rounded-lg transition ${
                isDisabled || isApplied ? 'bg-zinc-700 text-zinc-400 cursor-not-allowed' : 'bg-white hover:bg-gray-100 text-black'
              }`}
            >
              {isApplied ? 'Applied' : 'Apply'}
            </button>
          )}
          {!isAdmin && onToggleSave && !isApplied && (
            <button
              type="button"
              onClick={onToggleSave}
              className={`text-xs px-3 py-2 rounded-lg border transition ${isSaved ? 'border-green-500 text-green-300 bg-green-900/20' : 'border-zinc-700 text-zinc-300 hover:bg-zinc-700/50'}`}
            >
              {isSaved ? 'Saved' : 'Save'}
            </button>
          )}
          {!isAdmin && onToggleSave && isApplied && (
            <button
              type="button"
              disabled
              className="text-xs px-3 py-2 rounded-lg border border-zinc-700 text-zinc-500 cursor-not-allowed"
              title="Already applied"
            >
              Save
            </button>
          )}
        </div>
      </div>
      {job.description ? (
        <p className={`mt-3 text-sm line-clamp-2 ${isDisabled ? 'text-zinc-500' : 'text-zinc-300'}`}>{job.description}</p>
      ) : null}
    </div>
  )
}


