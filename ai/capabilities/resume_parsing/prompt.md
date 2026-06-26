# Resume Parsing Prompt v1.0.0 — PLACEHOLDER

> **Production prompt not yet authored.** Complete sections in `prompt.template.md`, then copy into this file.
>
> Capability: `resume_parsing` | Prompt ID: `resume_parser_v1` | Schema: `resume_v1`

## Status

Pending manual prompt authoring. This stub satisfies capability loader requirements.

## Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `{{input}}` | yes | Primary unstructured or structured input payload |
| `{{context}}` | no | Optional additional context |
| `{{locale}}` | no | Output locale hint (default: en) |

## User Template

```
{{input}}
```

## Output Contract

Emit JSON conforming to schema `resume_v1`. See `schema.json` and `field_definitions.yaml`.
