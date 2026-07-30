/**
 * Parse job descriptions with structured **Title:** sections and • bullet lists.
 */

const SECTION_TITLE_RE = /^\*\*(.+?)\*\*\s*:?\s*$/
const BULLET_RE = /^[•\-\*]\s+(.+)$/

function flushList(lines, items) {
  if (items.length) {
    lines.push({ type: 'list', items: [...items] })
    items.length = 0
  }
}

function flushPara(lines, parts) {
  const text = parts.join(' ').trim()
  if (text) lines.push({ type: 'para', text })
  parts.length = 0
}

/**
 * @param {string} description
 * @returns {{ title: string|null, lines: Array<{type:'list',items:string[]}|{type:'para',text:string}> }[]}
 */
export function parseJobDescriptionBlocks(description) {
  if (!description || typeof description !== 'string') return []

  const rawLines = description.replace(/\r\n/g, '\n').split('\n')
  const blocks = []
  let current = { title: null, lines: [] }
  const listItems = []
  const paraParts = []

  const pushBlock = () => {
    flushList(current.lines, listItems)
    flushPara(current.lines, paraParts)
    if (current.title || current.lines.length) {
      blocks.push(current)
    }
    current = { title: null, lines: [] }
  }

  for (const raw of rawLines) {
    const line = raw.trim()
    if (!line) {
      flushList(current.lines, listItems)
      flushPara(current.lines, paraParts)
      continue
    }

    const titleMatch = line.match(SECTION_TITLE_RE)
    if (titleMatch) {
      pushBlock()
      current.title = titleMatch[1].trim()
      continue
    }

    const bulletMatch = line.match(BULLET_RE)
    if (bulletMatch) {
      flushPara(current.lines, paraParts)
      listItems.push(bulletMatch[1].trim())
      continue
    }

    flushList(current.lines, listItems)
    paraParts.push(line)
  }

  pushBlock()
  return blocks
}

/**
 * Extract skills from a **Required Skills:** section (comma / bullet separated).
 * @param {string} description
 * @returns {string[]}
 */
export function extractRequiredSkillsFromDescription(description) {
  if (!description || typeof description !== 'string') return []

  const blocks = parseJobDescriptionBlocks(description)
  const skillsBlock = blocks.find((b) => {
    const t = (b.title || '').toLowerCase()
    return t === 'required skills' || t.includes('required skill')
  })
  if (!skillsBlock) return []

  const skills = []
  for (const line of skillsBlock.lines) {
    if (line.type === 'list' && Array.isArray(line.items)) {
      for (const item of line.items) {
        for (const part of String(item).split(/[,;|]/)) {
          const s = part.trim()
          if (s) skills.push(s)
        }
      }
    } else if (line.type === 'para' && line.text) {
      for (const part of line.text.split(/[,;|]/)) {
        const s = part.trim()
        if (s) skills.push(s)
      }
    }
  }
  return skills
}
