from __future__ import annotations
import os
import time
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional
import requests

from .errors import SDKError, AuthError, NotFound, Conflict, Transient, ServerError


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    base_ms: int = 200
    jitter: bool = True


@dataclass
class ErrorPolicy:
    fail_fast: bool = True
    continue_on_not_found: bool = False
    suppress_transient: bool = False
    on_error: str = "log_only"  # log_only | raise | emit_event (future)


@dataclass
class DatlakeClient:
    base_url: str
    api_key: Optional[str] = None
    timeout: float = float(os.getenv("DATLAKE_DEFAULT_TIMEOUT_MS", "5000")) / 1000.0
    retry: RetryPolicy = RetryPolicy(
        max_attempts=int(os.getenv("DATLAKE_SDK_RETRY_MAX", "3")),
        base_ms=int(os.getenv("DATLAKE_SDK_RETRY_BASE_MS", "200")),
        jitter=os.getenv("DATLAKE_SDK_RETRY_JITTER", "true").lower() == "true",
    )
    errors: ErrorPolicy = ErrorPolicy(
        fail_fast=os.getenv("DATLAKE_SDK_ERROR_STRATEGY", "fail_fast") == "fail_fast",
        continue_on_not_found=os.getenv("DATLAKE_SDK_ERROR_STRATEGY", "fail_fast")
        == "continue_on_not_found",
        suppress_transient=os.getenv("DATLAKE_SDK_ERROR_STRATEGY", "fail_fast")
        == "suppress_transient",
        on_error=os.getenv("DATLAKE_SDK_ON_ERROR", "log_only"),
    )

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _request(self, method: str, path: str, *, json_body: Optional[Dict[str, Any]] = None) -> requests.Response:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        attempts = 0
        delay = self.retry.base_ms / 1000.0
        last_exc: Optional[Exception] = None
        while attempts < self.retry.max_attempts:
            try:
                resp = requests.request(method, url, headers=self._headers(), json=json_body, timeout=self.timeout)
                if resp.status_code >= 200 and resp.status_code < 300:
                    return resp
                # classify
                if resp.status_code in (401, 403):
                    raise AuthError("unauthorized", code=resp.status_code)
                if resp.status_code == 404:
                    raise NotFound("not found", code=resp.status_code)
                if resp.status_code == 409:
                    raise Conflict("conflict", code=resp.status_code)
                if resp.status_code >= 500:
                    raise Transient("server transient", code=resp.status_code)
                raise ServerError(f"unexpected status {resp.status_code}", code=resp.status_code)
            except Transient as te:
                last_exc = te
                attempts += 1
                if attempts >= self.retry.max_attempts:
                    if self.errors.suppress_transient:
                        # synthesize a pseudo-response with 200 + empty
                        raise ServerError("transient suppressed but exhausted", code=503)
                    raise
                sleep = delay + (delay * 0.5 * (os.urandom(1)[0] / 255.0) if self.retry.jitter else 0)
                time.sleep(sleep)
                delay *= 2
            except (AuthError, NotFound, Conflict, ServerError) as se:
                last_exc = se
                raise
            except Exception as ex:
                last_exc = ex
                raise ServerError(str(ex))
        # should not reach
        raise ServerError(str(last_exc) if last_exc else "request failed")
