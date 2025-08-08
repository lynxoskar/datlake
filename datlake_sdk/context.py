from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from .client import DatlakeClient
from .functional import Run, Artifact, start_run, complete_run, fetch_latest_uri, register_snapshot, make_log_artifact
from .result import Result, Ok, Err
from .errors import SDKError


@dataclass
class JobContext:
    client: DatlakeClient
    job_name: str
    metadata: Optional[Dict[str, Any]] = None
    ship_logs: bool = False
    log_path: Optional[str] = None
    artifact_bucket: Optional[str] = None

    _run: Optional[Run] = None

    def __enter__(self) -> "JobHandle":
        res = start_run(self.client, self.job_name, self.metadata)
        if isinstance(res, Err):
            raise RuntimeError(f"start_run failed: {res.error}")
        self._run = res.value
        return JobHandle(self.client, self._run, self)

    def __exit__(self, exc_type, exc, tb) -> None:
        success = exc is None
        arts: List[Artifact] = []
        if self.ship_logs and self.log_path and self.artifact_bucket and self._run:
            art = make_log_artifact(self.client, self.artifact_bucket, self._run, self.log_path)
            if isinstance(art, Ok):
                arts.append(art.value)
        if self._run:
            complete_run(self.client, self._run, success=success, extra={"exception": str(exc)} if exc else None, artifacts=arts)


class JobHandle:
    def __init__(self, client: DatlakeClient, run: Run, ctx: JobContext) -> None:
        self._client = client
        self._run = run
        self._ctx = ctx

    def get_table_latest_uri(self, table_name: str) -> str:
        res = fetch_latest_uri(self._client, self._run, table_name)
        if isinstance(res, Err):
            raise RuntimeError(str(res.error))
        return res.value.uri

    def register_snapshot(self, table_name: str, uri: str, *, format: str, schema: Optional[Dict[str, Any]] = None) -> None:
        res = register_snapshot(self._client, self._run, table_name, uri, format=format, schema=schema)
        if isinstance(res, Err):
            raise RuntimeError(str(res.error))

    def log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        # TODO: implement event endpoint if needed; placeholder no-op for now
        _ = (event_type, data)
