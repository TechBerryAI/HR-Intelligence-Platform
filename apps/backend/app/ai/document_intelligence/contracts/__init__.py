"""Field contracts — every form field is traceable to exactly one source."""
from app.ai.document_intelligence.contracts.registry import (
    FieldContract,
    JD_FIELD_CONTRACTS,
    RESUME_FIELD_CONTRACTS,
    get_contract,
)

__all__ = [
    'FieldContract',
    'JD_FIELD_CONTRACTS',
    'RESUME_FIELD_CONTRACTS',
    'get_contract',
]
