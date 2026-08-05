"""Resolve ontology asset paths (contracts, schemas, toon)."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = REPO_ROOT / "ai"

CONTRACTS_DIR = AI_ROOT / "contracts"
SCHEMAS_DIR = AI_ROOT / "schemas"
TOON_DIR = AI_ROOT / "toon"


def resolve_contract(name: str) -> Path:
    return CONTRACTS_DIR / name


def resolve_schema(name: str) -> Path:
    return SCHEMAS_DIR / name


def resolve_toon_asset(*parts: str) -> Path:
    return TOON_DIR.joinpath(*parts)
