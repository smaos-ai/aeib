#!/usr/bin/env python3
r"""
middleware.py — Deterministic Post-Commit Fault-Injection Engine
Sovereign Multi-Agent OS (SMAOS) / Deterministic Fault-Injection Testbed

Injects transport-layer ambiguity (HTTP 504 Gateway Timeout or TCP drops)
*after* the target ledger transaction has already committed to persistent store.
This directly reproduces the double-mutation trap:
  [ POST /debit ] -> [ Commit to SQLite OK ] -> [ Wait 5ms ] -> [ 504 Gateway Timeout ]
"""

import time
import json
from dataclasses import dataclass, field
from typing import Callable, Optional, Dict, Any
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse


@dataclass
class FaultConfig:
    """Configurable parameters for deterministic fault injection."""
    enabled: bool = True
    fault_mode: str = "POST_COMMIT_504"  # 'POST_COMMIT_504', 'POST_COMMIT_DROP', 'NONE'
    post_commit_delay_ms: float = 5.0
    target_path: str = "/debit"
    trigger_count: int = 0
    max_faults_per_intent: int = 1  # Injects fault on 1st attempt, subsequent retries may pass if configured
    fault_every_attempt: bool = False  # If True, always faults regardless of attempt count


class DeterministicFaultMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware for injecting precise, timed transport failures
    post-commit on specified mutating endpoints.
    """

    def __init__(self, app, config: Optional[FaultConfig] = None):
        super().__init__(app)
        self.config = config or FaultConfig()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if fault injection applies to this request
        should_intercept = (
            self.config.enabled
            and request.url.path == self.config.target_path
            and request.method == "POST"
            and self.config.fault_mode != "NONE"
        )

        if not should_intercept:
            return await call_next(request)

        # Allow client or header to specify attempt counter
        attempt_header = request.headers.get("X-Attempt-Count", "1")
        try:
            attempt_num = int(attempt_header)
        except ValueError:
            attempt_num = 1

        # Check if we should fault on this attempt
        should_fault = self.config.fault_every_attempt or (attempt_num <= self.config.max_faults_per_intent)

        if not should_fault:
            return await call_next(request)

        # Execute target endpoint (which commits the debit transaction)
        response = await call_next(request)

        # If endpoint successfully processed (e.g. 200 or 201), inject post-commit fault!
        if response.status_code in (200, 201):
            if self.config.post_commit_delay_ms > 0:
                time.sleep(self.config.post_commit_delay_ms / 1000.0)

            self.config.trigger_count += 1

            if self.config.fault_mode == "POST_COMMIT_504":
                return JSONResponse(
                    status_code=504,
                    content={
                        "error": "GATEWAY_TIMEOUT",
                        "code": 504,
                        "message": "Upstream transport dropped connection post-commit before HTTP 200 acknowledgment",
                        "injected_fault": True,
                        "delay_ms": self.config.post_commit_delay_ms,
                    },
                    headers={"X-AEIB-Fault-Injected": "POST_COMMIT_504"}
                )
            elif self.config.fault_mode == "POST_COMMIT_DROP":
                # Returns 502/504 Bad Gateway / Connection Dropped
                return JSONResponse(
                    status_code=502,
                    content={
                        "error": "BAD_GATEWAY_TCP_RST",
                        "code": 502,
                        "message": "TCP socket reset by peer post-commit",
                        "injected_fault": True,
                    },
                    headers={"X-AEIB-Fault-Injected": "POST_COMMIT_DROP"}
                )

        return response
