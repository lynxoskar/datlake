from __future__ import annotations
from typing import Tuple, Optional
from urllib.parse import urlparse
from pathlib import Path

from .result import Result, Ok, Err
from .errors import SDKError, ServerError


def _get_fs_for_uri(uri: str):
    import fsspec  # type: ignore
    parsed = urlparse(uri)
    protocol = parsed.scheme or "file"
    # Basic S3/MinIO endpoint override via env is handled by fsspec if set (AWS_* or S3_* envs)
    fs = fsspec.filesystem(protocol)
    path = uri if protocol != "file" else parsed.path
    return fs, path


def download(uri: str, local_path: str) -> Result[str, SDKError]:
    """Download an object at URI to a local path. Returns the local path on success."""
    try:
        fs, path = _get_fs_for_uri(uri)
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        with fs.open(path, "rb") as src, open(local_path, "wb") as dst:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
        return Ok(str(local_path))
    except Exception as ex:
        return Err(ServerError(f"download failed: {ex}"))


def upload(local_path: str, uri: str) -> Result[str, SDKError]:
    """Upload a local file to the given URI. Returns the URI on success."""
    try:
        fs, path = _get_fs_for_uri(uri)
        with open(local_path, "rb") as src, fs.open(path, "wb") as dst:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
        return Ok(uri)
    except Exception as ex:
        return Err(ServerError(f"upload failed: {ex}"))
