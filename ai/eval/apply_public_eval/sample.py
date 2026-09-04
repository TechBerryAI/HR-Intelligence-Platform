"""Diverse corpus sampling for Apply evaluation. Layout-class stems are eval-only."""
from __future__ import annotations

import os
from pathlib import Path

SUPPORTED = {'.pdf', '.docx'}
DEFAULT_CORPUS = Path(os.environ.get(
    'RESUME_CORPUS_DIR',
    r'C:\Users\DELL\Downloads\resume testing',
))
# Layout classes used in prior Apply validation — filenames only, never parser rules.
_LAYOUT_CLASS_PREFIXES = (
    'Adil Rashid Khan RESUME',
    'Naukri_Rakeshdilipkarpe',
    'Naukri_RajendraNimbalkar',
    'Naukri_RakshaJaiswal',
)


def list_corpus_files(corpus_dir: Path | None = None) -> list[Path]:
    root = Path(corpus_dir or DEFAULT_CORPUS)
    if not root.is_dir():
        return []
    return sorted(
        p for p in root.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED
    )


def select_diverse(files: list[Path], n: int = 16) -> list[Path]:
    """Pick 10–20 files: layout-class fixtures first, then stride-sampled PDF/DOCX."""
    n = max(10, min(20, int(n)))
    if not files:
        return []
    by_name = {p.name: p for p in files}
    chosen: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        if path.name in seen:
            return
        seen.add(path.name)
        chosen.append(path)

    for prefix in _LAYOUT_CLASS_PREFIXES:
        for p in files:
            if p.name.startswith(prefix):
                add(p)
                break

    pdfs = [p for p in files if p.suffix.lower() == '.pdf' and p.name not in seen]
    docs = [p for p in files if p.suffix.lower() == '.docx' and p.name not in seen]

    def stride(seq: list[Path], k: int) -> list[Path]:
        if k <= 0 or not seq:
            return []
        if len(seq) <= k:
            return list(seq)
        step = max(1, len(seq) // k)
        out = []
        i = 0
        while len(out) < k and i < len(seq) * 2:
            out.append(seq[(i * step) % len(seq)])
            i += 1
            # unique
            uniq = []
            seen_local = set()
            for x in out:
                if x.name not in seen_local:
                    seen_local.add(x.name)
                    uniq.append(x)
            out = uniq
        return out[:k]

    remaining = n - len(chosen)
    n_pdf = (remaining + 1) // 2
    n_docx = remaining - n_pdf
    for p in stride(pdfs, n_pdf):
        add(p)
    for p in stride(docs, n_docx):
        add(p)
    if len(chosen) < min(n, len(files)):
        for p in files:
            add(p)
            if len(chosen) >= min(n, len(files)):
                break
    return chosen[: min(n, len(files))]


def load_reference(path: Path, references_dir: Path | None = None) -> dict | None:
    """Optional expected Form DTO sidecar — never required."""
    stem = path.stem
    candidates = [
        path.with_suffix(path.suffix + '.expected.json'),
        path.with_name(stem + '.expected.json'),
    ]
    if references_dir:
        safe = ''.join(ch if ch.isalnum() or ch in '-_.' else '_' for ch in stem)[:80]
        candidates.append(Path(references_dir) / f'{safe}.json')
        candidates.append(Path(references_dir) / f'{path.name}.json')
    for cand in candidates:
        if cand.is_file():
            import json
            return json.loads(cand.read_text(encoding='utf-8'))
    return None
