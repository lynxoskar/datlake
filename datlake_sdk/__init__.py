"""Datlake SDK (functional, lineage-first)

Public surface:
- DatlakeClient
- Result, Ok, Err
- functional operations: start_run, complete_run, fetch_latest_uri, register_snapshot, upload_object, make_log_artifact
- JobContext (optional wrapper)
"""

from .result import Result, Ok, Err
from .client import DatlakeClient
from .functional import (
    start_run,
    complete_run,
    fetch_latest_uri,
    register_snapshot,
    upload_object,
    make_log_artifact,
)
from .context import JobContext

__all__ = [
    "Result",
    "Ok",
    "Err",
    "DatlakeClient",
    "start_run",
    "complete_run",
    "fetch_latest_uri",
    "register_snapshot",
    "upload_object",
    "make_log_artifact",
    "JobContext",
]
