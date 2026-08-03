"""Hardware-adaptive runtime profiles for OCR / layout / LLM concurrency."""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

_PROFILE_LOCK = threading.Lock()
_APPLIED = False


@dataclass(frozen=True)
class HardwareProfile:
    name: str  # gpu_high | gpu_mid | cpu
    ollama_max_concurrent: int
    bulk_workers: int
    ocr_dpi_start: int
    enable_doclayout: bool
    preferred_model_hint: str
    vram_mb: int
    cpu_count: int


def _cpu_count() -> int:
    try:
        return max(1, os.cpu_count() or 1)
    except Exception:
        return 1


def _detect_vram_mb() -> int:
    """Best-effort nvidia-smi VRAM detection; 0 means CPU-only / unknown."""
    override = os.getenv('HCIP_VRAM_MB')
    if override is not None:
        try:
            return max(0, int(override))
        except ValueError:
            pass
    try:
        import subprocess

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
            return 0
        return max(int(float(x)) for x in lines)
    except Exception:
        return 0


@lru_cache(maxsize=1)
def detect_hardware_profile() -> HardwareProfile:
    """
    Select gpu_high (≈4090 / ≥20GB), gpu_mid (≈3060 / 6–20GB), or cpu.
    Operator env HCIP_HARDWARE_PROFILE overrides auto-detect.
    """
    forced = (os.getenv('HCIP_HARDWARE_PROFILE') or '').strip().lower()
    cpus = _cpu_count()
    vram = _detect_vram_mb()

    if forced in ('gpu_high', 'gpu_mid', 'cpu'):
        name = forced
    elif vram >= 20000:
        name = 'gpu_high'
    elif vram >= 6000:
        name = 'gpu_mid'
    else:
        name = 'cpu'

    if name == 'gpu_high':
        profile = HardwareProfile(
            name=name,
            ollama_max_concurrent=int(os.getenv('OLLAMA_MAX_CONCURRENT', '3')),
            bulk_workers=int(os.getenv('BULK_PARSE_MAX_WORKERS', '8')),
            ocr_dpi_start=200,
            enable_doclayout=True,
            preferred_model_hint=os.getenv('OLLAMA_MODEL', 'qwen2.5:14b-instruct'),
            vram_mb=vram,
            cpu_count=cpus,
        )
    elif name == 'gpu_mid':
        profile = HardwareProfile(
            name=name,
            ollama_max_concurrent=int(os.getenv('OLLAMA_MAX_CONCURRENT', '2')),
            bulk_workers=int(os.getenv('BULK_PARSE_MAX_WORKERS', '4')),
            ocr_dpi_start=180,
            enable_doclayout=True,
            preferred_model_hint=os.getenv('OLLAMA_MODEL', 'qwen2.5:7b-instruct'),
            vram_mb=vram,
            cpu_count=cpus,
        )
    else:
        profile = HardwareProfile(
            name=name,
            ollama_max_concurrent=int(os.getenv('OLLAMA_MAX_CONCURRENT', '1')),
            bulk_workers=int(os.getenv('BULK_PARSE_MAX_WORKERS', '2')),
            ocr_dpi_start=150,
            enable_doclayout=os.getenv('HCIP_ENABLE_DOCLAYOUT', 'false').lower()
            in ('1', 'true', 'yes'),
            preferred_model_hint=os.getenv('OLLAMA_MODEL', 'qwen2.5:3b-instruct'),
            vram_mb=vram,
            cpu_count=cpus,
        )

    logger.info(
        'HCIP hardware profile=%s vram_mb=%s cpus=%s concurrent=%s',
        profile.name,
        profile.vram_mb,
        profile.cpu_count,
        profile.ollama_max_concurrent,
    )
    return profile


def apply_hardware_env(profile: Optional[HardwareProfile] = None) -> HardwareProfile:
    """
    Apply profile defaults into process env once (operator-set env always wins).
    Safe to call from pipeline entry.
    """
    global _APPLIED
    profile = profile or detect_hardware_profile()
    with _PROFILE_LOCK:
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
        _APPLIED = True
    return profile
