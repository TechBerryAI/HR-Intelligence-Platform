"""Hardware-adaptive runtime profiles for OCR / layout / LLM concurrency."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_PROFILE_LOCK = threading.Lock()
_APPLIED = False

# Conservative output cap until the performance harness proves a lower limit is safe.
DEFAULT_MAX_TOKENS_RESUME_JD = 4096

_FORCED_PROFILES = frozenset({'gpu_high', 'gpu_mid', 'unknown', 'cpu'})


@dataclass(frozen=True)
class AIPerformanceProfile:
    """Version-controlled AI performance defaults for one hardware class."""

    name: str
    preferred_model: str
    ollama_max_concurrent: int
    bulk_workers: int
    ocr_dpi_start: int
    enable_doclayout: bool
    max_tokens_resume_jd: int = DEFAULT_MAX_TOKENS_RESUME_JD


PERFORMANCE_PROFILES: dict[str, AIPerformanceProfile] = {
    'gpu_high': AIPerformanceProfile(
        name='gpu_high',
        preferred_model='qwen2.5:14b-instruct',
        ollama_max_concurrent=3,
        bulk_workers=8,
        ocr_dpi_start=200,
        enable_doclayout=True,
    ),
    'gpu_mid': AIPerformanceProfile(
        name='gpu_mid',
        preferred_model='qwen2.5:7b-instruct',
        ollama_max_concurrent=2,
        bulk_workers=4,
        ocr_dpi_start=180,
        enable_doclayout=True,
    ),
    'unknown': AIPerformanceProfile(
        name='unknown',
        preferred_model='qwen2.5:7b-instruct',
        ollama_max_concurrent=1,
        bulk_workers=4,
        ocr_dpi_start=180,
        enable_doclayout=True,
    ),
    'cpu': AIPerformanceProfile(
        name='cpu',
        preferred_model='qwen2.5:3b-instruct',
        ollama_max_concurrent=1,
        bulk_workers=2,
        ocr_dpi_start=150,
        enable_doclayout=False,
    ),
}

# Pull-only fallback when hardware detection is unavailable (never written to .env).
SAFE_PULL_MODEL = PERFORMANCE_PROFILES['unknown'].preferred_model


@dataclass(frozen=True)
class HardwareProfile:
    name: str  # gpu_high | gpu_mid | unknown | cpu
    ollama_max_concurrent: int
    bulk_workers: int
    ocr_dpi_start: int
    enable_doclayout: bool
    preferred_model_hint: str
    vram_mb: int
    cpu_count: int
    max_tokens_resume_jd: int = DEFAULT_MAX_TOKENS_RESUME_JD
    detection_source: str = 'fallback'


def operator_ollama_model() -> str:
    """Non-empty OLLAMA_MODEL is an explicit operator pin. Blank/missing is unset."""
    return (os.getenv('OLLAMA_MODEL') or '').strip()


def ollama_model_is_explicit() -> bool:
    return bool(operator_ollama_model())


def _cpu_count() -> int:
    try:
        return max(1, os.cpu_count() or 1)
    except Exception:
        return 1


def _explicit_vram_mb() -> Optional[int]:
    override = os.getenv('HCIP_VRAM_MB')
    if override is None or not str(override).strip():
        return None
    try:
        return max(0, int(str(override).strip()))
    except ValueError:
        logger.warning('HCIP_VRAM_MB=%r is not an integer; ignoring', override)
        return None


def _nvidia_smi_vram_mb() -> Optional[int]:
    """Measured NVIDIA VRAM in MB, or None if nvidia-smi is unavailable."""
    try:
        out = subprocess.check_output(
            [
                'nvidia-smi',
                '--query-gpu=memory.total',
                '--format=csv,noheader,nounits',
            ],
            stderr=subprocess.DEVNULL,
            timeout=3,
            text=True,
        )
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        if not lines:
            return None
        return max(int(float(x)) for x in lines)
    except Exception:
        return None


def _gpu_present_unverified() -> bool:
    """True when a discrete GPU is visible but VRAM cannot be measured.

    Does not invent VRAM. Ignores generic /dev/dri (often Intel iGPU on CPU laptops).
    AMD/Apple/Intel VRAM is not measured here — operators should set
    HCIP_HARDWARE_PROFILE / HCIP_VRAM_MB.
    """
    for path in ('/dev/nvidia0', '/dev/nvidiactl', '/dev/dxg'):
        try:
            if Path(path).exists():
                return True
        except OSError:
            continue
    lspci = shutil.which('lspci')
    if not lspci:
        return False
    try:
        out = subprocess.check_output(
            [lspci, '-nn'],
            stderr=subprocess.DEVNULL,
            timeout=3,
            text=True,
        )
    except Exception:
        return False
    for line in out.splitlines():
        low = line.lower()
        if 'vga compatible' not in low and '3d controller' not in low:
            continue
        if 'nvidia' in low or 'amd' in low or 'advanced micro devices' in low:
            return True
    return False


def _detect_vram_mb() -> int:
    """Best-effort VRAM in MB. 0 means unknown / not measured (not a fake estimate)."""
    explicit = _explicit_vram_mb()
    if explicit is not None:
        return explicit
    measured = _nvidia_smi_vram_mb()
    if measured is not None:
        return measured
    return 0


def _select_profile_name(*, forced: str, vram_mb: int, explicit_vram: bool) -> tuple[str, str]:
    if forced in _FORCED_PROFILES:
        return forced, 'HCIP_HARDWARE_PROFILE'
    if vram_mb >= 20000:
        return 'gpu_high', 'nvidia-smi'
    if vram_mb >= 6000:
        return 'gpu_mid', 'nvidia-smi'
    if vram_mb > 0:
        return 'cpu', 'nvidia-smi-small'
    if explicit_vram:
        return 'cpu', 'HCIP_VRAM_MB'
    if _gpu_present_unverified():
        logger.warning(
            'GPU present but VRAM was not measured; using unknown/mid-safe profile. '
            'Set HCIP_HARDWARE_PROFILE or HCIP_VRAM_MB for AMD/Apple/Intel or unreadable NVIDIA.'
        )
        return 'unknown', 'gpu-present-unverified'
    return 'cpu', 'conservative-fallback'


def _env_int(name: str, default: int, *, lo: int = 1, hi: int = 24) -> int:
    raw = (os.getenv(name) or '').strip()
    if not raw:
        return default
    try:
        return max(lo, min(hi, int(raw)))
    except ValueError:
        return default


@lru_cache(maxsize=1)
def detect_hardware_profile() -> HardwareProfile:
    """
    Select gpu_high / gpu_mid / unknown / cpu.

    Precedence:
      explicit OLLAMA_MODEL (model only)
      → HCIP_HARDWARE_PROFILE
      → HCIP_VRAM_MB / nvidia-smi
      → unverified GPU presence (unknown, not cpu)
      → conservative cpu fallback
    """
    forced = (os.getenv('HCIP_HARDWARE_PROFILE') or '').strip().lower()
    cpus = _cpu_count()
    explicit_vram = _explicit_vram_mb() is not None
    vram = _detect_vram_mb()
    name, source = _select_profile_name(forced=forced, vram_mb=vram, explicit_vram=explicit_vram)
    defaults = PERFORMANCE_PROFILES[name]

    operator_model = operator_ollama_model()
    preferred = operator_model or defaults.preferred_model

    cpu_doclayout = os.getenv('HCIP_ENABLE_DOCLAYOUT', '').lower() in ('1', 'true', 'yes')
    enable_doclayout = defaults.enable_doclayout if name != 'cpu' else cpu_doclayout

    profile = HardwareProfile(
        name=name,
        ollama_max_concurrent=_env_int(
            'OLLAMA_MAX_CONCURRENT', defaults.ollama_max_concurrent, lo=1, hi=8
        ),
        bulk_workers=_env_int('BULK_PARSE_MAX_WORKERS', defaults.bulk_workers, lo=1, hi=24),
        ocr_dpi_start=defaults.ocr_dpi_start,
        enable_doclayout=enable_doclayout,
        preferred_model_hint=preferred,
        vram_mb=vram,
        cpu_count=cpus,
        max_tokens_resume_jd=defaults.max_tokens_resume_jd,
        detection_source=source,
    )

    logger.info(
        'HCIP hardware profile=%s source=%s vram_mb=%s cpus=%s concurrent=%s model=%s',
        profile.name,
        profile.detection_source,
        profile.vram_mb,
        profile.cpu_count,
        profile.ollama_max_concurrent,
        profile.preferred_model_hint,
    )
    return profile


def apply_hardware_env(profile: Optional[HardwareProfile] = None) -> HardwareProfile:
    """
    Apply profile defaults into process env once (operator-set env always wins).
    Sets OLLAMA_MODEL from tier when unset/blank — adaptive model selection.
    Does not write .env files.
    """
    global _APPLIED
    profile = profile or detect_hardware_profile()
    with _PROFILE_LOCK:
        if not ollama_model_is_explicit():
            chosen = profile.preferred_model_hint
            if os.environ.get('OLLAMA_MODEL') != chosen:
                os.environ['OLLAMA_MODEL'] = chosen
                logger.info(
                    'HCIP adaptive OLLAMA_MODEL=%s (profile=%s source=%s)',
                    chosen,
                    profile.name,
                    profile.detection_source,
                )
        if _APPLIED:
            return profile
        if 'OLLAMA_MAX_CONCURRENT' not in os.environ:
            os.environ['OLLAMA_MAX_CONCURRENT'] = str(profile.ollama_max_concurrent)
        if 'BULK_PARSE_MAX_WORKERS' not in os.environ:
            os.environ['BULK_PARSE_MAX_WORKERS'] = str(profile.bulk_workers)
        if 'HCIP_OCR_DPI_START' not in os.environ:
            os.environ['HCIP_OCR_DPI_START'] = str(profile.ocr_dpi_start)
        if 'HCIP_ENABLE_DOCLAYOUT' not in os.environ:
            os.environ['HCIP_ENABLE_DOCLAYOUT'] = 'true' if profile.enable_doclayout else 'false'
        if 'RESUME_LAYOUT_ENABLED' not in os.environ:
            os.environ['RESUME_LAYOUT_ENABLED'] = (
                'true' if profile.enable_doclayout else 'false'
            )
        _APPLIED = True
    return profile


def reset_hardware_env_for_tests() -> None:
    """Test helper: allow apply_hardware_env to run again."""
    global _APPLIED
    with _PROFILE_LOCK:
        _APPLIED = False
        detect_hardware_profile.cache_clear()


def main() -> None:
    """Print the adaptive (or operator-pinned) model hint. Used by start.js pull."""
    skip = (os.getenv('HCIP_SKIP_DOTENV') or '').strip().lower() in ('1', 'true', 'yes')
    if not skip:
        try:
            from dotenv import load_dotenv

            env_path = Path(__file__).resolve().parents[4] / '.env'
            load_dotenv(env_path, override=False)
        except Exception:
            pass
    detect_hardware_profile.cache_clear()
    print(detect_hardware_profile().preferred_model_hint)


if __name__ == '__main__':
    main()
