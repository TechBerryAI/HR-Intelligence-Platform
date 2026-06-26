# Edge Case Input Template

> Ambiguous or challenging parse scenarios. No production HR data.

```
[EDGE_CASE_INPUT_PLACEHOLDER]
```

## Edge Case Categories

| Category | Test Focus |
|----------|------------|
| Overlapping employment dates | `cross_field.experience_dates_order` warnings |
| Present/current role tokens | `is_current` derivation from end date |
| Career gap in timeline | No fabricated roles to fill gaps |
| Pipe-delimited skills | `skills[]` string normalization |
| Mixed certification formats | String vs object `certifications[]` |
| International phone/date formats | Normalization per `proposal_mapping.yaml` |
| Duplicate URLs in person and links | Dedupe per `cross_field.person_links_dedupe` |
| Multiple degrees same institution | Distinct `education[]` entries |

## Expected Behavior

- Schema validation passes with required keys
- Warnings acceptable in `validation.warnings`
- No invention of credentials not supported by input
