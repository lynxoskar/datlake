# Datlake Python SDK — Lineage‑First System Plan (v1)

## 1) Goals and scope
- Primary goal: make it trivial for users and services to run lineage‑tracked jobs against Datlake.
- The SDK will manage job context: start → operate (read/write) → complete, while notifying the backend for lineage and operational telemetry.
- Provide convenience helpers for fetching table URIs (for reads) and registering new snapshots (for writes).
- Optional “ship logs” feature: at job completion, upload and link a log file artifact to the run.

Out of scope for v1: full detached caching and rich dataframe integrations (kept for v2+).

## 2) Concepts and lifecycle
- Job: a named unit of work (e.g., "daily_sales_etl").
- Run: a single execution of a job (created on `start`).
- JobContext: a context manager that encapsulates run state, emits start/complete events, and offers helpers.
- Artifacts: optional outputs like a final log file uploaded and linked to the run.

```
with JobContext(job_name, metadata) as job:
  uri = job.get_table_latest_uri("source_table")
  df  = read_data(uri)                      # user’s code / helpers
  out_uri = write_data_and_get_uri(df)      # user’s code / helpers
  job.register_snapshot("target_table", out_uri, format="parquet", schema=...)  
  # (optional) job.log_event(...)
# on exit → job.complete(success/failed) and (optional) upload log file
```

## 3) API design

### 3.1 Client configuration
- Env vars: `DATLAKE_API_URL`, `DATLAKE_API_KEY` (or per‑call token).
- Optional settings:
  - `DATLAKE_ARTIFACT_BUCKET` (for log uploads via SDK helper)
  - `DATLAKE_DEFAULT_TIMEOUT_MS` (HTTP timeouts)
  - `DATLAKE_LOG_SHIP=true|false` (default opt‑in behavior)

```python
from datlake_sdk import DatlakeClient

client = DatlakeClient(
  base_url=os.getenv("DATLAKE_API_URL"),
  api_key=os.getenv("DATLAKE_API_KEY"),
)
```

### 3.2 JobContext
- `JobContext` manages: start, heartbeat (optional), custom events, and completion.
- Methods:
  - `start(job_name: str, metadata: dict | None) -> JobContext` (usually internal; use constructor/with)
  - `log_event(event_type: str, data: dict)`
  - `get_table_latest_uri(table_name: str) -> str`
  - `register_snapshot(table_name: str, uri: str, format: str, schema: dict | None) -> dict`
  - `complete(success: bool = True, extra: dict | None = None)`
  - `attach_log(filepath: str)` (marks for upload on completion)

Usage
```python
from datlake_sdk import JobContext

with JobContext(client, job_name="daily_sales_etl", metadata={"source": "s3"}, ship_logs=True) as job:
    src = job.get_table_latest_uri("sales_raw")
    df  = read_sales(src)  # user-defined
    out_uri = write_sales_curated(df)  # returns s3://.../parquet
    job.register_snapshot("sales_curated", out_uri, format="parquet", schema=df_schema)
    job.log_event("metrics", {"rows": len(df)})
# on exit: job.complete(success=True) and if ship_logs, upload and link logs
```

### 3.3 Data helpers (thin)
- Keep SDK minimal; do not force a single dataframe engine.
- Provide optional helpers to ease IO without choosing the user’s stack:
  - `resolve_table_uri(table_name: str) -> str`
  - `upload_object(bucket: str, object_name: str, file_path: str) -> str` (to support artifact upload)

## 4) Backend API interactions (canonical intent)
Normalize towards `/api/v1/*` (aliases may exist during transition):

- Jobs & runs
  - POST `/api/v1/jobs/{job_name}/runs` → start a run, returns `{ run_id, ... }`
  - PUT  `/api/v1/jobs/{job_name}/runs/{run_id}/complete` → mark success/failure + metadata
  - POST `/api/v1/events/broadcast` → custom events (optionally namespaced to run)

- Tables (read path)
  - GET `/api/v1/tables/{table_name}/snapshots/latest` → `{ uri, format, schema, created_at }`

- Snapshots (write path)
  - POST `/api/v1/jobs/register-snapshot` (authenticated, lineage-aware)
    - Body: `{ table_name, uri, format, schema, job_name, run_id }`

- Artifacts (optional log shipping)
  - SDK uploads the log file via datasets endpoint, then links artifact to the run via completion payload:
    - PUT `/api/v1/datasets/{bucket}/{object}` (stream upload)
    - On `complete`, include `{ artifacts: [{ type: "log", uri: "s3://..." }] }`

## 5) Error handling, retries, and telemetry
- All HTTP interactions use retries with exponential backoff and jitter (idempotent endpoints only).
- Clear exceptions: AuthError, NotFound, Conflict, TransientNetworkError, ServerError.
- Correlation: include `X-Request-Id` pass‑through; surface run_id in exceptions where relevant.
- Optional heartbeats: SDK may send periodic pings as events, controlled by `heartbeat_interval_s`.

## 6) Logging & artifact shipping (opt‑in)
- `ship_logs=True` in `JobContext` collects a file path (default points to the process log) and uploads on `complete`.
- Upload target derived from `DATLAKE_ARTIFACT_BUCKET` and object key `jobs/{job_name}/{run_id}/run.log`.
- The completion call includes the uploaded URI as an artifact.

```python
with JobContext(client, "etl_users", ship_logs=True, log_path="/var/log/app/run.log") as job:
    ...
# completion uploads / links the log automatically
```

## 7) Minimal implementation plan
- Phase A — Core lineage context (v1.0)
  - DatlakeClient, auth, config
  - JobContext: start/complete, log_event, get_table_latest_uri, register_snapshot
  - Optional log shipping: upload + artifact linkage
  - Solid retries and typed errors
- Phase B — Quality & ergonomics (v1.1)
  - Heartbeats, progress events
  - Better artifact helpers (JSON metrics, HTML reports)
  - Type hints, mypy, ruff; examples and docstrings
- Phase C — Data convenience (v1.2+)
  - Optional helpers for DuckDB/Polars integration
  - Detached caching (latest snapshot URI memoization)

## 8) Example end‑to‑end
```python
from datlake_sdk import DatlakeClient, JobContext

client = DatlakeClient(base_url="https://api.datlake.local", api_key="...")

with JobContext(client, job_name="daily_users", ship_logs=True) as job:
    src_uri = job.get_table_latest_uri("users_raw")
    df = load_users(src_uri)               # user code
    out_uri = write_users_curated(df)      # e.g., returns s3://...parquet
    job.register_snapshot("users_curated", out_uri, format="parquet")
    job.log_event("stats", {"users": len(df)})
# JobContext completes; if enabled, run.log uploaded and linked
```

## 9) Packaging & distribution
- `pyproject.toml` with typed package `datlake_sdk`.
- Publish to PyPI; semantic versioning.
- Docs page: `docs/sdk/python.md` with API reference and recipes.
