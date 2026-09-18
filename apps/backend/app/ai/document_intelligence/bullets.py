"""Bullet / list-item preservation for resume parsing.

Schema string fields join items with newlines so boundaries survive Form DTO.
"""
from __future__ import annotations

import re

# Leading markers. Hyphen bullets require start-of-line + space (not "well-known").
# Include middle-dot and Word/Wingdings leftovers so PDF glyphs are not dropped.
_BULLET_GLYPH = (
    r'[•●○▪■□◦‣▸►→✓✔◆◇❖➢·\uf0b7\u2022\u25cf\u25e6]'
)
BULLET_PREFIX_RE = re.compile(
    r'^(?:'
    rf'{_BULLET_GLYPH}\s*'
    r'|\*\s+'
    r'|[-–—]\s+'
    r'|\d{1,2}[.)]\s+'
    r'|\([a-zA-Z]\)\s+'
    r'|[a-zA-Z][.)]\s+'
    r')'
)

_INLINE_BULLET_RE = re.compile(
    rf'(?<=\S)\s+({_BULLET_GLYPH})\s+'
)
_GLYPH_ONLY_RE = re.compile(rf'^(?:{_BULLET_GLYPH}\s*)+$')


def is_bullet_line(line: str) -> bool:
    s = (line or '').strip()
    if not s:
        return False
    return bool(BULLET_PREFIX_RE.match(s))


def strip_bullet_prefix(line: str) -> str:
    s = (line or '').strip()
    prev = None
    while s and prev != s:
        prev = s
        nxt = BULLET_PREFIX_RE.sub('', s, count=1).strip()
        if nxt == s:
            break
        s = nxt
    return s


def is_glyph_crumb(line: str) -> bool:
    """True for empty / glyph-only lines (PDF bullet + restored marker)."""
    s = (line or '').strip()
    if not s:
        return True
    body = strip_bullet_prefix(s)
    if not body:
        return True
    return bool(_GLYPH_ONLY_RE.match(body) or _GLYPH_ONLY_RE.match(s))


def split_inline_bullets(text: str) -> str:
    """Put mid-line bullet glyphs onto their own lines. Does not split hyphens in prose."""
    if not text:
        return ''
    out = _INLINE_BULLET_RE.sub(r'\n\1 ', text)
    return out


def split_bullet_items(text: str) -> list[str]:
    """Return logical list items from a block of duties / achievements."""
    raw = split_inline_bullets(text or '')
    items: list[str] = []
    buf = ''
    for ln in raw.splitlines():
        s = ln.strip()
        if not s or is_glyph_crumb(s):
            if buf:
                items.append(buf.strip())
                buf = ''
            continue
        if is_bullet_line(s) or re.match(r'^\d{1,2}[.)]\s+', s):
            body = strip_bullet_prefix(s)
            if buf and is_wrap_continuation(buf, body, nxt_had_bullet=True):
                buf = f'{buf} {body}'.strip()
            else:
                if buf:
                    items.append(buf.strip())
                buf = body
        elif buf and is_wrap_continuation(buf, s, nxt_had_bullet=False):
            buf = f'{buf} {s}'.strip()
        elif buf:
            items.append(buf.strip())
            buf = s
        else:
            buf = s
    if buf:
        items.append(buf.strip())
    return [i for i in items if i]


_DUTY_ITEM_START = re.compile(
    r'(?i)^(?:'
    r'managed|executed|coordinated|collaborated|utilized|maintained|'
    r'facilitated|developed|designed|created|built|led|drove|implemented|'
    r'optimized|improved|increased|worked|assisted|supported|handled|'
    r'performed|conducted|analyzed|monitored|delivered|owned|spearheaded|'
    r'researched|prepared|observed|catalogued|reviewed|refactored|'
    r'designing|developing|implementing|creating|building|improving|'
    r'reducing|leveraging|maintaining|supporting|leading|writing|'
    r'oversaw|directed|administered|completed|provided|ensured|deployed|'
    r'configured|installing|administer|'
    r'responsible\s+for'
    r')\b'
)
_LABELED_ITEM = re.compile(
    r'(?i)^[A-Z][A-Za-z /&]{1,40}:\s+\S'
)


def looks_like_list_item(line: str) -> bool:
    s = (line or '').strip()
    if not s:
        return False
    if is_bullet_line(s):
        return True
    body = strip_bullet_prefix(s)
    if _DUTY_ITEM_START.match(body):
        return True
    if _LABELED_ITEM.match(s) or _LABELED_ITEM.match(body):
        return True
    return False


