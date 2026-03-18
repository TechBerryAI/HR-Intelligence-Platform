import React from 'react'
import { parseJobDescriptionBlocks } from '@/lib/jobDescription.js'

/**
 * Renders job description with structured sections (**Title:**) and bullet lists (•).
 * Use for modal, detail page, or any place job.description is shown.
 */
export default function JobDescriptionView({ description, className = '', titleClassName = '', textClassName = 'text-slate-600' }) {
  if (!description || typeof description !== 'string') {
    return <p className={textClassName}>No description provided.</p>
  }
  const blocks = parseJobDescriptionBlocks(description)
  if (blocks.length === 0) {
    return <p className={`whitespace-pre-wrap ${textClassName}`}>{description}</p>
  }
  return (
    <div className={`text-sm leading-relaxed space-y-4 ${className}`}>
      {blocks.map((block, bi) => (
        <section key={bi} className="space-y-2">
          {block.title && (
            <h4 className={`text-sm font-semibold text-slate-800 mt-4 first:mt-0 ${titleClassName}`}>
              {block.title}
            </h4>
          )}
          {block.lines.map((line, li) => {
            if (line.type === 'list' && line.items?.length) {
              return (
                <ul key={li} className="list-disc list-inside space-y-1 ml-0 pl-1">
                  {line.items.map((item, ii) => (
                    <li key={ii} className={textClassName}>{item}</li>
                  ))}
                </ul>
              )
            }
            if (line.type === 'para' && line.text) {
              return <p key={li} className={textClassName}>{line.text}</p>
            }
            return null
          })}
        </section>
      ))}
    </div>
  )
}
