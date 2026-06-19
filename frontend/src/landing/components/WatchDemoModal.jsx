import React from 'react'
import Modal from '../../components/ui/Modal.jsx'

import { HERO_VIDEO_SRC } from '../constants/heroVideo.js'

export default function WatchDemoModal({ open, onClose }) {
  return (
    <Modal open={open} onClose={onClose} title="Platform Demo" size="xl">
      <div className="rounded-xl overflow-hidden bg-slate-900 aspect-video">
        <video
          key={open ? 'playing' : 'paused'}
          className="w-full h-full object-cover"
          controls
          autoPlay={open}
          playsInline
          preload="metadata"
        >
          <source src={HERO_VIDEO_SRC} type="video/mp4" />
          Your browser does not support the video tag.
        </video>
      </div>
      <p className="mt-3 text-sm text-slate-500 dark:text-slate-400 text-center">
        Experience the AI-powered HR intelligence platform in action.
      </p>
    </Modal>
  )
}