def has_list_evidence(lines: list[str] | tuple[str, ...] | None) -> bool:
    """True when the block is a list (glyphs, numbering, or 2+ duty/labeled items)."""
    n_bullet = 0
    n_duty = 0
    for ln in lines or []:
        s = (ln or '').strip()
        if not s or is_glyph_crumb(s):
            continue
        if is_bullet_line(s) or re.match(r'^\d{1,2}[.)]\s+', s):
            n_bullet += 1
            continue
        if looks_like_list_item(s):
            n_duty += 1
    return n_bullet >= 1 or n_duty >= 2


def restore_inferred_list_markers(text: str) -> str:
    """If PDF dropped the glyph but indent + list shape remain, restore a bullet.

    Does not convert ordinary paragraphs: requires indent and list-item evidence.
    """
    if not text:
        return ''
    out: list[str] = []
    for raw in text.splitlines():
        if not raw.strip():
            out.append('')
            continue
        indent = len(raw) - len(raw.lstrip(' \t'))
        body = raw.strip()
        if is_glyph_crumb(body):
            continue
        if (
            indent >= 2
            and not is_bullet_line(body)
            and looks_like_list_item(body)
        ):
            out.append(f'• {strip_bullet_prefix(body)}')
        else:
            out.append(body)
    return '\n'.join(out)


_INCOMPLETE_TAIL = re.compile(
    r'(?i)(?:'
    r'[-–—,;/&]'
    r'|\b(?:with|of|in|and|the|for|to|a|an|as|by|on|from|into|via|'
    r'using|including|such\s+as|or|at|over|under|per|vs\.?|vs)\s*'
    r')$'
)


def is_new_list_item(line: str) -> bool:
    """True when the line starts a new duty / labeled item (not a wrap tail)."""
    s = (line or '').strip()
    if not s or is_glyph_crumb(s):
        return False
    body = strip_bullet_prefix(s)
    if _DUTY_ITEM_START.match(body):
        return True
    if _LABELED_ITEM.match(s) or _LABELED_ITEM.match(body):
        return True
    return False


def is_wrap_continuation(prev: str, nxt: str, *, nxt_had_bullet: bool = False) -> bool:
    """True when nxt is a wrapped tail of prev, not a new list item.

    Uppercase wrap tails after an unfinished line stay on the same item.
    A real new bullet (duty verb / labeled Key:) is never joined.
    """
    p = (prev or '').rstrip()
    n = (nxt or '').strip()
    if not p or not n:
        return False
    if is_new_list_item(n):
        return False
    if n[:1].islower() or n[:1] in ',;':
        return True
    if p.endswith(('-', '–', '—', ',', '/', '&')):
        return True
    if _INCOMPLETE_TAIL.search(p):
        return True
    # Unfinished sentence + not a duty/label → same item when the next line
    # has no list marker. A leftover glyph is a wrap only when prev is clearly
    # unfinished (handled above); otherwise "1. … / 2. …" stay separate.
    if not re.search(r'[.!?]$', p) and not nxt_had_bullet:
        return True
    return False


def join_duty_lines(lines: list[str], *, mark_bullets: bool = True) -> str:
    """Keep list items on separate lines; join wrapped continuations with a space.

    When the block is a list and several items are present, prefix each with '• '
    so Form DTO strings keep visible boundaries even if the PDF dropped the glyph.
    Ordinary paragraphs (no list evidence) stay one paragraph — wrap lines are
    not turned into fake bullets.
    """
    raw = [ln for ln in (lines or []) if not is_glyph_crumb(ln)]
    listed = has_list_evidence(raw)
    items: list[str] = []
    for ln in raw:
        s = (ln or '').strip()
        if not s:
            continue
        had_bullet = is_bullet_line(s)
        body = strip_bullet_prefix(s) if had_bullet else s
        if not body:
            continue
        if items and is_wrap_continuation(
            items[-1], body, nxt_had_bullet=had_bullet
        ):
            items[-1] = f'{items[-1].rstrip()} {body}'.strip()
            continue
        items.append(body)
    cleaned = [i.strip() for i in items if i and i.strip()]
    if not cleaned:
        return ''
    if not listed:
        return ' '.join(cleaned)
    if mark_bullets and len(cleaned) >= 2:
        return '\n'.join(
            i if i.lstrip().startswith(('•', '●', '-', '*')) else f'• {i}'
            for i in cleaned
        )
    return '\n'.join(cleaned)
