# Architecture Decision Records (ADR)

Index of significant architectural decisions for the HRMS AI platform.

## Format

Each ADR follows:
- **Status** — Proposed | Accepted | Deprecated | Superseded
- **Context** — Why the decision was needed
- **Problem** — What goes wrong without a decision
- **Decision** — What we chose
- **Alternatives considered** — What we rejected and why
- **Consequences** — Positive and negative outcomes
- **Future work** — Follow-up items

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-001](ADR-001-ai-workspace-layout.md) | AI Workspace Layout | Accepted |
| [ADR-002](ADR-002-dataset-pipeline.md) | Dataset Pipeline | Accepted |
| [ADR-003](ADR-003-registry-design.md) | Registry Design | Accepted |
| [ADR-004](ADR-004-artifact-lineage.md) | Artifact Lineage | Accepted |
| [ADR-005](ADR-005-versioning-strategy.md) | Versioning Strategy | Accepted |
| [ADR-006](ADR-006-ai-platform-vision.md) | AI Platform Vision | Accepted |

## Creating new ADRs

```
ai/docs/adr/ADR-{NNN}-{kebab-title}.md
```

Increment NNN sequentially. Set status to `Proposed` until reviewed in architecture review.

## Superseding ADRs

When reversing a decision, create a new ADR and mark the old one `Superseded by ADR-NNN`. Never delete ADRs.
