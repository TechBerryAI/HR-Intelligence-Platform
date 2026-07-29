"""Compatibility shim — use app.core.auth and app.api.middleware.auth."""
from app.core.auth import *  # noqa: F401, F403
from app.api.middleware.auth import *  # noqa: F401, F403
