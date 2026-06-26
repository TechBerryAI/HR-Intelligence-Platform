# Bad Input Template

> Input that should fail validation or trigger human review.

```
[BAD_INPUT_PLACEHOLDER]
```

## Failure Scenarios

Use one of the following at evaluation time (do not embed real data):

| Scenario | Expected Outcome |
|----------|------------------|
| Empty input | Missing required fields or confidence below threshold |
| Non-resume document | `type` mismatch or validation failure |
| Corrupted OCR text | Low confidence; sparse extraction |
| Invalid email in output | Regex validation failure |

## Expected Behavior

- Runtime validation rejects invalid JSON shape
- `confidence` below `min_overall` (0.6) triggers review
- No fabrication of contact details from empty input
