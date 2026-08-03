"""Form mapping package — explicit one-source mappings only."""
from app.ai.document_intelligence.mapping.jd_form import JD_FORM_MAPPING_GRAPH, map_job_to_form
from app.ai.document_intelligence.mapping.resume_form import (
    RESUME_FORM_MAPPING_GRAPH,
    map_candidate_to_form,
)

__all__ = [
    'JD_FORM_MAPPING_GRAPH',
    'RESUME_FORM_MAPPING_GRAPH',
    'map_candidate_to_form',
    'map_job_to_form',
]
