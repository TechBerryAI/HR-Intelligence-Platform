import React, { useEffect, useRef, useState } from 'react'
import Modal from '@/shared/components/ui/Modal.jsx'

import { HERO_VIDEO_SRC, heroVideoRetrySrc } from '../constants/heroVideo.js'

export default function WatchDemoModal({ open, onClose }) {
  const [src, setSrc] = useState(HERO_VIDEO_SRC)
  const retryUsed = useRef(false)

  useEffect(() => {
    if (!open) return
    retryUsed.current = false
    setSrc(HERO_VIDEO_SRC)
  }, [open])

  return (
    <Modal open={open} onClose={onClose} title="Platform Demo" size="xl">
      <div className="rounded-xl overflow-hidden bg-slate-900 aspect-video">
        <video
          key={open ? src : 'paused'}
          className="w-full h-full object-cover"
          controls
          autoPlay={open}
          playsInline
          preload="metadata"
          onError={() => {
            if (retryUsed.current) return
            retryUsed.current = true
            setSrc(heroVideoRetrySrc(HERO_VIDEO_SRC))
          }}
        >
          <source src={src} type="video/mp4" />
          Your browser does not support the video tag.
        </video>
      </div>
      <p className="mt-3 text-sm text-slate-500 dark:text-slate-400 text-center">
        Experience the AI-powered HR intelligence platform in action.
      </p>
    </Modal>
  )
}
