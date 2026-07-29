# AI Runtime Package (shim)

Bridge to the AI platform execution engine.

## Source of truth

`../../ai/runtime/`

## Consumers

- `apps/backend/app/ai/adapter/runtime_adapter.py`

## Usage

The backend adapter inserts `ai/` on `sys.path` and calls `get_runtime()`.
This package documents the canonical path for future workspace tooling.
