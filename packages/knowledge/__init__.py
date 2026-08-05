"""Resolve knowledge base paths."""
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "ai" / "knowledge"


def resolve_knowledge(domain: str, filename: str) -> Path:
    return KNOWLEDGE_DIR / domain / filename
