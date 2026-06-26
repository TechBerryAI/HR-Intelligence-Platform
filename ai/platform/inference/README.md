# Inference Layer (Future — M8)

## Purpose

Unified inference runtime that sits between AI services and LLM providers. Not a model trainer — a **request execution engine**.

## Responsibilities (planned)

- Route requests to correct model + provider per feature
- Batch and queue inference for bulk parsing
- Response caching (hash-keyed on input + prompt version)
- Timeout, retry, and fallback chain execution
- Token counting and cost attribution
- Structured output enforcement (TOON contract)

## Inputs / outputs

| Input | Output |
|-------|--------|
| Feature request (parse resume, summarize, etc.) | Structured response (TOON, JSON, text) |
| Provider config from `registry/providers/` | Latency + provider metadata |

## Will NOT contain

- Training code (lives in `training/`)
- Dataset preprocessing (lives in `preprocessing/`)
- HRMS route handlers (lives in `backend/` until M9 adapter)

## Milestone

Implemented as part of **M8 — LLM Gateway**.
