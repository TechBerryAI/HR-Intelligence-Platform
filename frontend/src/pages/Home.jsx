import React from 'react'
import { useNavigate } from 'react-router-dom'
import Hero from '../components/Hero.jsx'

export default function Home() {
  const navigate = useNavigate()

  const handleSearch = ({ keywords, location }) => {
    const params = new URLSearchParams()
    if (keywords) params.set('q', keywords)
    if (location) params.set('loc', location)
    navigate(`/jobs?${params.toString()}`)
  }

  return (
    <>
      <Hero onSearch={handleSearch} />
    </>
  )
}


