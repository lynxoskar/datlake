from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any

from .client import DatlakeClient
from .functional import Run, start_run, complete_run, fetch_latest_uri, register_snapshot
from .storage import download, upload
from .result import Result, Ok, Err, and_then
from .errors import SDKError


@dataclass
class DetachedIO:
    """Convenience for detached workflows: fetch inputs and publish outputs without backend storage.

    The backend only records lineage: job/run, input URIs, and output snapshots.
    """

    client: DatlakeClient
    artifact_bucket: Optional[str] = None

    # Read path: resolve latest snapshot URI via backend, then download via fsspec
    def get_latest_and_download(self, table_name: str, local_path: str, *, run: Optional[Run] = None) -> Result[str, SDKError]:
        def _download(uri_info):
            return download(uri_info.uri, local_path)
        return and_then(fetch_latest_uri(self.client, run, table_name), _download)

    # Write path: upload local file to a given external URI, then register snapshot with backend
    def upload_and_register(self, run: Run, table_name: str, local_path: str, dest_uri: str, *, format: str, schema: Optional[Dict[str, Any]] = None) -> Result[str, SDKError]:
        up = upload(local_path, dest_uri)
        if isinstance(up, Err):
            return up
        reg = register_snapshot(self.client, run, table_name, dest_uri, format=format, schema=schema)
        if isinstance(reg, Err):
            return reg  # surface registration failure
        return Ok(dest_uri)
