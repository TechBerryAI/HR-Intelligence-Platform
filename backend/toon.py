"""
TOON (Token-Oriented Object Notation) – exclusive structured format for the ATS pipeline.
Serialization/deserialization for Resume TOON, JD TOON, and ATS Result TOON.
No internal JSON for these payloads; JSON only at HTTP boundary via single adapter.
Format: one entry per line; key path with dots; pipe for scalar lists; indexed paths for object arrays.
"""
from __future__ import annotations

from typing import Any, Dict, List


def toon_dumps(obj: Dict[str, Any]) -> str:
    """Serialize a dict (Resume TOON, JD TOON, or ATS Result TOON) to TOON text."""
    if not isinstance(obj, dict):
        raise TypeError("toon_dumps requires a dict")
    lines: List[str] = []

    def enc_val(v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, str):
            if "\n" in v or "|" in v or "\\" in v or v.strip() != v or not v or v in ("true", "false", "null"):
                return '"' + v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
            return v
        return str(v)

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
                        for i, item in enumerate(v):
                            walk(f"{key}.{i}", item)
                    else:
                        lines.append(f"{key}: " + "|".join(enc_val(x) for x in v))
                else:
                    lines.append(f"{key}: {enc_val(v)}")
        else:
            lines.append(f"{prefix}: {enc_val(o)}")

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
    """Parse TOON text to a dict."""
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
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        colon = line.find(":")
        if colon < 0:
            continue
        path = line[:colon].strip()
        value_part = line[colon + 1 :].strip()

        if path.endswith("[0]") and not value_part:
            _set_by_path(root, path, None)
            continue
        value = _parse_val(value_part)
        if isinstance(value, str) and "|" in value_part and value_part.strip() and not (value_part.startswith('"') and value_part.endswith('"')):
            value = [_parse_val(x.strip()) for x in value_part.split("|")]
        _set_by_path(root, path, value)

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
