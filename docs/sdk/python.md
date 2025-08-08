# Datlake Python SDK — Lineage‑First, Functional/ROP System Plan (v1)

## 1) Goals and scope
- Primary goal: make it trivial for users and services to run lineage‑tracked jobs against Datlake.
- Programming model: functional, Railway‑Oriented Programming (ROP) with explicit `Result` types for predictable control flow and configurable error handling.
- Provide pure, composable functions for: starting a job run, fetching data URIs, registering snapshots, completing a run, and (optionally) shipping a log artifact.
- Keep an optional imperative `JobContext` wrapper for users who prefer `with` semantics, implemented on top of the functional core.

## 2) Functional core: Result types and combinators

### 2.1 Result type
```python
from dataclasses import dataclass
from typing import Generic, TypeVar, Callable, Union

T = TypeVar("T")
E = TypeVar("E")

@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T

@dataclass(frozen=True)
class Err(Generic[E]):
    error: E

Result = Union[Ok[T], Err[E]]
```

### 2.2 Combinators
```python
def map(result: Result[T, E], f: Callable[[T], T]) -> Result[T, E]:
    return Ok(f(result.value)) if isinstance(result, Ok) else result

def map_err(result: Result[T, E], f: Callable[[E], E]) -> Result[T, E]:
    return Err(f(result.error)) if isinstance(result, Err) else result

def and_then(result: Result[T, E], f: Callable[[T], Result[T, E]]) -> Result[T, E]:
    return f(result.value) if isinstance(result, Ok) else result

def tee(result: Result[T, E], f: Callable[[T], None]) -> Result[T, E]:
    if isinstance(result, Ok):
        f(result.value)
    return result

def recover(result: Result[T, E], f: Callable[[E], Result[T, E]]) -> Result[T, E]:
    return f(result.error) if isinstance(result, Err) else result
```

## 3) Functional SDK surface (pure orchestration)

### Types
```python
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

@dataclass
class Run:
    job_name: str
    run_id: str

@dataclass
class UriInfo:
    table_name: str
    uri: str
    format: str
    schema: Optional[Dict[str, Any]]

@dataclass
class SnapshotInfo:
    table_name: str
    snapshot_id: str
    uri: str

@dataclass
class Artifact:
    type: str  # e.g. "log"
    uri: str
```

### Functional operations
```python
# All functions return Result[Ok(...)/Err(...)] and never raise for expected failures

def start_run(client, job_name: str, metadata: Optional[Dict[str, Any]] = None) -> Result[Run, SDKError]:
    ...  # POST /api/v1/jobs/{job}/runs

def complete_run(client, run: Run, success: bool, extra: Optional[Dict[str, Any]] = None,
                 artifacts: Optional[List[Artifact]] = None) -> Result[None, SDKError]:
    ...  # PUT /api/v1/jobs/{job}/runs/{run_id}/complete

def fetch_latest_uri(client, run: Optional[Run], table_name: str) -> Result[UriInfo, SDKError]:
    ...  # GET /api/v1/tables/{table}/snapshots/latest

def register_snapshot(client, run: Run, table_name: str, uri: str, *,
                      format: str, schema: Optional[Dict[str, Any]] = None) -> Result[SnapshotInfo, SDKError]:
    ...  # POST /api/v1/jobs/register-snapshot

def upload_object(client, bucket: str, object_name: str, file_path: str) -> Result[str, SDKError]:
    ...  # PUT /api/v1/datasets/{bucket}/{object}

# Convenience: attach log for shipment on completion

def make_log_artifact(bucket: str, run: Run, local_log_path: str) -> Result[Artifact, SDKError]:
    object_name = f"jobs/{run.job_name}/{run.run_id}/run.log"
    return map(upload_object(client=None, bucket=bucket, object_name=object_name, file_path=local_log_path),
               lambda uri: Artifact(type="log", uri=uri))
```

## 4) Configurable error handling (policy‑driven)

