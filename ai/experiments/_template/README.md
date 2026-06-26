# Experiment template

Copy this directory to start a new experiment:

```bash
cp -r experiments/_template experiments/2026-06-25_my-experiment
```

Then fill in README.md, config.yaml, and links.yaml.

## config.yaml (starter)

```yaml
experiment_id: YYYY-MM-DD_slug
feature: parsing
status: planned
variables: {}
success_criteria: {}
```

## links.yaml (starter)

```yaml
training_runs: []
eval_reports: []
registry_models: []
related_experiments: []
```
