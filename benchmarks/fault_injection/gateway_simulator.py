#!/usr/bin/env python3
r"""
gateway_simulator.py — Standard API Gateway Idempotency Layer (Kong / Envoy Simulation)
Sovereign Multi-Agent OS (SMAOS) / Deterministic Fault-Injection Testbed

Emulates modern API Gateway RFC-compliant idempotency behavior:
  - Stable exact-byte retries (C_1) with unchanged Idempotency-Key are deduplicated.
  - Semantic drift (C_2) alters payload bytes or regenerates the key, causing
    cache misses and passing the duplicate request straight to the backend ledger.
"""

import hashlib
import json
from typing import Dict, Any, Optional, Tuple
from starlette.testclient import TestClient


class GatewaySimulator:
    """
    Simulates an Envoy / Kong API Gateway idempotency filter.
    Caches successful and in-flight idempotent operations based on
    (Idempotency-Key, SHA256(raw_body_bytes)).
    """

    def __init__(self, backend_client: TestClient):
        self.backend = backend_client
        # Cache maps idempotency_key -> (body_hash, status_code, response_json)
        self.idempotency_cache: Dict[str, Tuple[str, int, Dict[str, Any]]] = {}
        # In-flight lock table
        self.in_flight_keys: Dict[str, str] = {}

    def reset_cache(self) -> None:
        """Clears the gateway idempotency cache."""
        self.idempotency_cache.clear()
        self.in_flight_keys.clear()

    def dispatch(
        self,
        path: str,
        json_data: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        raw_body_override: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, Dict[str, Any], Dict[str, str]]:
        """
        Dispatches request through gateway filter to backend.
        Returns: (status_code, response_data, response_headers)
        """
        req_headers = dict(headers or {})
        if idempotency_key:
            req_headers["Idempotency-Key"] = idempotency_key

        # 1. Determine raw byte payload and its SHA-256 digest
        if raw_body_override is not None:
            raw_bytes = raw_body_override
        else:
            raw_bytes = json.dumps(json_data, sort_keys=False).encode("utf-8")

        body_sha256 = hashlib.sha256(raw_bytes).hexdigest()

        # 2. Check Idempotency Cache
        if idempotency_key:
            if idempotency_key in self.idempotency_cache:
                cached_hash, cached_status, cached_json = self.idempotency_cache[idempotency_key]
                if cached_hash == body_sha256:
                    # Cache HIT: Safe deduplication (C_1)
                    return (
                        200,
                        cached_json,
                        {"X-Gateway-Cache": "HIT-IDEMPOTENT", "X-Deduplicated": "true"}
                    )
                else:
                    # Key reused with mismatched payload (Semantic Drift conflict)
                    return (
                        422,
                        {
                            "error": "UNPROCESSABLE_ENTITY",
                            "message": "Idempotency-Key reused with modified payload (semantic drift detected)",
                            "key": idempotency_key,
                        },
                        {"X-Gateway-Error": "IDEMPOTENCY_PAYLOAD_MISMATCH"}
                    )

        # 3. Cache MISS: Forward request to target backend
        response = self.backend.post(
            path,
            content=raw_bytes,
            headers={"Content-Type": "application/json", **req_headers}
        )

        resp_status = response.status_code
        try:
            resp_data = response.json()
        except Exception:
            resp_data = {"raw": response.text}

        # 4. If backend successfully committed before dropping, or succeeded:
        # Note: If backend committed and returned 200, cache it.
        # If backend injected 504 post-commit, gateway records the committed intent
        # if the client uses the same key on retry.
        if idempotency_key:
            if resp_status in (200, 201):
                self.idempotency_cache[idempotency_key] = (body_sha256, resp_status, resp_data)
            elif resp_status == 504 and response.headers.get("X-AEIB-Fault-Injected") == "POST_COMMIT_504":
                # Backend committed transaction before timing out!
                # Modern intelligent gateway records the commitment for the exact key/hash
                self.idempotency_cache[idempotency_key] = (
                    body_sha256,
                    200,
                    {
                        "status": "COMMITTED_DEDUPLICATED",
                        "note": "Reconciled from gateway cache on post-commit 504 recovery",
                        "intent_id": json_data.get("intent_id"),
                        "logical_operation_id": json_data.get("logical_operation_id"),
                    }
                )

        return resp_status, resp_data, dict(response.headers)
