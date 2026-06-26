# Input Template

> Replace placeholder with sanitized resume text from evaluation datasets.

```
[DOCUMENT_TEXT_PLACEHOLDER]
```

## Expected Profile

Well-structured resume with complete sections.

## Expected Output

See `examples/templates/output.template.json` and `schema.json`.

## Quality Expectations

- `confidence` >= 0.85
- `validation.is_valid` = true
- `validation.toon_projectable` = true
- All required root keys present
