"""Bullet / list-item preservation for resume parsing.

Schema string fields join items with newlines so boundaries survive Form DTO.
"""
from __future__ import annotations

import re

# Leading markers. Hyphen bullets require start-of-line + space (not "well-known").
BULLET_PREFIX_RE = re.compile(
    r'^(?:'
    r'[•●○▪■□◦‣▸►→✓✔◆◇❖❖➢]\s*'
    r'|\*\s+'
    r'|[-–—]\s+'
    r'|\d{1,2}[.)]\s+'
    r'|\([a-zA-Z]\)\s+'
    r'|[a-zA-Z][.)]\s+'
    r')'
)

_INLINE_BULLET_RE = re.compile(
    r'(?<=\S)\s+([•●○▪■◦‣▸►→✓✔◆◇➢])\s+'
)


def is_bullet_line(line: str) -> bool:
    s = (line or '').strip()
    if not s:
        return False
    return bool(BULLET_PREFIX_RE.match(s))


def strip_bullet_prefix(line: str) -> str:
    s = (line or '').strip()
    return BULLET_PREFIX_RE.sub('', s, count=1).strip()


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
        if not s:
            if buf:
                items.append(buf.strip())
                buf = ''
            continue
        if is_bullet_line(s) or re.match(r'^\d{1,2}[.)]\s+', s):
            if buf:
                items.append(buf.strip())
            buf = strip_bullet_prefix(s)
        elif buf and (s[:1].islower() or s[:1] in ',;'):
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
    if _DUTY_ITEM_START.match(strip_bullet_prefix(s)):
        return True
    if _LABELED_ITEM.match(s):
        return True
    return False


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
        if (
            indent >= 2
            and not is_bullet_line(body)
            and looks_like_list_item(body)
        ):
            out.append(f'• {strip_bullet_prefix(body)}')
        else:
            out.append(body)
    return '\n'.join(out)


def is_wrap_continuation(prev: str, nxt: str) -> bool:
    """True when nxt is a wrapped tail of prev, not a new list item."""
    p = (prev or '').rstrip()
    n = (nxt or '').strip()
    if not p or not n:
        return False
    if n[:1].islower() or n[:1] in ',;':
        return True
    if looks_like_list_item(n) or is_bullet_line(n):
        return False
    if p.endswith(('-', '–', '—', ',')):
        return True
    if not re.search(r'[.!?]$', p) and n[:1].islower():
        return True
    return False


def join_duty_lines(lines: list[str], *, mark_bullets: bool = True) -> str:
    """Keep list items on separate lines; join wrapped continuations with a space.

    When several items are present, prefix each with '• ' so Form DTO strings
    keep visible boundaries even if the PDF dropped the original glyph.
    """
    items: list[str] = []
    for ln in lines or []:
        s = (ln or '').strip()
        if not s:
            continue
        body = strip_bullet_prefix(s) if is_bullet_line(s) else s
        if items and is_wrap_continuation(items[-1], body):
            items[-1] = f'{items[-1].rstrip()} {body}'.strip()
            continue
        items.append(body)
    cleaned = [i.strip() for i in items if i and i.strip()]
    if mark_bullets and len(cleaned) >= 2:
        return '\n'.join(
            i if i.lstrip().startswith(('•', '●', '-', '*')) else f'• {i}'
            for i in cleaned
        )
    return '\n'.join(cleaned)
