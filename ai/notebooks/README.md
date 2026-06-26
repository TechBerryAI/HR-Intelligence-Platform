# Notebooks

Jupyter notebooks for exploratory work — **not** production pipelines.

## Intended use

- Prompt A/B experiments before promoting to `prompts/*.yaml`
- Error analysis on benchmark failures
- Dataset distribution and field coverage charts
- Ad-hoc provider latency comparisons

## Conventions

- Name notebooks with date prefix: `YYYY-MM-DD_topic.ipynb`
- Do not embed API keys; use `%env` or `dotenv` loading from `../.env`
- Export reproducible findings to `docs/` or promote logic to `scripts/`

## Kernel setup

```bash
cd ai
source .venv/bin/activate
python -m ipykernel install --user --name=hrms-ai
```

Select kernel **hrms-ai** in Jupyter Lab/Notebook.
