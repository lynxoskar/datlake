from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from .client import DatlakeClient
from .errors import SDKError, NotFound, ServerError
from .result import Result, Ok, Err


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
    type: str
    uri: str


def _safe_json(resp) -> Result[Dict[str, Any], SDKError]:
    try:
        return Ok(resp.json())
    except Exception as ex:
        return Err(ServerError(f"invalid json: {ex}"))


def start_run(client: DatlakeClient, job_name: str, metadata: Optional[Dict[str, Any]] = None) -> Result[Run, SDKError]:
    try:
        payload = {"metadata": metadata or {}}
        resp = client._request("POST", f"/api/v1/jobs/{job_name}/runs", json_body=payload)
        j = _safe_json(resp)
        if isinstance(j, Err):
            return j
        run_id = j.value.get("run_id") or j.value.get("id")
        if not run_id:
            return Err(ServerError("missing run_id in response"))
        return Ok(Run(job_name=job_name, run_id=str(run_id)))
    except SDKError as e:
        return Err(e)
    except Exception as ex:
        return Err(ServerError(str(ex)))


def complete_run(
    client: DatlakeClient,
    run: Run,
    success: bool,
    extra: Optional[Dict[str, Any]] = None,
    artifacts: Optional[List[Artifact]] = None,
) -> Result[None, SDKError]:
    try:
        payload: Dict[str, Any] = {"success": success}
        if extra:
            payload["extra"] = extra
        if artifacts:
            payload["artifacts"] = [artifact.__dict__ for artifact in artifacts]
        client._request("PUT", f"/api/v1/jobs/{run.job_name}/runs/{run.run_id}/complete", json_body=payload)
        return Ok(None)
    except SDKError as e:
        return Err(e)
    except Exception as ex:
        return Err(ServerError(str(ex)))


def fetch_latest_uri(client: DatlakeClient, run: Optional[Run], table_name: str) -> Result[UriInfo, SDKError]:
    try:
        resp = client._request("GET", f"/api/v1/tables/{table_name}/snapshots/latest")
        j = _safe_json(resp)
        if isinstance(j, Err):
            return j
        value = j.value
        uri = value.get("uri")
        fmt = value.get("format", "")
        schema = value.get("schema")
        if not uri:
            return Err(NotFound("latest snapshot uri not found", code=404))
        return Ok(UriInfo(table_name=table_name, uri=uri, format=fmt, schema=schema))
    except SDKError as e:
        return Err(e)
    except Exception as ex:
        return Err(ServerError(str(ex)))


def register_snapshot(
    client: DatlakeClient,
    run: Run,
    table_name: str,
    uri: str,
    *,
    format: str,
    schema: Optional[Dict[str, Any]] = None,
) -> Result[SnapshotInfo, SDKError]:
    try:
        payload = {
            "table_name": table_name,
            "uri": uri,
            "format": format,
            "schema": schema,
            "job_name": run.job_name,
            "run_id": run.run_id,
        }
        resp = client._request("POST", "/api/v1/jobs/register-snapshot", json_body=payload)
        j = _safe_json(resp)
        if isinstance(j, Err):
            return j
        snap_id = j.value.get("snapshot_id") or j.value.get("id") or ""
        return Ok(SnapshotInfo(table_name=table_name, snapshot_id=str(snap_id), uri=uri))
    except SDKError as e:
        return Err(e)
    except Exception as ex:
        return Err(ServerError(str(ex)))


def upload_object(client: DatlakeClient, bucket: str, object_name: str, file_path: str) -> Result[str, SDKError]:
    try:
        # Use PUT; for simplicity, read file in memory (could be streamed)
        with open(file_path, "rb") as f:
            import requests

            url = f"{client.base_url.rstrip('/')}/api/v1/datasets/{bucket}/{object_name}"
            headers = client._headers()
            resp = requests.put(url, data=f, headers=headers, timeout=client.timeout)
            if 200 <= resp.status_code < 300:
                # Assume backend returns URI or we can construct it
                return Ok(f"s3://{bucket}/{object_name}")
            if resp.status_code == 404:
                return Err(NotFound("bucket or path not found", code=404))
            if resp.status_code >= 500:
                return Err(ServerError("server error", code=resp.status_code))
            return Err(SDKError(f"upload failed: {resp.status_code}", code=resp.status_code))
    except SDKError as e:
        return Err(e)
    except Exception as ex:
        return Err(ServerError(str(ex)))


def make_log_artifact(client: DatlakeClient, bucket: str, run: Run, local_log_path: str) -> Result[Artifact, SDKError]:
    obj = f"jobs/{run.job_name}/{run.run_id}/run.log"
    up = upload_object(client, bucket, obj, local_log_path)
    if isinstance(up, Err):
        return up
    return Ok(Artifact(type="log", uri=up.value))
