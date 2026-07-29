"""Compatibility shim — see app package."""
import app.domains.recruitment.services.ats_service as _mod

globals().update({k: getattr(_mod, k) for k in dir(_mod) if not k.startswith('__')})
