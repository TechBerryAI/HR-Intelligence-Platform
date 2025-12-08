import React, { useState } from 'react'

export default function SearchBar({ onSearch, large = false, defaultQuery = {}, className = '' }) {
  const [keywords, setKeywords] = useState(defaultQuery.keywords || '')
  const [location, setLocation] = useState(defaultQuery.location || '')

  const submit = (e) => {
    e.preventDefault()
    onSearch?.({ keywords: keywords.trim(), location: location.trim() })
  }

  return (
    <form onSubmit={submit} className={`w-full ${className}`}>
      <div className={`flex flex-col sm:flex-row gap-3 sm:gap-0 bg-zinc-800 rounded-2xl shadow ring-1 ring-zinc-700 ${large ? 'p-2' : 'p-1.5'} overflow-hidden`}>
        <div className="flex-1 flex items-center gap-3 px-4 py-3">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 text-zinc-400"><path fillRule="evenodd" d="M10.5 3.75a6.75 6.75 0 1 0 4.21 12.029l3.255 3.256a.75.75 0 1 0 1.06-1.06l-3.255-3.256A6.75 6.75 0 0 0 10.5 3.75Zm-5.25 6.75a5.25 5.25 0 1 1 10.5 0 5.25 5.25 0 0 1-10.5 0Z" clipRule="evenodd" /></svg>
          <input
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            className="w-full outline-none placeholder:text-zinc-400 text-gray-100 bg-transparent"
            placeholder="Title, skills, or company"
          />
        </div>
        <div className="w-px bg-zinc-700 hidden sm:block" />
        <div className="flex-1 flex items-center gap-3 px-4 py-3">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 text-zinc-400"><path d="M11.54 22.351l-.002.001C8.25 19.52 3 14.706 3 10.5 3 6.358 6.358 3 10.5 3S18 6.358 18 10.5c0 4.206-5.25 9.02-8.458 11.851l-.002-.001a.75.75 0 0 1-1.001 0zM10.5 12.75a2.25 2.25 0 1 0 0-4.5 2.25 2.25 0 0 0 0 4.5z"/></svg>
          <input
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            className="w-full outline-none placeholder:text-zinc-400 text-gray-100 bg-transparent"
            placeholder="Location"
          />
        </div>
        <button type="submit" className="sm:ml-2 bg-white hover:bg-gray-100 text-black font-medium px-6 py-3 rounded-xl transition">
          Search
        </button>
      </div>
    </form>
  )
}


