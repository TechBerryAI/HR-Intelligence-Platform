"""
LLM API Key Manager: multi-key rotation, per-service round-robin, cooldown on failure.
Production-ready: no keys in logs; thread-safe; extensible.
"""
import os
import time
import threading
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Env: HRMS_API_KEY_1 .. HRMS_API_KEY_9, then XAI_API_KEY as fallback
KEY_ENV_PREFIX = "HRMS_API_KEY_"
KEY_ENV_FALLBACK = "XAI_API_KEY"
MAX_NUMERIC_KEYS = 9

COOLDOWN_SECONDS = int(os.getenv("LLM_KEY_COOLDOWN_SECONDS", "90"))
MAX_KEYS_TO_TRY = None  # None = try all keys once per request


def _load_keys() -> list[tuple[int, str]]:
    """Load keys from env. Returns list of (slot_id, secret). Never log secret."""
    out: list[tuple[int, str]] = []
    for i in range(1, MAX_NUMERIC_KEYS + 1):
        key = os.getenv(f"{KEY_ENV_PREFIX}{i}", "").strip()
        if key:
            out.append((i - 1, key))
    fallback = os.getenv(KEY_ENV_FALLBACK, "").strip()
    if fallback:
        out.append((len(out), fallback))
    return out


class KeyRegistry:
    """Holds loaded API keys. Opaque slot IDs only in logs."""

    def __init__(self) -> None:
        self._keys: list[tuple[int, str]] = _load_keys()
        if not self._keys:
            logger.warning("No LLM API keys found in env (%s1..%s or %s)", KEY_ENV_PREFIX, str(MAX_NUMERIC_KEYS), KEY_ENV_FALLBACK)

    @property
    def count(self) -> int:
        return len(self._keys)

    def get_key_at_index(self, index: int) -> Optional[tuple[int, str]]:
        if not self._keys:
            return None
        idx = index % len(self._keys)
        return self._keys[idx]


class KeyManager:
    """
    Per-service round-robin key selection with cooldown on 429/5xx/timeout.
    Thread-safe; minimal lock scope.
    """

    _instance: Optional["KeyManager"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._registry = KeyRegistry()
        self._service_index: dict[str, int] = {}
        self._cooldown_until: dict[int, float] = {}
        self._cooldown_lock = threading.Lock()
        self._metrics: dict[int, dict[str, int | float]] = {}

    @classmethod
    def get_instance(cls) -> "KeyManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get_key_for_service(self, service_id: str) -> Optional[tuple[int, str]]:
        """
        Returns (slot_id, secret) for the next key in round-robin for this service.
        Skips keys in cooldown; if all in cooldown, returns the one with earliest expiry.
        """
        if self._registry.count == 0:
            return None
        with self._cooldown_lock:
            start_index = self._service_index.get(service_id, 0)
            n = self._registry.count
            best: Optional[tuple[int, str]] = None
            best_expiry: Optional[float] = None
            now = time.monotonic()
            for offset in range(n):
                idx = (start_index + offset) % n
                slot_id, secret = self._registry.get_key_at_index(idx)
                if slot_id is None:
                    continue
                expiry = self._cooldown_until.get(slot_id, 0.0)
                if expiry <= now:
                    self._service_index[service_id] = (start_index + offset + 1) % n
                    logger.debug("LLM key slot=%s service=%s", slot_id, service_id)
                    return (slot_id, secret)
                if best_expiry is None or expiry < best_expiry:
                    best_expiry = expiry
                    best = (slot_id, secret)
            if best is not None:
                logger.warning("All keys in cooldown for service=%s; using slot with earliest expiry", service_id)
                return best
            return self._registry.get_key_at_index(start_index % n)

    def report_result(
        self,
        slot_id: int,
        success: bool,
        status_code: Optional[int] = None,
        latency_ms: float = 0.0,
    ) -> None:
        """Record result and put key in cooldown on 429/5xx/timeout."""
        with self._cooldown_lock:
            if slot_id not in self._metrics:
                self._metrics[slot_id] = {"requests": 0, "successes": 0, "failures": 0, "rate_limits": 0}
            self._metrics[slot_id]["requests"] += 1
            if success:
                self._metrics[slot_id]["successes"] += 1
            else:
                self._metrics[slot_id]["failures"] += 1
            if status_code == 429:
                self._metrics[slot_id]["rate_limits"] += 1
            if not success and (
                status_code == 429 or status_code is None or (status_code is not None and 500 <= status_code < 600)
            ):
                self._cooldown_until[slot_id] = time.monotonic() + COOLDOWN_SECONDS
                logger.info(
                    "LLM key slot=%s cooldown until %s s (status=%s)",
                    slot_id,
                    COOLDOWN_SECONDS,
                    status_code if status_code is not None else "timeout",
                )
        if success:
            logger.debug("LLM key slot=%s success latency_ms=%.0f", slot_id, latency_ms)
        else:
            logger.debug("LLM key slot=%s failure status=%s", slot_id, status_code)

    def get_metrics(self) -> dict:
        """Return usage metrics (no secrets). For observability."""
        with self._cooldown_lock:
            return {
                "cooldown_seconds": COOLDOWN_SECONDS,
                "key_count": self._registry.count,
                "slots": dict(self._metrics),
            }


def get_key_for_service(service_id: str) -> Optional[tuple[int, str]]:
    """Convenience: get (slot_id, secret) for the given service."""
    return KeyManager.get_instance().get_key_for_service(service_id)


def report_result(
    slot_id: int,
    success: bool,
    status_code: Optional[int] = None,
    latency_ms: float = 0.0,
) -> None:
    """Convenience: report result for a key slot."""
    KeyManager.get_instance().report_result(slot_id, success, status_code, latency_ms)
