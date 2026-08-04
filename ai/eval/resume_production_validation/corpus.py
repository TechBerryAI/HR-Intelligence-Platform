"""Discover and classify resumes in the corpus folder."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_EXT = {'pdf', 'docx', 'png', 'jpg', 'jpeg', 'webp'}
SKIP_NAMES = {'organize_resumes.ps1', '_organize_log.txt'}
MAX_BYTES = 10 * 1024 * 1024


@dataclass
class CorpusItem:
    path: Path
    rel_name: str
    ext: str
    size: int
    supported: bool
    skip_reason: str | None = None
    case_id: str = ''

    def __post_init__(self):
        if not self.case_id:
            digest = hashlib.sha1(self.rel_name.encode('utf-8', errors='ignore')).hexdigest()[:12]
            stem = ''.join(c if c.isalnum() or c in '-_' else '_' for c in self.path.stem)[:40]
            self.case_id = f'{stem}_{digest}'


def classify_file(path: Path, root: Path) -> CorpusItem:
    try:
        rel = str(path.relative_to(root))
    except ValueError:
        rel = path.name
    name = path.name
    if name in SKIP_NAMES or name.startswith('.'):
        return CorpusItem(path, rel, '', path.stat().st_size if path.exists() else 0, False, 'meta')

    ext = path.suffix.lower().lstrip('.')
    try:
        size = path.stat().st_size
    except OSError as exc:
        return CorpusItem(path, rel, ext, 0, False, f'stat_error:{exc}')

    if size == 0:
        return CorpusItem(path, rel, ext, size, False, 'empty_file')
    if ext not in SUPPORTED_EXT:
        return CorpusItem(path, rel, ext, size, False, f'unsupported_ext:{ext or "none"}')
    if size > MAX_BYTES:
        return CorpusItem(path, rel, ext, size, False, 'oversized')
    return CorpusItem(path, rel, ext, size, True, None)


def discover_corpus(corpus_dir: Path) -> tuple[list[CorpusItem], list[CorpusItem]]:
    root = corpus_dir.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f'Corpus not found: {root}')

    supported: list[CorpusItem] = []
    unsupported: list[CorpusItem] = []
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        item = classify_file(path, root)
        if item.skip_reason == 'meta':
            continue
        if item.supported:
            supported.append(item)
        else:
            unsupported.append(item)
    return supported, unsupported
