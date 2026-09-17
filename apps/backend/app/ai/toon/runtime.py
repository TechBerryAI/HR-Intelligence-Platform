"""
TOON (Token-Oriented Object Notation) – exclusive structured format for the ATS pipeline.
Serialization/deserialization for Resume TOON, JD TOON, and ATS Result TOON.
No internal JSON for these payloads; JSON only at HTTP boundary via single adapter.

Format: one entry per line; key path with dots; pipe for scalar lists.

Object arrays use a tabular block that declares its columns once::

    education[2]{degree,institution,endMonth}:
      Bachelor of Science,"SM Shetty College, Mumbai",2014-04
      Higher Secondary,St. Xavier's College,2011-02

instead of repeating ``education.0.degree``-style paths on every field. On real
resume payloads that is ~16% fewer characters than the dotted form and ~12%
fewer than JSON; the dotted form was *larger* than JSON because a resume is
mostly object arrays.

A table needs every item to carry the same scalar keys. Mixed or nested arrays
fall back to dotted paths, so nothing is invented and the round trip stays
exact.

Documents written before the tabular form carry no ``#toon/v2`` banner and are
still read by the dotted-path branch below. The reader accepts both regardless
of the banner, so a stored document never has to be migrated.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

FORMAT_BANNER = "#toon/v2"


def _looks_numeric(s: str) -> bool:
    """True when the reader would turn this string back into an int/float.

    ``'2012'`` and ``'+919619463501'`` are strings on the way in; without
    quoting they come back as ``2012`` and ``919619463501``, and that second
    one has silently lost its ``+``. Quote them so the type survives.
    """
    try:
        float(s) if "." in s else int(s)
    except ValueError:
        return False
    return True


def _enc_val(v: Any) -> str:
    """Encode a scalar for ``key: value`` position."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        if (
            "\n" in v
            or "|" in v
            or "\\" in v
            or v.strip() != v
            or not v
            or v in ("true", "false", "null")
            or _looks_numeric(v)
        ):
            return (
                '"'
                + v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
                + '"'
            )
        return v
    return str(v)


