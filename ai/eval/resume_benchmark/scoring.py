"""Field-level scoring of a prediction against gold.

Every field produces a :class:`FieldResult` carrying a 0..1 score, a verdict,
and - when it is not a clean match - the evidence needed to fix the parser.

Verdicts
--------
``match``          gold present, recovered
``partial``        gold present, recovered imperfectly
``miss``           gold present, not recovered (or wrong)
``blank_ok``       gold empty, prediction empty
``false_positive`` gold empty, prediction invented a value
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import normalize as nz
from .config import MATCH_PARTIAL, MATCH_STRONG, SECTION_VALUE_FIELDS, FieldSpec

MATCH = 'match'
PARTIAL = 'partial'
MISS = 'miss'
BLANK_OK = 'blank_ok'
FALSE_POSITIVE = 'false_positive'

SCORED_VERDICTS = (MATCH, PARTIAL, MISS)


@dataclass
class FieldResult:
    field: str
    verdict: str
    score: float
    gold: str = ''
    pred: str = ''
    detail: dict[str, Any] = field(default_factory=dict)
    error_tags: list[str] = field(default_factory=list)

    @property
    def counts_toward_accuracy(self) -> bool:
        return self.verdict in SCORED_VERDICTS

    def to_dict(self) -> dict:
        return {
            'field': self.field,
            'verdict': self.verdict,
            'score': round(self.score, 4),
            'gold': self.gold[:400],
            'pred': self.pred[:400],
            'detail': self.detail,
            'error_tags': self.error_tags,
        }


def _verdict(score: float) -> str:
    if score >= MATCH_STRONG:
        return MATCH
    if score >= MATCH_PARTIAL:
        return PARTIAL
    return MISS


def _preview(value: Any, limit: int = 300) -> str:
    if value is None:
        return ''
    if isinstance(value, (list, tuple)):
        return ' | '.join(_preview(v, 80) for v in value)[:limit]
    if isinstance(value, dict):
        return ', '.join(f'{k}={v}' for k, v in value.items() if v)[:limit]
    return str(value).strip()[:limit]


# ------------------------------------------------------------ scalar scorers


def _score_email(gold: str, pred: Any) -> tuple[float, dict, list[str]]:
    g, p = nz.emails(gold), nz.emails(pred)
    if not p:
        return 0.0, {}, ['email_not_extracted']
    if g & p:
        return 1.0, {}, []
    # Same local part, different domain usually means an OCR/ligature slip.
    gl = {e.split('@')[0] for e in g}
    pl = {e.split('@')[0] for e in p}
    if gl & pl:
        return 0.6, {'gold': sorted(g), 'pred': sorted(p)}, ['email_domain_wrong']
    return 0.0, {'gold': sorted(g), 'pred': sorted(p)}, ['email_wrong_value']


def _score_phone(gold: str, pred: Any) -> tuple[float, dict, list[str]]:
    g, p = nz.phones(gold), nz.phones(pred)
    if not p:
        return 0.0, {}, ['phone_not_extracted']
    if g & p:
        return 1.0, {}, []
    return 0.0, {'gold': sorted(g), 'pred': sorted(p)}, ['phone_wrong_number']


def _score_name(gold: str, pred: Any) -> tuple[float, dict, list[str]]:
    score = nz.name_score(gold, pred)
    tags: list[str] = []
    if not str(pred or '').strip():
        tags.append('name_not_extracted')
    elif score < MATCH_STRONG:
        pt, gt = nz.tokens(pred), nz.tokens(gold)
        tags.append('name_contains_noise' if len(pt - gt) > len(gt) else 'name_wrong_value')
    return score, {}, tags


def _score_location(gold: str, pred: Any) -> tuple[float, dict, list[str]]:
    score = nz.location_score(gold, pred)
    tags: list[str] = []
    if not str(pred or '').strip():
        tags.append('location_not_extracted')
    elif score < MATCH_PARTIAL:
        tags.append('location_wrong_value')
    return score, {'gold_parts': nz.location_parts(gold), 'pred_parts': nz.location_parts(pred)}, tags


def _score_url(gold: str, pred: Any, field_key: str) -> tuple[float, dict, list[str]]:
    score = nz.url_score(gold, pred)
    tags: list[str] = []
    if not str(pred or '').strip():
        tags.append(f'{field_key}_not_extracted')
    elif score < MATCH_STRONG:
        tags.append(f'{field_key}_wrong_value')
    return score, {}, tags


def _score_enum(gold: str, pred: Any) -> tuple[float, dict, list[str]]:
    score = nz.level_score(gold, pred)
    detail = {'gold_key': nz.level_key(gold), 'pred_key': nz.level_key(pred)}
    tags: list[str] = []
    if not str(pred or '').strip():
        tags.append('level_not_extracted')
    elif score < 1.0:
        tags.append(f'level_{detail["gold_key"]}_predicted_{detail["pred_key"] or "blank"}')
    return score, detail, tags


def _score_skills(gold: str, pred: Any) -> tuple[float, dict, list[str]]:
    precision, recall, f1, missed, extra = nz.skills_prf(gold, pred)
    detail = {
        'precision': round(precision, 3),
        'recall': round(recall, 3),
        'f1': round(f1, 3),
        'missed': missed[:20],
        'extra': extra[:20],
        'gold_n': len(nz.split_skills(gold, drop_headers=True)),
        'pred_n': len(nz.split_skills(pred)),
    }
    tags: list[str] = []
    if detail['gold_n'] == 0:
        # The whole gold cell was category labels - nothing to measure.
        return 1.0, detail, []
    if detail['pred_n'] == 0:
        tags.append('skills_not_extracted')
    else:
        if recall < 0.7:
            tags.append('skills_low_recall')
        if precision < 0.7:
            tags.append('skills_low_precision')
    return f1, detail, tags


def _score_text(gold: str, pred: Any) -> tuple[float, dict, list[str]]:
    """Summary-style text: reward covering the gold, tolerate extra length."""
    pred_text = str(pred or '').strip()
    if not pred_text:
        return 0.0, {}, ['summary_not_extracted']
    cover = nz.containment(gold, pred_text)
    similarity = nz.ratio(gold, pred_text)
    score = max(cover, similarity)
    tags: list[str] = []
    if score < MATCH_PARTIAL:
        tags.append('summary_wrong_text')
    elif cover >= 0.9 and len(nz.tokens(pred_text)) > 3 * max(1, len(nz.tokens(gold))):
        tags.append('summary_over_captured')
    return score, {'coverage': round(cover, 3), 'similarity': round(similarity, 3)}, tags


# ----------------------------------------------------------- section scoring


def _pred_section_strings(section_key: str, rows: Any) -> list[str]:
    """Flatten predicted rows into comparable normalized entity strings."""
    out: list[str] = []
    if not isinstance(rows, list):
        return out
    value_fields = SECTION_VALUE_FIELDS.get(section_key, ())
    for row in rows:
        if not isinstance(row, dict):
            out.append(nz.norm(row))
            continue
        for key in value_fields:
            value = nz.norm(row.get(key))
            if len(value) >= 3:
                out.append(value)
    return out


def _pred_section_rows_text(section_key: str, rows: Any) -> list[str]:
    out: list[str] = []
    if not isinstance(rows, list):
        return out
    value_fields = SECTION_VALUE_FIELDS.get(section_key, ())
    for row in rows:
        if isinstance(row, dict):
            parts = [str(row.get(k) or '') for k in value_fields]
            out.append(nz.norm(' '.join(p for p in parts if p)))
        else:
            out.append(nz.norm(row))
    return out


def _fact_hit(fact: str, candidates: list[str]) -> tuple[bool, float]:
    best = 0.0
    for cand in candidates:
        if not cand:
            continue
        if fact == cand:
            return True, 1.0
        if len(fact) >= 6 and (fact in cand or cand in fact):
            return True, 0.95
        score = nz.ratio(fact, cand)
        best = max(best, score)
        if score >= MATCH_STRONG:
            return True, score
    return False, best


def _score_section(section_key: str, gold_entries: list[dict], pred_rows: Any) -> tuple[float, dict, list[str]]:
    """Fact recall + row precision + date accuracy for a repeating section."""
    pred_strings = _pred_section_strings(section_key, pred_rows)
    pred_rows_text = _pred_section_rows_text(section_key, pred_rows)
    gold_facts = [f for entry in gold_entries for f in entry.get('facts', [])]
    gold_years: set[str] = set()
    for entry in gold_entries:
        gold_years.update(entry.get('years') or [])

    tags: list[str] = []
    if not gold_facts:
        return 0.0, {'reason': 'gold_had_no_facts'}, []

    if not pred_strings:
        return 0.0, {
            'recall': 0.0,
            'precision': 0.0,
            'gold_facts': len(gold_facts),
            'pred_rows': 0,
            'missed_facts': gold_facts[:12],
        }, [f'{section_key}_not_extracted']

    missed = []
    hits = 0
    for fact in gold_facts:
        ok, _best = _fact_hit(fact, pred_strings)
        if ok:
            hits += 1
        else:
            missed.append(fact)
    recall = hits / len(gold_facts)

    # Precision over predicted rows: a row that matches no gold fact is noise
    # (section bleed, a bullet promoted to a row, a hallucinated employer).
    gold_blob = ' \n '.join(nz.norm(e.get('raw', '')) for e in gold_entries)
    spurious = []
    for row_text in pred_rows_text:
        if not row_text:
            spurious.append('<empty row>')
            continue
        ok, _best = _fact_hit(row_text, gold_facts)
        if not ok and nz.containment(row_text, gold_blob) < 0.6:
            spurious.append(row_text[:90])
    precision = 1 - len(spurious) / max(1, len(pred_rows_text))

    pred_years: set[str] = set()
    if isinstance(pred_rows, list):
        for row in pred_rows:
            if isinstance(row, dict):
                for key in ('startMonth', 'endMonth', 'validTill'):
                    pred_years.update(nz.year_tokens(row.get(key)))
    date_recall = (len(gold_years & pred_years) / len(gold_years)) if gold_years else 1.0

    row_count_delta = len(pred_rows_text) - len(gold_entries)

    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    score = 0.65 * f1 + 0.2 * recall + 0.15 * date_recall

    if recall < 0.7:
        tags.append(f'{section_key}_low_fact_recall')
    if precision < 0.7:
        tags.append(f'{section_key}_spurious_rows')
    if gold_years and date_recall < 0.5:
        tags.append(f'{section_key}_dates_missing')
    if row_count_delta <= -1 and len(gold_entries) > 1:
        tags.append(f'{section_key}_rows_merged')
    if row_count_delta >= 2:
        tags.append(f'{section_key}_rows_split')

    detail = {
        'recall': round(recall, 3),
        'precision': round(precision, 3),
        'f1': round(f1, 3),
        'date_recall': round(date_recall, 3),
        'gold_entries': len(gold_entries),
        'pred_rows': len(pred_rows_text),
        'gold_facts': len(gold_facts),
        'missed_facts': missed[:12],
        'spurious_rows': spurious[:8],
    }
    return min(1.0, score), detail, tags


# ----------------------------------------------------------------- dispatch


def score_field(spec: FieldSpec, gold: dict, prediction: dict) -> FieldResult:
    gold_value = str(gold.get(spec.key) or '').strip()
    pred_value = prediction.get(spec.key)

    if spec.metric == 'section':
        gold_entries = (gold.get('_sections') or {}).get(spec.key) or []
        pred_rows = pred_value if isinstance(pred_value, list) else []
        if not gold_value and not gold_entries:
            if pred_rows:
                return FieldResult(
                    spec.key, FALSE_POSITIVE, 0.0, '', _preview(pred_rows),
                    {'pred_rows': len(pred_rows)}, [f'{spec.key}_invented'],
                )
            return FieldResult(spec.key, BLANK_OK, 1.0)
        score, detail, tags = _score_section(spec.key, gold_entries, pred_rows)
        return FieldResult(
            spec.key, _verdict(score), score,
            gold_value, _preview(pred_rows), detail, tags,
        )

    pred_text = '' if pred_value is None else str(pred_value).strip()

    if not gold_value:
        if not pred_text:
            return FieldResult(spec.key, BLANK_OK, 1.0)
        if spec.blank_gold_fallback:
            # Designed behaviour: the field mirrors another when the resume is
            # silent. Compare against that field on either side of the pair.
            echoes = [
                str(gold.get(spec.blank_gold_fallback) or '').strip(),
                str(prediction.get(spec.blank_gold_fallback) or '').strip(),
            ]
            if any(e and nz.location_score(e, pred_text) >= MATCH_STRONG for e in echoes):
                return FieldResult(
                    spec.key, BLANK_OK, 1.0, '', pred_text[:300],
                    {'designed_fallback_from': spec.blank_gold_fallback},
                )
        return FieldResult(
            spec.key, FALSE_POSITIVE, 0.0, '', pred_text[:300], {}, [f'{spec.key}_invented']
        )

    if spec.metric == 'email':
        score, detail, tags = _score_email(gold_value, pred_text)
    elif spec.metric == 'phone':
        score, detail, tags = _score_phone(gold_value, pred_text)
    elif spec.metric == 'name':
        score, detail, tags = _score_name(gold_value, pred_text)
    elif spec.metric == 'location':
        score, detail, tags = _score_location(gold_value, pred_text)
    elif spec.metric == 'url':
        score, detail, tags = _score_url(gold_value, pred_text, spec.key)
    elif spec.metric == 'enum':
        score, detail, tags = _score_enum(gold_value, pred_text)
    elif spec.metric == 'skills':
        pred_for_skills = prediction.get('_skills') or pred_text
        score, detail, tags = _score_skills(gold_value, pred_for_skills)
    elif spec.metric == 'text':
        score, detail, tags = _score_text(gold_value, pred_text)
    else:  # pragma: no cover - guarded by FIELDS
        raise ValueError(f'unknown metric: {spec.metric}')

    return FieldResult(spec.key, _verdict(score), score, gold_value, pred_text, detail, tags)


def score_case(gold: dict, prediction: dict, specs: tuple[FieldSpec, ...]) -> list[FieldResult]:
    return [score_field(spec, gold, prediction) for spec in specs]


def case_accuracy(results: list[FieldResult], specs: tuple[FieldSpec, ...]) -> float:
    """Weighted mean over fields where gold actually had a value."""
    by_key = {s.key: s for s in specs}
    total = weight_sum = 0.0
    for res in results:
        if not res.counts_toward_accuracy:
            continue
        weight = by_key[res.field].weight
        total += res.score * weight
        weight_sum += weight
    return total / weight_sum if weight_sum else 0.0
