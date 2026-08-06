"""Developer Mode feature flag — Admin performance tooling only when enabled."""
from __future__ import annotations

import os
from functools import lru_cache


def _parse_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@lru_cache(maxsize=1)
def is_developer_mode_enabled() -> bool:
    """
    True when DEVELOPER_MODE is set (env) or Flask config DEVELOPER_MODE is True.

    Cached for the process lifetime. Restart the app after changing the env var.
    """
    return _parse_bool(os.getenv("DEVELOPER_MODE"), default=False)


def developer_mode_max_sessions() -> int:
    try:
        return max(50, int(os.getenv("DEVELOPER_MODE_MAX_SESSIONS", "500")))
    except (TypeError, ValueError):
        return 500


def clear_developer_mode_cache() -> None:
    """Test helper — reset the cached flag."""
    is_developer_mode_enabled.cache_clear()
