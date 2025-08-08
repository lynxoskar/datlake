from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

from .client import DatlakeClient
from .functional import (
    Run,
    Artifact,
    DatasetRef,
    start_run,
    complete_run,
    fetch_latest_uri,
    register_snapshot,
    make_log_artifact,
)
from .result import Result, Ok, Err


@dataclass
class JobContext:
    client: DatlakeClient
    job_name: str
    metadata: Optional[Dict[str, Any]] = None
    ship_logs: bool = False
    log_path: Optional[str] = None
    artifact_bucket: Optional[str] = None
    track_inputs: bool = True

    _run: Optional[Run] = None
    _inputs: List[DatasetRef] = field(default_factory=list)
    _outputs: List[DatasetRef] = field(default_factory=list)

    def __enter__(self) -> "JobHandle":
        res = start_run(self.client, self.job_name, self.metadata)
        if isinstance(res, Err):
            raise RuntimeError(f"start_run failed: {res.error}")
        self._run = res.value
        return JobHandle(self, self._run)

    def __exit__(self, exc_type, exc, tb) -> None:
        success = exc is None
        artifacts: List[Artifact] = []
        if self.ship_logs and self.log_path and self.artifact_bucket and self._run:
            art = make_log_artifact(self.client, self.artifact_bucket, self._run, self.log_path)
            if isinstance(art, Ok):
                artifacts.append(art.value)
        if self._run:
            meta: Dict[str, Any] = {}
            if self._inputs:
                meta["inputs"] = [d.__dict__ for d in self._inputs]
            if self._outputs:
                meta["outputs"] = [d.__dict__ for d in self._outputs]
            complete_run(self.client, self._run, success=success, metadata=meta if meta else None)

    # Public helpers to explicitly record datasets (for detached or custom flows)
    def add_input(self, *, name: str, description: str, uri: Optional[str] = None,
                  format: Optional[str] = None, schema: Optional[Dict[str, Any]] = None,
                  tags: Optional[List[str]] = None) -> None:
        self._inputs.append(DatasetRef(name=name, description=description, uri=uri, format=format, schema=schema, tags=tags))

    def add_output(self, *, name: str, description: str, uri: Optional[str] = None,
                   format: Optional[str] = None, schema: Optional[Dict[str, Any]] = None,
                   tags: Optional[List[str]] = None) -> None:
        self._outputs.append(DatasetRef(name=name, description=description, uri=uri, format=format, schema=schema, tags=tags))


class JobHandle:
    def __init__(self, ctx: JobContext, run: Run) -> None:
        self._ctx = ctx
        self._client = ctx.client
        self._run = run

    def get_table_latest_uri(self, table_name: str, *, description: Optional[str] = None) -> str:
        res = fetch_latest_uri(self._client, self._run, table_name)
        if isinstance(res, Err):
            raise RuntimeError(str(res.error))
        uri_info = res.value
        # Auto-record as input for lineage if enabled
        if self._ctx.track_inputs:
            self._ctx.add_input(
                name=table_name,
                description=description or "latest snapshot",
                uri=uri_info.uri,
                format=uri_info.format,
                schema=uri_info.schema,
            )
        return uri_info.uri

    def register_snapshot(self, table_name: str, uri: str, *, format: str,
                          schema: Optional[Dict[str, Any]] = None,
                          description: Optional[str] = None) -> None:
        res = register_snapshot(self._client, self._run, table_name, uri, format=format, schema=schema)
        if isinstance(res, Err):
            raise RuntimeError(str(res.error))
        # Record as output for lineage
        self._ctx.add_output(
            name=table_name,
            description=description or "registered snapshot",
            uri=uri,
            format=format,
            schema=schema,
        )

    def log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        # TODO: implement events endpoint and wire here
        _ = (event_type, data)
