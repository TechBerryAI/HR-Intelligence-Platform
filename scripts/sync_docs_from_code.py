#!/usr/bin/env python3
"""
Regenerate machine-readable inventories inside HCIP docs from the live codebase.

Updates marked regions in:
  - docs/07-API.md   (Flask routes)
  - docs/08-Database.md (schema_pg file list)

Usage (from repo root):
  python scripts/sync_docs_from_code.py

Safe to run repeatedly. Does not invent product narrative.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
DOCS = ROOT / "docs"

ROUTE_DECORATOR = re.compile(
    r"@(?P<bp>\w+)\.(?:route|get|post|put|patch|delete)\(\s*['\"](?P<path>[^'\"]+)['\"]"
    r"(?:\s*,\s*methods\s*=\s*\[(?P<methods>[^\]]+)\])?",
    re.IGNORECASE,
)
METHOD_ONLY = re.compile(
    r"@(?P<bp>\w+)\.(?P<method>get|post|put|patch|delete)\(\s*['\"](?P<path>[^'\"]+)['\"]",
    re.IGNORECASE,
)
REGISTER = re.compile(
    r"app\.register_blueprint\(\s*(?P<bp>\w+)\s*,\s*url_prefix\s*=\s*['\"](?P<prefix>[^'\"]+)['\"]"
)

BEGIN_API = "<!-- BEGIN:GENERATED-API-ROUTES -->"
END_API = "<!-- END:GENERATED-API-ROUTES -->"
BEGIN_SCHEMA = "<!-- BEGIN:GENERATED-SCHEMA-FILES -->"
END_SCHEMA = "<!-- END:GENERATED-SCHEMA-FILES -->"


def replace_region(text: str, begin: str, end: str, body: str) -> str:
    if begin not in text or end not in text:
        raise SystemExit(f"Missing markers {begin!r} .. {end!r} in target doc")
    pre, rest = text.split(begin, 1)
    _, post = rest.split(end, 1)
    return f"{pre}{begin}\n{body.rstrip()}\n{end}{post}"


def discover_blueprints() -> dict[str, str]:
    create_app = (BACKEND / "app" / "bootstrap" / "create_app.py").read_text(encoding="utf-8")
    return {m.group("bp"): m.group("prefix") for m in REGISTER.finditer(create_app)}


def normalize_methods(raw: str | None, fallback: str | None) -> str:
    if fallback:
        return fallback.upper()
    if not raw:
        return "GET"  # Flask default for .route without methods
    parts = re.findall(r"['\"](\w+)['\"]", raw)
    return ", ".join(p.upper() for p in parts) if parts else "GET"


def collect_routes(bp_prefix: dict[str, str]) -> list[tuple[str, str, str, str]]:
    """Return rows: method, full_path, blueprint, relative_file."""
    rows: list[tuple[str, str, str, str]] = []
    domains = BACKEND / "app" / "domains"
    for py in domains.rglob("*.py"):
        if py.name.startswith("__"):
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        rel = py.relative_to(BACKEND).as_posix()
        for m in ROUTE_DECORATOR.finditer(text):
            bp = m.group("bp")
            if bp not in bp_prefix:
                continue
            path = m.group("path")
            methods = normalize_methods(m.group("methods"), None)
            # If decorator was .get/.post without methods=, ROUTE_DECORATOR may still match via .route only.
            # Handle method-style decorators separately below.
            if ".route(" in m.group(0) or "methods" in (m.group(0) or ""):
                full = _join(bp_prefix[bp], path)
                for method in [x.strip() for x in methods.split(",")]:
                    rows.append((method, full, bp, rel))
        for m in METHOD_ONLY.finditer(text):
            bp = m.group("bp")
            if bp not in bp_prefix:
                continue
            # Skip if this line is also a .route( with methods — METHOD_ONLY also matches get/post helpers
            if ".route(" in m.group(0):
                continue
            method = m.group("method").upper()
            full = _join(bp_prefix[bp], path := m.group("path"))
            rows.append((method, full, bp, rel))

    # Dedupe
    seen = set()
    unique = []
    for row in rows:
        if row in seen:
            continue
        seen.add(row)
        unique.append(row)
    unique.sort(key=lambda r: (r[1], r[0], r[2]))
    return unique


def _join(prefix: str, path: str) -> str:
    prefix = prefix.rstrip("/") or ""
    if not path.startswith("/"):
        path = "/" + path
    if path == "/":
        return prefix + "/" if prefix else "/"
    return f"{prefix}{path}"


def render_api_markdown(rows: list[tuple[str, str, str, str]], bp_prefix: dict[str, str]) -> str:
    today = date.today().isoformat()
    lines = [
        f"_Auto-generated on {today} by `scripts/sync_docs_from_code.py`. Do not hand-edit this block._",
        "",
        "### Registered blueprints",
        "",
        "| Blueprint | URL prefix |",
        "|-----------|------------|",
    ]
    for bp, prefix in sorted(bp_prefix.items(), key=lambda x: x[1]):
        lines.append(f"| `{bp}` | `{prefix}` |")
    lines.extend(["", "### Discovered routes", "", "| Method | Path | Blueprint | Source |", "|--------|------|-----------|--------|"])
    for method, full, bp, rel in rows:
        lines.append(f"| `{method}` | `{full}` | `{bp}` | `{rel}` |")
    lines.append("")
    lines.append(
        f"_Route count: {len(rows)}. If a route is missing, ensure it uses "
        f"`@blueprint.route` / `.get` / `.post` and the blueprint is registered in `create_app.py`._"
    )
    return "\n".join(lines)


def render_schema_markdown() -> str:
    today = date.today().isoformat()
    schema_dir = BACKEND / "schema_pg"
    files = sorted(schema_dir.glob("*.sql"))
    lines = [
        f"_Auto-generated on {today} by `scripts/sync_docs_from_code.py`. Do not hand-edit this block._",
        "",
        "| File | Purpose (from filename / header) |",
        "|------|-----------------------------------|",
    ]
    for f in files:
        purpose = f.stem
        try:
            first = f.read_text(encoding="utf-8", errors="ignore").splitlines()[:5]
            comment = next((ln[2:].strip() for ln in first if ln.strip().startswith("--")), "")
            if comment:
                purpose = comment
        except OSError:
            pass
        lines.append(f"| `apps/backend/schema_pg/{f.name}` | {purpose} |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    bp_prefix = discover_blueprints()
    rows = collect_routes(bp_prefix)

    api_path = DOCS / "07-API.md"
    api_text = api_path.read_text(encoding="utf-8")
    api_text = replace_region(api_text, BEGIN_API, END_API, render_api_markdown(rows, bp_prefix))
    api_path.write_text(api_text, encoding="utf-8")
    print(f"updated {api_path.relative_to(ROOT)} ({len(rows)} routes, {len(bp_prefix)} blueprints)")

    db_path = DOCS / "08-Database.md"
    db_text = db_path.read_text(encoding="utf-8")
    db_text = replace_region(db_text, BEGIN_SCHEMA, END_SCHEMA, render_schema_markdown())
    db_path.write_text(db_text, encoding="utf-8")
    print(f"updated {db_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
