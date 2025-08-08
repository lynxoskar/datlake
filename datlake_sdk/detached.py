from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from .client import DatlakeClient
from .functional import Run, start_run, complete_run, DatasetRef
from .result import Result, Ok, Err
from .errors import SDKError


@dataclass
class DetachedJob:
    client: DatlakeClient
    job_name: str
    metadata: Optional[Dict[str, Any]] = None

    def start(self) -> Result[Run, SDKError]:
        return start_run(self.client, self.job_name, self.metadata)

    def complete(
        self,
        run: Run,
        *,
        success: bool,
        inputs: Optional[List[DatasetRef]] = None,
        outputs: Optional[List[DatasetRef]] = None,
        artifacts: Optional[List[Dict[str, Any]]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Result[None, SDKError]:
        meta: Dict[str, Any] = {}
        if inputs:
            meta["inputs"] = [ds.__dict__ for ds in inputs]
        if outputs:
            meta["outputs"] = [ds.__dict__ for ds in outputs]
        if artifacts:
            meta["artifacts"] = artifacts
        if extra:
            meta.update(extra)
        return complete_run(self.client, run, success=success, metadata=meta)