def _enc_cell(v: Any) -> str:
    """Encode a scalar for a table cell, where ``,`` also terminates the value."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        # An empty cell already reads back as '', so it needs no quotes — and
        # blank cells are common (cgpa, institution), so this is worth doing.
        if not v:
            return ""
        if (
            "," in v
            or "\n" in v
            or '"' in v
            or "\\" in v
            or v.strip() != v
            or v in ("true", "false", "null")
            or _looks_numeric(v)
        ):
            return (
                '"'
                + v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
                + '"'
            )
        return v
    return str(v)


def _table_columns(items: Sequence[Any]) -> list[str] | None:
    """Column order for a tabular block, or ``None`` if these items need paths.

    Every item must be a dict carrying exactly the same keys, all scalar. A key
    missing from one row would come back as ``""`` rather than absent, so an
    uneven array is written as dotted paths instead of being padded.
    """
    if not items:
        return None
    first = items[0]
    if not isinstance(first, dict) or not first:
        return None
    cols = list(first.keys())
    col_set = set(cols)
    for item in items:
        if not isinstance(item, dict) or set(item.keys()) != col_set:
            return None
        for value in item.values():
            if isinstance(value, (dict, list)):
                return None
    return cols


def toon_dumps(obj: Dict[str, Any]) -> str:
    """Serialize a dict (Resume TOON, JD TOON, or ATS Result TOON) to TOON text."""
    if not isinstance(obj, dict):
        raise TypeError("toon_dumps requires a dict")
    lines: List[str] = [FORMAT_BANNER]

    def walk(prefix: str, o: Any) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                key = f"{prefix}.{k}" if prefix else k
                if v is None:
                    continue
                if isinstance(v, dict):
                    walk(key, v)
                elif isinstance(v, list):
                    if not v:
                        lines.append(f"{key}[0]:")
                    elif all(isinstance(x, dict) for x in v):
                        cols = _table_columns(v)
                        if cols is None:
                            for i, item in enumerate(v):
                                walk(f"{key}.{i}", item)
                        else:
                            lines.append(f"{key}[{len(v)}]{{{','.join(cols)}}}:")
                            for item in v:
                                lines.append(
                                    "  " + ",".join(_enc_cell(item[c]) for c in cols)
                                )
                    else:
                        # Explicit count: a one-element list is otherwise
                        # indistinguishable from a bare scalar on the way back.
                        lines.append(
                            f"{key}[{len(v)}]: " + "|".join(_enc_val(x) for x in v)
                        )
                else:
                    lines.append(f"{key}: {_enc_val(v)}")
        else:
            lines.append(f"{prefix}: {_enc_val(o)}")

    walk("", obj)
    return "\n".join(lines)


def _parse_val(s: str) -> Any:
    s = s.strip()
    if not s:
        return ""
    if s == "null":
        return None
    if s == "true":
        return True
    if s == "false":
        return False
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1].replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        return s


def _split_row(row: str) -> list[str]:
    """Split a table row on commas that sit outside a quoted cell."""
    cells: list[str] = []
    buf: list[str] = []
    in_quotes = False
    i = 0
    while i < len(row):
        ch = row[i]
        if in_quotes:
            if ch == "\\" and i + 1 < len(row):
                buf.append(ch)
                buf.append(row[i + 1])
                i += 2
                continue
            if ch == '"':
                in_quotes = False
            buf.append(ch)
        elif ch == '"':
            in_quotes = True
            buf.append(ch)
        elif ch == ",":
            cells.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    cells.append("".join(buf))
    return cells


def _parse_table_header(path: str) -> tuple[str, int, list[str]] | None:
    """``education[2]{degree,institution}`` -> ``('education', 2, [...])``."""
    if not path.endswith("}") or "[" not in path or "{" not in path:
        return None
    brace = path.find("{")
    bracket = path.find("[")
    if bracket > brace:
        return None
    key = path[:bracket]
    count_part = path[bracket + 1 : path.find("]", bracket)]
    cols_part = path[brace + 1 : -1]
    if not key or not count_part.isdigit():
        return None
    cols = [c.strip() for c in cols_part.split(",") if c.strip()]
    if not cols:
        return None
    return key, int(count_part), cols


def _parse_list_count(path: str) -> tuple[str, int] | None:
    """``skills[3]`` -> ``('skills', 3)``; ``None`` when there is no count."""
    if not path.endswith("]"):
        return None
    bracket = path.rfind("[")
    if bracket <= 0:
        return None
    count_part = path[bracket + 1 : -1]
    if not count_part.isdigit():
        return None
    return path[:bracket], int(count_part)


def _set_by_path(root: Dict[str, Any], path: str, value: Any) -> None:
    """Set value at path (dot-separated; numeric segments are list indices)."""
    parts = [p for p in path.split(".") if p]
    if not parts:
        return
    cur: Any = root
    i = 0
    while i < len(parts) - 1:
        seg = parts[i]
        nxt = parts[i + 1]
        if nxt.isdigit():
            idx = int(nxt)
            if isinstance(cur, dict) and seg not in cur:
                cur[seg] = []
            if isinstance(cur, dict):
                arr = cur[seg]
                if not isinstance(arr, list):
                    arr = []
                    cur[seg] = arr
                while len(arr) <= idx:
                    arr.append({})
                cur = arr[idx]
            i += 2
            continue
        if isinstance(cur, dict):
            if seg not in cur:
                cur[seg] = {}
            cur = cur[seg]
        i += 1
    last = parts[-1]
    if last.endswith("[0]"):
        last = last.replace("[0]", "").strip()
        if isinstance(cur, dict):
            cur[last] = []
    elif isinstance(cur, dict):
        cur[last] = value


def toon_loads(text: str) -> Dict[str, Any]:
    """Parse TOON text to a dict. Accepts tabular and dotted-path object arrays."""
    if not text or not text.strip():
        return {}
    text = text.strip()
    if text.startswith("```toon"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    root: Dict[str, Any] = {}
    # Rows of the table currently being read; reset by the next non-row line.
    table_key = ""
    table_cols: list[str] = []
    table_rows: list[dict] = []

    def flush_table() -> None:
        nonlocal table_key, table_cols, table_rows
        if table_key:
            _set_by_path(root, table_key, table_rows)
        table_key = ""
        table_cols = []
        table_rows = []

    for raw_line in text.split("\n"):
        if not raw_line.strip():
            continue
        if raw_line.strip() == FORMAT_BANNER:
            continue

        # A table row is indented and belongs to the header above it. Checked
        # before the colon rule, since a cell may itself contain a colon.
        if table_key and raw_line[:1] in (" ", "\t"):
            cells = _split_row(raw_line.strip())
            if len(cells) == len(table_cols):
                table_rows.append(
                    {c: _parse_val(cells[i]) for i, c in enumerate(table_cols)}
                )
                continue

        line = raw_line.strip()
        colon = line.find(":")
        if colon < 0:
            continue
        path = line[:colon].strip()
        value_part = line[colon + 1 :].strip()

        header = _parse_table_header(path) if not value_part else None
        if header is not None:
            flush_table()
            table_key, _count, table_cols = header
            continue

        flush_table()

        # ``key[N]`` marks a scalar list explicitly, so a one-element list does
        # not decay to a scalar. ``key[0]:`` (empty list) is the N == 0 case.
        counted = _parse_list_count(path)
        if counted is not None:
            bare_key, count = counted
            if count == 0 and not value_part:
                _set_by_path(root, f"{bare_key}[0]", None)
            else:
                _set_by_path(
                    root, bare_key, [_parse_val(x.strip()) for x in value_part.split("|")]
                )
            continue

        value = _parse_val(value_part)
        # Legacy documents wrote scalar lists as a bare pipe-joined value.
        if (
            isinstance(value, str)
            and "|" in value_part
            and value_part.strip()
            and not (value_part.startswith('"') and value_part.endswith('"'))
        ):
            value = [_parse_val(x.strip()) for x in value_part.split("|")]
        _set_by_path(root, path, value)

    flush_table()
    return root


def toon_loads_flex(text: str) -> Dict[str, Any]:
    """
    Parse TOON or legacy JSON. Use only at the boundary when reading
    stored content that may be historical JSON.
    """
    if not text or not text.strip():
        return {}
    text = text.strip()
    if text.startswith("{") and text.rstrip().endswith("}"):
        import json as _json

        try:
            return _json.loads(text)
        except _json.JSONDecodeError:
            pass
    return toon_loads(text)
