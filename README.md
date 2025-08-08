# Datlake

Datlake is a modern, lineage‑aware data platform. It couples a FastAPI backend, a Next.js frontend, Kubernetes deployment manifests, and a Python SDK that makes lineage operations easy and safe by design.

## Quick links
- Architecture: docs/architecture/overview.md
- Backend: docs/backend/system-plan.md
- API organization: docs/backend/api-organization.md
- Infra & K8s: docs/infra/system-plan.md
- Frontend: docs/frontend/system-plan.md
- Database: docs/database/rbac.md
- SDK: docs/sdk/python.md
- Changelogs: docs/changelogs/

---

## Using the SDK for lineage‑first jobs
The Datlake Python SDK provides a friendly, safe way to run jobs with end‑to‑end lineage. It follows a functional, railway‑oriented programming style with clear `Result` types, plus an optional `JobContext` wrapper for ergonomics.

### Install
```bash
pip install datlake  # (future: datlake-sdk if split to a separate package)
```

### Minimal example: start → read → write → register → complete
```python
from datlake_sdk import DatlakeClient, JobContext

client = DatlakeClient(base_url="http://localhost:8000", api_key="<token>")

with JobContext(client, job_name="daily_users", ship_logs=True, log_path="/var/log/app/run.log", artifact_bucket="datlake-artifacts") as job:
    # Resolve latest source snapshot URI
    src_uri = job.get_table_latest_uri("users_raw")

    # Your data processing here
    df = load_users(src_uri)
    out_uri = write_users_curated(df)  # e.g., returns s3://bucket/path/file.parquet

    # Register curated output snapshot with lineage attribution to this run
    job.register_snapshot("users_curated", out_uri, format="parquet")

    # Optional custom telemetry events
    job.log_event("stats", {"rows": len(df)})
# On exit: run is completed; if enabled, run.log is uploaded and linked as an artifact
```

### Functional style (Result/ROP)
If you prefer a pure functional flow with explicit `Ok/Err` handling:
```python
from datlake_sdk import DatlakeClient
from datlake_sdk.functional import start_run, fetch_latest_uri, register_snapshot, complete_run
from datlake_sdk.result import Ok, Err, and_then

client = DatlakeClient(base_url="http://localhost:8000", api_key="<token>")

r0 = start_run(client, "daily_users")
r1 = and_then(r0, lambda run: fetch_latest_uri(client, run, "users_raw"))

# transform returns a URI as Result[str, SDKError]
transform = lambda u: Ok(write_users_curated(load_users(u.uri)))

r2 = and_then(r1, transform)
r3 = and_then(r2, lambda uri: register_snapshot(client, r0.value, "users_curated", uri, format="parquet")) if isinstance(r0, Ok) else r0

complete_run(client, r0.value, success=isinstance(r3, Ok)) if isinstance(r0, Ok) else None
```

### Configuration via environment
```bash
export DATLAKE_API_URL="http://localhost:8000"
export DATLAKE_API_KEY="<token>"
# Optional SDK policies
export DATLAKE_SDK_ERROR_STRATEGY=fail_fast   # or: continue_on_not_found | suppress_transient
export DATLAKE_SDK_RETRY_MAX=3
export DATLAKE_SDK_RETRY_BASE_MS=200
export DATLAKE_SDK_RETRY_JITTER=true
```

---

## Backend REST API (brief)
The REST API is versioned under `/api/v1` and secured with bearer tokens.

- Base URL: `http://localhost:8000`
- Auth: `Authorization: Bearer <token>`
- Content: JSON request/response unless noted

### Jobs & runs (lineage core)
- Start a run
  ```bash
  curl -s -X POST \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    "$API/api/v1/jobs/daily_users/runs" \
    -d '{"metadata": {"source": "s3"}}'
  # => { "run_id": "...", "job_name": "daily_users", ... }
  ```
- Complete a run
  ```bash
  curl -s -X PUT \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    "$API/api/v1/jobs/daily_users/runs/$RUN_ID/complete" \
    -d '{"success": true, "artifacts": [{"type": "log", "uri": "s3://.../run.log"}]}'
  ```

### Tables (reads)
- Resolve latest snapshot
  ```bash
  curl -s -H "Authorization: Bearer $TOKEN" \
    "$API/api/v1/tables/users_raw/snapshots/latest"
  # => { "table_name":"users_raw", "uri":"s3://...", "format":"parquet", "schema": {...} }
  ```

### Snapshots (writes)
- Register an output snapshot
  ```bash
  curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    "$API/api/v1/jobs/register-snapshot" \
    -d '{"table_name":"users_curated","uri":"s3://...","format":"parquet","schema":null,"job_name":"daily_users","run_id":"'$RUN_ID'"}'
  ```

### Datasets (artifacts)
- Upload a log artifact (SDK wraps this)
  ```bash
  curl -s -X PUT -H "Authorization: Bearer $TOKEN" \
    --data-binary @run.log \
    "$API/api/v1/datasets/datlake-artifacts/jobs/daily_users/$RUN_ID/run.log"
  ```

### Events (SSE)
- Stream events for live monitoring
  ```bash
  curl -N -H "Accept: text/event-stream" "$API/api/v1/events/stream?events=job_status,lineage_event"
  ```

### Health & admin
- Health: `GET $API/health` (alias) or `GET $API/api/v1/admin/health`
- Config summary: `GET $API/api/v1/admin/config/summary`

For a full description and the source of truth, see docs/backend/api-organization.md (OpenAPI).

---

## Contributing
- See docs/architecture/overview.md and docs/backend/system-plan.md to understand the moving parts.
- The SDK plan and examples live at docs/sdk/python.md.
- Please open issues or PRs with a clear description and reproduction steps.

## License (MIT)
Copyright (c) 2025 Datlake

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