The SDK reads policies from environment variables or a config file and applies them inside the HTTP layer and combinators.

- `DATLAKE_SDK_ERROR_STRATEGY`:
  - `fail_fast` (default): first `Err` aborts the pipeline; caller decides on `complete_run` with `success=False`.
  - `continue_on_not_found`: convert specific 404 lookups (e.g., `fetch_latest_uri`) into `Ok(None)` or a sentinel to continue with defaults.
  - `suppress_transient`: auto‑retry transient classes and downgrade to warnings if still failing.
- `DATLAKE_SDK_RETRY` (e.g., `max=3,base_ms=200,jitter=true`): applies to idempotent requests.
- `DATLAKE_SDK_ON_ERROR` (e.g., `log_only`, `raise`, `emit_event`): how the SDK reacts internally; still surfaces `Result` to the caller.

Policy application example
```python
res = fetch_latest_uri(client, run, "users_raw")
res = recover(res, lambda e: Ok(UriInfo("users_raw", uri="", format="", schema=None))
              if (policy.continue_on_not_found and e.code == 404) else Err(e))
```

## 5) Railway examples

### 5.1 Read‑transform‑write pipeline
```python
from datlake_sdk import DatlakeClient
from datlake_sdk.functional import start_run, fetch_latest_uri, register_snapshot, complete_run, and_then, map, tee, Err, Ok

client = DatlakeClient(base_url=..., api_key=...)

# 1) Start
r0 = start_run(client, "daily_users", metadata={"source": "s3"})

# 2) Fetch latest source
r1 = and_then(r0, lambda run: fetch_latest_uri(client, run, "users_raw"))

# 3) Load & transform (user function returns uri of output)

def process(u: UriInfo) -> Result[str, SDKError]:
    try:
        df = load_users(u.uri)
        out_uri = write_users_curated(df)  # s3://...
        return Ok(out_uri)
    except Exception as ex:
        return Err(SDKError.from_exception(ex))

r2 = and_then(r1, process)

# 4) Register snapshot
r3 = and_then(r2, lambda out_uri: register_snapshot(client, r0.value, "users_curated", out_uri, format="parquet"))

# 5) Complete (success based on chain result)
if isinstance(r3, Ok):
    complete_run(client, r0.value, success=True)
else:
    complete_run(client, r0.value, success=False, extra={"error": str(r3.error)})
```

### 5.2 Shipping a log artifact (opt‑in)
```python
if ship_logs and isinstance(r0, Ok):
    art = make_log_artifact(artifact_bucket, r0.value, "/var/log/app/run.log")
    arts = [art.value] if isinstance(art, Ok) else []
    complete_run(client, r0.value, success=isinstance(r3, Ok), artifacts=arts)
```

## 6) Backend endpoints (normalized intent)
- POST `/api/v1/jobs/{job_name}/runs`
- PUT  `/api/v1/jobs/{job_name}/runs/{run_id}/complete`
- GET  `/api/v1/tables/{table}/snapshots/latest`
- POST `/api/v1/jobs/register-snapshot`
- PUT  `/api/v1/datasets/{bucket}/{object}` (artifact upload)

## 7) Imperative wrapper (optional)
`JobContext` remains available, internally delegating to the functional operations and policies. It exposes the same behavior but hides `Result` from basic users.

## 8) Errors, retries, and observability
- Typed errors with categories: `AuthError`, `NotFound`, `Conflict`, `Transient`, `ServerError`.
- Per‑operation idempotency keys where applicable; safe retries with exponential backoff + jitter.
- Correlation headers (`X-Request-Id`) and run_id propagation; optional `events` on errors based on policy.

## 9) Packaging & roadmap
- v1.0: functional core + policies + imperative wrapper + examples.
- v1.1: heartbeats, progress events, richer artifact types, structured metrics helpers.
- v1.2+: detached caching and optional DuckDB/Polars helpers.
