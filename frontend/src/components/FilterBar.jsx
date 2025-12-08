import React from 'react'
import SearchBar from './SearchBar.jsx'

export default function FilterBar({ onSearch, initial }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-3">
      <SearchBar key={`${initial.keywords}|${initial.location}`} onSearch={onSearch} defaultQuery={initial} />
    </div>
  )
}


