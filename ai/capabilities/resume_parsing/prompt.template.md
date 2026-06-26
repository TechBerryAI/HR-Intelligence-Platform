# Resume Parsing Prompt Template

> Capability: `resume_parsing` | Prompt ID: `resume_parser_v1` | Schema: `resume_v1`
>
> **Status:** Template only — extraction logic to be authored manually.
> Copy completed sections into `prompt.md` when ready for production.

---

## Role

<!-- Define the persona and domain expertise of the parser. -->

---

## Objective

<!-- State the single outcome: structured JSON conforming to resume_v1. -->

---

## Input

<!-- Describe expected input formats (plain text, OCR text, locale hints). -->
<!-- Reference variable: {{input}} -->
<!-- Optional context variable: {{context}} -->
<!-- Optional locale variable: {{locale}} -->

---

## Output

<!-- Reference schema resume_v1 and required root keys. -->
<!-- Specify JSON-only output; no markdown fences unless configured otherwise. -->

---

## Rules

<!-- Global behavioral rules: no fabrication, preserve uncertainty, etc. -->

---

## Extraction Rules

### Personal Information

<!-- How to locate and extract person block fields. -->

### Experience

<!-- Employment history extraction rules. -->

### Education

<!-- Academic credentials extraction rules. -->

### Skills

<!-- Skill list and structured skill object rules. -->

### Projects

<!-- Portfolio and side-project extraction rules. -->

### Certifications

<!-- Credential extraction rules. -->

### Languages

<!-- Language proficiency extraction rules. -->

### Awards

<!-- Honors and recognition extraction rules. -->

### Publications

<!-- Research and publication extraction rules. -->

### Links

<!-- URL and social profile extraction rules. -->

---

## Normalization Rules

<!-- Date formats, Present token, phone/email normalization, company/title cleanup. -->

---

## Validation Rules

<!-- Self-check before emit: required keys, enum values, confidence thresholds. -->

---

## Edge Cases

<!-- Multi-column layouts, career gaps, overlapping roles, international formats, etc. -->

---

## Error Handling

<!-- Behavior when input is empty, corrupted, or not a resume. -->

---

## Output Requirements

<!-- Final checklist: schema compliance, field completeness, confidence scoring. -->

---

## Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `{{input}}` | yes | Primary unstructured or structured input payload |
| `{{context}}` | no | Optional additional context (JD, policy, locale) |
| `{{locale}}` | no | Output locale hint (default: en) |
