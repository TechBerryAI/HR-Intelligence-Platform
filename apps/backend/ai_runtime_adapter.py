"""Compatibility shim — see app package."""
import app.ai.adapter.runtime_adapter as _mod

globals().update({k: getattr(_mod, k) for k in dir(_mod) if not k.startswith('__')})
