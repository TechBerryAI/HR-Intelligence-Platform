"""AI runtime path resolution shim."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = REPO_ROOT / "ai"
RUNTIME_DIR = AI_ROOT / "runtime"
DEFAULT_CONFIG = RUNTIME_DIR / "config" / "runtime.production.yaml"


def get_runtime_config_path() -> Path:
    return DEFAULT_CONFIG


def get_ai_root() -> Path:
    return AI_ROOT
