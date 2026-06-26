# Current Database Flow — Storage and Retrieval

**Status:** Reverse-engineered from production code  
**Schema source:** `backend/schema_pg/01_schema.sql`  
**Access layer:** `backend/db.py` (via `db_run`, `db_get`, `db_all`)

---

## Tables Involved in Parsing

### `raw_files`

Immutable upload metadata and deduplication anchor.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | UUID PK | `raw_file_id` returned to client |
| `uploader_id` | VARCHAR(50) | Candidate CID or HR ID |
| `uploader_role` | VARCHAR(20) | `'candidate'` or `'admin'` |
| `original_filename` | VARCHAR(255) | Sanitized name |
| `storage_url` | VARCHAR(1000) | `file://{absolute_path}` |
| `mime_type` | VARCHAR(100) | From extension map |
| `file_hash` | VARCHAR(64) | SHA-256 hex |
| `size_bytes` | BIGINT | File size |
| `created_at` | TIMESTAMPTZ | Upload time |

**Constraints:** `UNIQUE (file_hash, uploader_id)`

**Indexes:**

- `IX_raw_files_uploader` on `(uploader_id, uploader_role)`
- `IX_raw_files_hash` on `file_hash`
- `IX_raw_files_created_at` on `created_at DESC`

**Write path:** `parsing_utils.store_raw_file()`

**Duplicate behavior:** If `(file_hash, uploader_id)` exists, returns existing row without re-writing file.

---

### `parsed_resumes`

Canonical structured resume output.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | UUID PK | `parsed_id` |
| `raw_file_id` | UUID FK → `raw_files` | CASCADE delete |
| `candidate_id` | VARCHAR(20) FK → `candidate_signup` | Nullable; SET NULL on delete |
| `toon` | TEXT | `toon_dumps(parsed dict)` |
| `full_text` | TEXT | Extracted plain text |
| `confidence` | FLOAT | 0.0–1.0 heuristic |
| `model_version` | VARCHAR(100) | e.g. `xai-v1` |
| `created_at` | TIMESTAMPTZ | Parse time |

**Indexes:**

- `IX_parsed_resumes_raw_file`
- `IX_parsed_resumes_candidate`
- `IX_parsed_resumes_confidence`
- `IX_parsed_resumes_created_at DESC`

**Write path:** `parsing_utils.store_parsed_resume()`

**Linking `candidate_id`:**

1. Form field `candidate_id` on upload
2. Auto-set from JWT for candidate role
3. Cache hit update: `UPDATE parsed_resumes SET candidate_id = ?`
4. Apply fallback: link via `raw_files.uploader_id`

---

### `parsed_jds`

Canonical structured job description output.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | UUID PK | `parsed_id` |
| `raw_file_id` | UUID FK | CASCADE |
| `job_id` | VARCHAR(20) FK → `jobs` | Nullable; SET NULL |
| `toon` | TEXT | Serialized TOON |
| `full_text` | TEXT | Extracted text |
| `confidence` | FLOAT | Heuristic |
| `model_version` | VARCHAR(100) | Provider version tag |
| `created_at` | TIMESTAMPTZ | Parse time |

**Indexes:** `raw_file_id`, `job_id`, `confidence`, `created_at`

**Write path:** `parsing_utils.store_parsed_jd()`

**Note:** `job_id` from form is optional; JD parse can occur before job row exists.

---

## Write Sequence (Single Parse)

```
1. compute_file_hash(file_data)
2. get_cached_parsing_result(hash, uploader_id, type) → early return if hit
3. store_raw_file() → INSERT raw_files (or return duplicate)
4. extract_text()
5. call_llm() → dict
6. [resume post-process]
7. validate_toon_format()
8. calculate_confidence()
9. store_parsed_resume/jd() → INSERT parsed_*
```

**Transaction model:** Each `db_run` is individual; no explicit multi-statement transaction wrapper in parsing code.

---

## Read Paths

### API Retrieval

| Endpoint | Query | Deserialize |
|----------|-------|-------------|
| `GET /api/parsed/resume/{id}` | `SELECT id, toon, confidence, model_version, created_at FROM parsed_resumes WHERE id = ?` | `toon_loads_flex` |
| `GET /api/parsed/jd/{id}` | Same on `parsed_jds` | `toon_loads_flex` |

### Duplicate Cache Read

