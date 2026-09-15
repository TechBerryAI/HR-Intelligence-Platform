"""Turn per-field misses into a ranked, actionable fix list.

A scorecard tells you *how good* the parser is. Triage tells you *what to fix
next*: failure modes ordered by how much benchmark score they would return.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .config import FIELD_BY_KEY

# Human-readable guidance per tag family. Keyed by suffix so section tags
# (education_low_fact_recall, experiences_low_fact_recall, ...) share an entry.
_GUIDANCE = {
    'not_extracted': 'Field never produced a value - check section detection and the '
                     'field extractor for this layout.',
    'wrong_value': 'A value was produced but it is the wrong one - check candidate '
                   'ranking / first-match bias in the extractor.',
    'invented': 'Gold is empty but the parser emitted a value - tighten validation so '
                'unrelated text cannot populate this field.',
    'low_fact_recall': 'Entities present in the resume are not reaching the form rows - '
                       'usually a section boundary or entry-splitting problem.',
    'spurious_rows': 'Rows were emitted that match nothing in gold - usually adjacent '
                     'section text bleeding in, or bullets promoted to rows.',
    'rows_merged': 'Several real entries collapsed into one row - entry splitting missed '
                   'a boundary (inline dates, run-on lines).',
    'rows_split': 'One real entry became several rows - a continuation line was treated '
                  'as a new entry.',
    'dates_missing': 'Entity text was found but its date range was not - extend the date '
                     'parser for the formats in these cases.',
    'low_recall': 'Too few items recovered versus gold.',
    'low_precision': 'Too many items recovered that gold does not list.',
    'domain_wrong': 'Local part matched but the domain did not - likely a character-level '
                    'extraction slip (ligature, OCR, line wrap).',
    'wrong_number': 'A phone was found but it is not the candidate one - check ordering '
                    'and reference-number filtering.',
    'contains_noise': 'Extra tokens came along with the right value - tighten trimming.',
    'over_captured': 'Far more text captured than gold - the summary boundary is too wide.',
    'wrong_text': 'Text captured does not correspond to gold.',
    'cell_unparseable': 'The gold cell itself could not be read - fix the spreadsheet.',
}


@dataclass
class FailureMode:
    tag: str
    field: str
    cases: list[str] = field(default_factory=list)
    lost_weight: float = 0.0
    examples: list[dict[str, Any]] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.cases)

    def guidance(self) -> str:
        for suffix, text in _GUIDANCE.items():
            if self.tag.endswith(suffix):
                return text
        return 'Inspect the example cases below.'

    def to_dict(self) -> dict:
        return {
            'tag': self.tag,
            'field': self.field,
            'count': self.count,
            'lost_score': round(self.lost_weight, 3),
            'guidance': self.guidance(),
            'cases': self.cases[:25],
            'examples': self.examples[:3],
        }


def build_failure_modes(case_results: list[dict]) -> list[FailureMode]:
    """Rank failure modes by weighted score recoverable if fixed."""
    modes: dict[str, FailureMode] = {}
    for case in case_results:
        case_id = case.get('case_id', '')
        for res in case.get('fields', []):
            tags = res.get('error_tags') or []
            if not tags:
                continue
            field_key = res.get('field', '')
            spec = FIELD_BY_KEY.get(field_key)
            weight = spec.weight if spec else 1.0
            lost = (1.0 - float(res.get('score', 0.0))) * weight
            for tag in tags:
                mode = modes.setdefault(tag, FailureMode(tag=tag, field=field_key))
                if case_id not in mode.cases:
                    mode.cases.append(case_id)
                mode.lost_weight += lost
                if len(mode.examples) < 3:
                    mode.examples.append({
                        'case_id': case_id,
                        'gold': res.get('gold', '')[:220],
                        'pred': res.get('pred', '')[:220],
                        'detail': {
                            k: v for k, v in (res.get('detail') or {}).items()
                            if k in ('missed_facts', 'spurious_rows', 'missed', 'extra',
                                     'recall', 'precision', 'gold_parts', 'pred_parts',
                                     'gold', 'pred', 'gold_key', 'pred_key')
                        },
                    })
    return sorted(modes.values(), key=lambda m: (-m.lost_weight, -m.count, m.tag))


def worst_cases(case_results: list[dict], limit: int = 15) -> list[dict]:
    ranked = sorted(case_results, key=lambda c: c.get('accuracy', 0.0))
    out = []
    for case in ranked[:limit]:
        misses = [
            f'{r["field"]}({r["score"]:.2f})'
            for r in case.get('fields', [])
            if r.get('verdict') in ('miss', 'partial', 'false_positive')
        ]
        out.append({
            'case_id': case.get('case_id'),
            'file_name': case.get('file_name'),
            'accuracy': round(case.get('accuracy', 0.0), 3),
            'error': case.get('error', ''),
            'weak_fields': misses,
        })
    return out


def field_rollup(case_results: list[dict]) -> list[dict]:
    """Per-field aggregate: mean score, verdict mix, and false-positive rate."""
    agg: dict[str, dict[str, Any]] = defaultdict(
        lambda: {'scores': [], 'match': 0, 'partial': 0, 'miss': 0,
                 'blank_ok': 0, 'false_positive': 0}
    )
    for case in case_results:
        for res in case.get('fields', []):
            bucket = agg[res['field']]
            verdict = res.get('verdict', 'miss')
            bucket[verdict] = bucket.get(verdict, 0) + 1
            if verdict in ('match', 'partial', 'miss'):
                bucket['scores'].append(float(res.get('score', 0.0)))

    rows = []
    for key, bucket in agg.items():
        spec = FIELD_BY_KEY.get(key)
        scored = bucket['scores']
        blanks = bucket['blank_ok'] + bucket['false_positive']
        rows.append({
            'field': key,
            'label': spec.label if spec else key,
            'weight': spec.weight if spec else 1.0,
            'critical': bool(spec and spec.critical),
            'scored_cases': len(scored),
            'mean_score': round(sum(scored) / len(scored), 4) if scored else None,
            'match': bucket['match'],
            'partial': bucket['partial'],
            'miss': bucket['miss'],
            'blank_gold': blanks,
            'false_positive': bucket['false_positive'],
            'false_positive_rate': round(bucket['false_positive'] / blanks, 3) if blanks else 0.0,
        })
    order = list(FIELD_BY_KEY)
    rows.sort(key=lambda r: order.index(r['field']) if r['field'] in order else 99)
    return rows
