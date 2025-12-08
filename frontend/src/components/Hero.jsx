import React from 'react'
import SearchBar from './SearchBar.jsx'

export default function Hero({ onSearch }) {
  return (
    <section className="relative overflow-hidden animated-hero">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
        <div className="max-w-3xl mx-auto text-center animate-[floatIn_500ms_ease_1]">
          <h1 className="text-3xl sm:text-5xl font-bold tracking-tight text-white">
            Find your dream job now
          </h1>
          <p className="mt-4 text-zinc-300 max-w-2xl mx-auto">
            Explore thousands of opportunities from top companies. Search by skills, titles, or location.
          </p>
        </div>

        <div className="mt-8 max-w-3xl mx-auto animate-[floatIn_650ms_ease_1]">
          <SearchBar onSearch={onSearch} large />
        </div>
      </div>
    </section>
  )
}


