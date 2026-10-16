# Copyright 2026 SovereignNexus Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
macp.backpressure
================================================================================
Gap 6: Bounded Semaphore Backpressure and Durable Fsync Observability Ledger.
Prevents system resource exhaustion and provides tamper-evident telemetry.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import threading
from typing import Any, Dict, Generator, Optional


class BackpressureLimiter:
    """Manages worker concurrency and records append-only telemetry with fsync."""

    def __init__(self, max_concurrent: int = 4, ledger_path: Optional[Path] = None) -> None:
        self.max_concurrent = max_concurrent
        self.semaphore = threading.BoundedSemaphore(max_concurrent)
        self.ledger_path = Path(ledger_path) if ledger_path else None
        if self.ledger_path:
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def throttle(self) -> Generator[None, None, None]:
        """Context manager acquiring bounded semaphore permit."""
        self.semaphore.acquire()
        try:
            yield
        finally:
            self.semaphore.release()

    def record_telemetry(
        self,
        task_id: str,
        status: str,
        summary: str,
        raw_result_bytes: bytes,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Appends a durable JSONL record synchronized to disk via os.fsync."""
        if not self.ledger_path:
            return {}

        summary_words = len(str(summary).split())
        record = {
            "task_id": task_id,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "summary_words": summary_words,
            "result_sha256": f"sha256:{hashlib.sha256(raw_result_bytes).hexdigest()}",
        }
        if extra:
            record.update(extra)

        line = (json.dumps(record, sort_keys=True) + "\n").encode("utf-8")
        fd = os.open(str(self.ledger_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, line)
            os.fsync(fd)
        finally:
            os.close(fd)

        return record