```sql
SELECT p.id, p.toon, p.confidence, p.model_version, p.created_at, r.id as raw_file_id
FROM parsed_resumes|parsed_jds p
INNER JOIN raw_files r ON p.raw_file_id = r.id
WHERE r.file_hash = ? AND r.uploader_id = ?
ORDER BY p.created_at DESC
LIMIT 1  -- via db_get (single row)
```

### Apply Workflow Read

```sql
-- Primary
SELECT toon, confidence, id FROM parsed_resumes
WHERE candidate_id = ? ORDER BY created_at DESC

-- Fallback
SELECT pr.toon, pr.confidence, pr.id
FROM parsed_resumes pr
INNER JOIN raw_files rf ON pr.raw_file_id = rf.id
WHERE rf.uploader_id = ?
ORDER BY pr.created_at DESC

-- JD
SELECT toon, confidence FROM parsed_jds
WHERE job_id = ? ORDER BY created_at DESC
```

### HR Applications View

`jobs.py` lists applications with `ats_analysis` from `applications` table — **not** direct `parsed_resumes` join. Candidate profile tables (`candidate_education`, etc.) are separate from parsed TOON.

---

## Related Tables (Downstream, Not Parsing Output)

### `applications`

Stores ATS results computed **from** parsed TOON at apply time:

| Column | Source |
|--------|--------|
| `match_score` | ATS `json_output.final_score` or `overall_match_score` |
| `matching_percentage` | Mirrored from match_score |
| `shortlisted` | Derived from ATS `decision` |
| `ats_reasoning` | Text rationale |
| `ats_analysis` | `toon_dumps(ats_result)` full structure |

### `candidate_profiles`

Populated manually from form after autofill — **not** auto-synced from `parsed_resumes`.

| Column | May originate from TOON via UI |
|--------|-------------------------------|
| `full_name`, `email`, `phone` | `mapResumeTOONToForm` |
| `linkedin_url`, `portfolio_url` | URL fields |
| `current_location` | `person.location` |
| `resume` | BYTEA — separate file upload, not `raw_files` |

---

## File Storage (Non-DB)

| Attribute | Value |
|-----------|-------|
| Path | `{UPLOAD_FOLDER}/{uploader_id}_{uuid}{ext}` |
| URL stored | `file://{absolute_path}` |
| Default folder | `./uploads` |

Bulk parsing does **not** write to `raw_files` or `parsed_resumes`.

---

## Data Lifecycle

```
Upload → raw_files (per uploader dedup)
      → parsed_* (new row every successful parse, even same raw_file_id possible on re-parse?)
```

**Note:** Cache prevents re-parse for same hash+uploader; new parse only on cache miss.

**Cascade:** Deleting `raw_files` cascades to `parsed_resumes` / `parsed_jds`.

---

## Consumers and Downstream Effects

| Consumer | Reads | Effect |
|----------|-------|--------|
| `ApplicantProfile` | API response TOON (ephemeral) | Form autofill; user saves to `candidate_profiles` |
| `Dashboard` JD upload | API response TOON | Job form autofill; job posted to `jobs` |
| `applications.apply_job` | `parsed_resumes`, `parsed_jds` | ATS thread; updates `applications` |
| `ats_service` | TOON dicts in memory | Match score, shortlist |
| `trigger_n8n` | TOON dicts (optional) | External workflow |
| `jobs.get_applications` | `applications.ats_analysis` | HR candidate review UI |
| `super_admin` | `applications.ats_analysis` | System analytics |
| Bulk Excel export | In-memory only | No DB effect |

---

## Model Version Tracking

```python
model_version = f"{os.getenv('LLM_PROVIDER', 'xai')}-v1"
```

Stored per parse row; returned in API. **Not** tied to `XAI_MODEL` name (e.g. `grok-4-fast-reasoning`).

---

## PostgreSQL vs Legacy

Schema file targets PostgreSQL. `applications.py` and `jobs.py` branch on `BACKEND == 'postgresql'` for boolean vs integer `shortlisted` — parsing tables use standard types in PG schema.

---

## Gaps and Observations

1. **No parse history versioning** — new insert per successful parse; retrieval uses `ORDER BY created_at DESC`.
2. **`full_text` stored but rarely exposed** via parse API endpoints.
3. **`job_id` / `candidate_id` optional** — linking depends on upload context.
4. **Profile tables decoupled** — parsed data and candidate profile can diverge after manual edits.
5. **Bulk parses leave no audit trail** in database.
