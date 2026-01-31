# LLM API Key Rotation and Usage Strategy (xAI / Grok)

Production-ready design for multi-key rotation, per-service isolation, and graceful degradation.

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         LLM Key Manager                                  │
│  ┌──────────────┐  ┌─────────────────┐  ┌──────────────────────────┐ │
│  │ Key Registry │  │ Selection Policy │  │ Failure / Cooldown State   │ │
│  │ (env-loaded) │  │ (per-service RR) │  │ (rate limit, 5xx, timeout)  │ │
│  └──────┬───────┘  └────────┬────────┘  └──────────────┬─────────────┘ │
│         │                    │                          │              │
│         └────────────────────┼────────────────────────────┘              │
│                              ▼                                          │
│                    get_key(service_id) → (slot_id, auth_header)          │
│                    report_result(slot_id, status_code, latency_ms)      │
└─────────────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
   Resume Parsing      JD Parsing         ATS / Bulk / Async
   (service: parsing)  (service: parsing) (service: ats | bulk | async)
```

- **Key Registry**: Loads keys from env (`HRMS_API_KEY_1` … `HRMS_API_KEY_N`, optional `XAI_API_KEY`). Stores only opaque slot IDs and secrets in memory; never logs or exposes raw keys.
- **Selection**: Per-service round-robin over the **shared** key pool (or per-service sub-pools if you later want isolation). Each service gets the next key in sequence so load is spread and one service cannot starve others when keys are shared fairly.
- **Failure handling**: On 429 (rate limit) or 5xx/timeout, mark that key as in cooldown for a configurable window; retry the request with the next key. No global lock: selection uses an atomic counter; cooldown state uses a lock only for the small critical section that updates key state.

---

## 2. Key Rotation Strategy

- **Selection**: Round-robin per service. Each call to `get_key(service_id)` advances that service’s index modulo key count and returns the next key. Deterministic, fair, and avoids thundering herd on a single key.
- **Per-service index**: Optional but recommended: each service has its own counter (e.g. `parsing`, `ats`, `bulk`, `async`). So resume parsing and JD parsing can share `parsing` or use separate service IDs; ATS/bulk/async use their own. Prevents one high-volume service from always getting “first” key and others from getting the rest.
- **Cooldown on failure**: On 429 or 5xx or timeout, put that key in cooldown for e.g. 60–120 seconds. During cooldown it is skipped in round-robin. After cooldown it re-enters rotation. No permanent blacklisting unless you add it explicitly.
- **Retry with next key**: When a request fails with a retryable condition, the caller (or a thin wrapper) gets the next key via `get_key(service_id)` and retries. Cap total retries (e.g. once per key, or 2–3 attempts total) to bound latency.
- **No key in logs**: Log only slot index (e.g. `key_slot=1`) and status/latency. Never log `Authorization` header or key value.

---

## 3. Python Module Structure

```
backend/
  llm_key_manager.py    # Key registry, selection, cooldown, metrics
  llm_service.py        # Uses key manager for xAI; same call_llm() API
```

**llm_key_manager.py**

- **KeyRegistry**
  - Load keys from env: `HRMS_API_KEY_1` … `HRMS_API_KEY_9`, then `XAI_API_KEY` if set. Store as list of (slot_id, secret); slot_id = 0, 1, … for logging only.
  - Method: `get_keys() -> list[tuple[int, str]]` (internal); no public API that returns raw secrets.

- **KeyManager** (singleton or app-scoped)
  - Holds: KeyRegistry instance; per-service round-robin index (dict[str, int]); cooldown_until per slot_id (dict[int, float]); lock for cooldown updates; optional metrics (usage count, failure count per slot).
  - `get_key_for_service(service_id: str) -> tuple[int, str]`
    - Under lock (or lock-free counter): advance service’s index, then scan keys in RR order starting at that index; skip keys in cooldown; return first usable (slot_id, secret). If all in cooldown, return the one with earliest cooldown_until (graceful degradation).
  - `report_result(slot_id: int, success: bool, status_code: int | None, latency_ms: float)`
    - If 429 or (5xx or timeout): set cooldown_until[slot_id] = now + COOLDOWN_SECONDS. Update metrics (success/fail, latency). Called by llm_service after each request.

- **Constants**: COOLDOWN_SECONDS (e.g. 60), MAX_KEYS_TO_TRY per request (e.g. number of keys).

**llm_service.py**

- For xAI: obtain (slot_id, secret) from KeyManager.get_key_for_service(service_id). Default `service_id='parsing'` (resume + JD). Future ATS/bulk/async can pass `'ats'`, `'bulk'`, `'async'` for per-service round-robin. Build `Authorization: Bearer <secret>`, send request. On 429/5xx/timeout, call report_result(slot_id, False, ...), then get next key and retry. On success, report_result(slot_id, True, 200, latency_ms). Never log secret or full header.

---

## 4. Failure Handling (Details)

- **Rate limit (429)**: Treat as retryable with another key. Put current key in cooldown; retry with next key immediately (no sleep, or optional short backoff).
- **5xx / timeout**: Same: cooldown current key, retry with next key.
- **4xx (except 429)**: Do not retry with another key (client error). Do not put key in cooldown. Optionally log slot_id for debugging.
- **All keys in cooldown**: Return the key whose cooldown expires soonest, so we still attempt a request rather than failing fast. Optionally log a warning “all keys in cooldown, using earliest expiry”.

---

## 5. Performance

- **Minimize latency**: Round-robin is O(1) per selection. Cooldown check is a dict lookup and float compare. Lock only around the small section that updates index and cooldown_until (or use atomic index + lock only for cooldown map).
- **Avoid global lock**: Use one lock per KeyManager, and keep the critical section small (increment index, pick key, optionally update cooldown on report_result). No lock held during the actual HTTP request.

---

## 6. Observability

- **Logging**: Log at INFO: service_id, key_slot (index), success/failure, status_code, latency_ms. Never log key or Authorization.
- **Metrics**: Optional in-memory counters: per-slot requests, successes, failures (and optionally 429 count). Expose via a simple get_metrics() dict or /metrics endpoint for Prometheus-style scraping. No keys in metrics.

---

## 7. Security

- **No hardcoding**: All keys from env. Business logic only receives (slot_id, secret) from KeyManager; no key strings in parsing_routes or elsewhere.
- **No leakage**: No key or Bearer token in logs, exceptions, or error messages. On ValueError from API, raise a generic message (e.g. “LLM request failed”) or include only status_code and slot_id if needed.

---

## 8. Extensibility

- **Add/remove keys**: Add `HRMS_API_KEY_5` in .env and restart; KeyRegistry loads all present keys. Remove by dropping from .env. No code change.
- **New services**: Call `get_key_for_service('new_service_name')` and `report_result(...)` after each request. Each service gets its own round-robin counter.
- **Vendor-agnostic**: KeyManager is provider-agnostic (returns a secret string). llm_service uses it only for xAI; OpenAI/Anthropic can keep single-key or get their own multi-key layer later.

---

## 9. Why This Improves Speed, Accuracy, and Reliability

- **Speed**: Spreading requests across keys reduces per-key rate limiting and avoids serializing all traffic behind one key. Round-robin adds negligible latency.
- **Accuracy**: No change to prompts or model; same accuracy. Reliability improvements reduce spurious failures that could be mistaken for “bad” outputs.
- **Reliability**: Multiple keys and automatic retry with cooldown prevent a single rate limit or outage from failing all requests. Graceful degradation (use key with earliest cooldown when all are cooling) maximizes chance of success under load.
