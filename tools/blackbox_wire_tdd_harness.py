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
tools/blackbox_wire_tdd_harness.py — Declarative Wire Conformance & Local Digital Twin Harness.

Combines:
1. CockroachDB / SQLite declarative data-driven wire testing (zero internal class coupling).
2. Trip.com AREX / Stripe-Mock stateful local Digital Twin HTTP server running on a real
   OS TCP socket (127.0.0.1:0) seeded strictly with our own synthetic data.
3. Clean-room black-box verification: any Python, Rust, or Swift binary implementing the
   wire contract can be swapped in and verified without modifying test assertions.
"""

import argparse
import hashlib
import hmac
import http.client
import json
import os
import sys
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VECTORS_PATH = REPO_ROOT / "evidence" / "conformance_vectors_v1.jsonl"


# ============================================================================
# 1. REAL LOCAL DIGITAL-TWIN SERVER (100% Our Own Data, Real TCP Socket)
# ============================================================================
@dataclass
class TwinBankDataset:
    """Self-contained synthetic dataset owned locally (zero external APIs)."""

    pinned_accounts: Dict[str, int] = field(
        default_factory=lambda: {
            "iban:DE89370400440532013000": 0,
            "iban:FR7630006000011234567890189": 0,
        }
    )
    # Deterministic fault rules keyed by operation_id:
    # "COMMIT_THEN_504" -> server mutates balance (commits), but returns HTTP 504 to caller!
    # "ABORT_THEN_504"  -> server does NOT mutate balance, returns HTTP 504 to caller!
    fault_rules: Dict[str, str] = field(
        default_factory=lambda: {
            "op-ambiguous-committed": "COMMIT_THEN_504",
            "op-ambiguous-aborted": "ABORT_THEN_504",
        }
    )
    committed_idempotency_keys: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    raw_mutation_count: int = 0
    duplicate_mutation_bugs: int = 0


class _TwinBankHttpHandler(BaseHTTPRequestHandler):
    dataset: TwinBankDataset
    lock: threading.Lock

    def log_message(self, format: str, *args: Any) -> None:
        pass  # Keep test output clean

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/v1/refunds":
            self._send_json(404, {"error": "NOT_FOUND"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length)
        req = json.loads(raw_body.decode("utf-8"))

        op_id = req["operation_id"]
        rcpt = req["recipient"]
        amt = int(req["amount_minor"])

        with self.lock:
            rule = self.dataset.fault_rules.get(op_id, "NORMAL_200")

            if rule == "ABORT_THEN_504":
                # Downstream failed before commit, returns HTTP 504
                self._send_json(504, {"error": "GATEWAY_TIMEOUT", "operation_id": op_id})
                return

            # Otherwise mutation lands on the bank ledger
            if op_id in self.dataset.committed_idempotency_keys:
                self.dataset.duplicate_mutation_bugs += 1
            else:
                self.dataset.raw_mutation_count += 1
                self.dataset.pinned_accounts[rcpt] = (
                    self.dataset.pinned_accounts.get(rcpt, 0) + amt
                )
                self.dataset.committed_idempotency_keys[op_id] = {
                    "amount_minor": amt,
                    "operation_id": op_id,
                    "recipient": rcpt,
                    "status": "SETTLED",
                }

            if rule == "COMMIT_THEN_504":
                # Downstream succeeded, but response timed out
                self._send_json(504, {"error": "GATEWAY_TIMEOUT", "operation_id": op_id})
                return

            self._send_json(
                200,
                {
                    "operation_id": op_id,
                    "status": "SETTLED",
                    "settled_amount_minor": amt,
                },
            )

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/v1/refund_status":
            self._send_json(404, {"error": "NOT_FOUND"})
            return

        qs = urllib.parse.parse_qs(parsed.query)
        op_id = qs.get("operation_id", [""])[0]

        with self.lock:
            if op_id in self.dataset.committed_idempotency_keys:
                self._send_json(200, self.dataset.committed_idempotency_keys[op_id])
            else:
                self._send_json(200, {"operation_id": op_id, "status": "NOT_FOUND_REFUTED"})


class RealLocalPaymentTwinServer:
    """Manages lifecycle of the real TCP HTTP server on 127.0.0.1:0."""

    def __init__(self, dataset: Optional[TwinBankDataset] = None) -> None:
        self.dataset = dataset or TwinBankDataset()
        self.lock = threading.Lock()

        class BoundHandler(_TwinBankHttpHandler):
            pass

        BoundHandler.dataset = self.dataset
        BoundHandler.lock = self.lock

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), BoundHandler)
        self.host, self.port = self._httpd.server_address
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def __enter__(self) -> "RealLocalPaymentTwinServer":
        self._thread.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


# ============================================================================
# 2. CLEAN-ROOM REVERSE-ENGINEERED BLACK BOX (Driven Strictly by Wire Specs)
# ============================================================================
class CleanRoomBlackBoxEngine:
    """
    Clean-room implementation built strictly to satisfy the Black-Box Wire Contract:
    - Input: raw JSON wire bytes (`action`: "DISPATCH" | "RECONCILE" | "INSPECT_STATE")
    - Output: deterministic canonical JSON response bytes
    """

    def __init__(
        self,
        target_host: str,
        target_port: int,
        sprint_ceiling_minor: int,
        pinned_recipients: Set[str],
        shared_secret_key: bytes,
    ) -> None:
        self.target_host = target_host
        self.target_port = target_port
        self.sprint_ceiling_minor = sprint_ceiling_minor
        self.pinned_recipients = frozenset(pinned_recipients)
        self.shared_secret_key = shared_secret_key

        self.escrowed_minor = 0
        self.settled_minor = 0
        self.operations: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _canonical_bytes(obj: Dict[str, Any]) -> bytes:
        return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def compute_caid_token(self, op_id: str, amount_minor: int, recipient: str) -> str:
        msg = self._canonical_bytes(
            {"amount_minor": amount_minor, "operation_id": op_id, "recipient": recipient}
        )
        return hmac.new(self.shared_secret_key, msg, hashlib.sha256).hexdigest()

    def handle_wire_frame(self, raw_frame: bytes) -> bytes:
        try:
            req = json.loads(raw_frame.decode("utf-8", errors="strict"))
        except Exception:
            return self._canonical_bytes(
                {"disposition": "NOT_DISPATCHED", "error_code": "ERR_MALFORMED_WIRE_FRAME"}
            )

        if not isinstance(req, dict):
            return self._canonical_bytes(
                {"disposition": "NOT_DISPATCHED", "error_code": "ERR_INVALID_SCHEMA"}
            )

        action = req.get("action")
        if action == "INSPECT_STATE":
            return self._canonical_bytes(
                {
                    "escrowed_minor": self.escrowed_minor,
                    "settled_minor": self.settled_minor,
                    "total_exposure_minor": self.escrowed_minor + self.settled_minor,
                }
            )

        if action == "RECONCILE":
            op_id = str(req.get("operation_id", ""))
            if op_id not in self.operations:
                return self._canonical_bytes({"error_code": "ERR_UNKNOWN_OP", "status": "ERROR"})
            op = self.operations[op_id]
            if op["state"] != "EFFECT_INDETERMINATE":
                return self._canonical_bytes(
                    {"error_code": "ERR_NOT_INDETERMINATE", "status": "ERROR"}
                )

            # Query the real local TCP twin server's status endpoint
            conn = http.client.HTTPConnection(self.target_host, self.target_port, timeout=2.0)
            conn.request("GET", f"/v1/refund_status?operation_id={urllib.parse.quote(op_id)}")
            resp = conn.getresponse()
            data = json.loads(resp.read().decode("utf-8"))
            conn.close()

            amt = op["amount_minor"]
            if data.get("status") == "SETTLED":
                self.escrowed_minor -= amt
                self.settled_minor += amt
                op["state"] = "CONFIRMED"
                return self._canonical_bytes({"disposition": "CONFIRMED", "operation_id": op_id})
            else:
                self.escrowed_minor -= amt
                op["state"] = "REFUTED"
                return self._canonical_bytes({"disposition": "REFUTED", "operation_id": op_id})

        # Default action: DISPATCH
        op_id = req.get("operation_id")
        amt = req.get("amount_minor")
        rcpt = req.get("recipient")
        caid_token = req.get("caid_token", "")

        if (
            not isinstance(op_id, str)
            or isinstance(amt, bool)
            or not isinstance(amt, int)
            or amt <= 0
            or not isinstance(rcpt, str)
        ):
            return self._canonical_bytes(
                {"disposition": "NOT_DISPATCHED", "error_code": "ERR_INVALID_SCHEMA"}
            )

        if op_id in self.operations:
            prior_state = self.operations[op_id]["state"]
            code = (
                "HALT_BLIND_RETRY_PROHIBITED"
                if prior_state == "EFFECT_INDETERMINATE"
                else "ERR_DUPLICATE_OPERATION_ID"
            )
            return self._canonical_bytes({"disposition": "NOT_DISPATCHED", "error_code": code})

        expected_token = self.compute_caid_token(op_id, amt, rcpt)
        if not hmac.compare_digest(expected_token, str(caid_token)):
            return self._canonical_bytes(
                {"disposition": "NOT_DISPATCHED", "error_code": "ERR_CAID_OR_PAYEE_MISMATCH"}
            )

        if rcpt not in self.pinned_recipients:
            return self._canonical_bytes(
                {"disposition": "NOT_DISPATCHED", "error_code": "ERR_UNPINNED_RECIPIENT"}
            )

        if self.escrowed_minor + self.settled_minor + amt > self.sprint_ceiling_minor:
            return self._canonical_bytes(
                {"disposition": "NOT_DISPATCHED", "error_code": "HALT_SPRINT_LIMIT_EXCEEDED"}
            )

        # Reserve in escrow BEFORE socket transmission
        self.escrowed_minor += amt
        self.operations[op_id] = {"amount_minor": amt, "recipient": rcpt, "state": "DISPATCHED"}

        # Transmit over real TCP socket to the local twin server
        conn = http.client.HTTPConnection(self.target_host, self.target_port, timeout=2.0)
        wire_body = self._canonical_bytes(
            {"amount_minor": amt, "operation_id": op_id, "recipient": rcpt}
        )
        conn.request(
            "POST",
            "/v1/refunds",
            body=wire_body,
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        _ = resp.read()
        status_code = resp.status
        conn.close()

        if status_code == 200:
            self.escrowed_minor -= amt
            self.settled_minor += amt
            self.operations[op_id]["state"] = "CONFIRMED"
            return self._canonical_bytes({"disposition": "CONFIRMED", "operation_id": op_id})

        # Ambiguous timeout -> Latch EFFECT_INDETERMINATE!
        self.operations[op_id]["state"] = "EFFECT_INDETERMINATE"
        return self._canonical_bytes(
            {"disposition": "EFFECT_INDETERMINATE", "operation_id": op_id}
        )


# ============================================================================
# 3. DECLARATIVE JSONL VECTOR RUNNER
# ============================================================================
def execute_declarative_vectors(
    vectors_path: Path,
    engine: CleanRoomBlackBoxEngine,
    twin_server: RealLocalPaymentTwinServer,
) -> Dict[str, Any]:
    """
    Executes a stream of declarative JSONL vectors against the engine under test.
    """
    if not vectors_path.exists():
        raise FileNotFoundError(f"Vectors file not found: {vectors_path}")

    results = []
    with open(vectors_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            vec = json.loads(line)
            vec_id = vec["vector_id"]

            # Configure twin server fault rule if specified
            if "twin_fault_rule" in vec and "inbound_obj" in vec:
                op_id = vec["inbound_obj"].get("operation_id")
                if op_id:
                    twin_server.dataset.fault_rules[op_id] = vec["twin_fault_rule"]

            # Prepare inbound wire frame
            if "inbound_raw" in vec:
                inbound_bytes = vec["inbound_raw"].encode("utf-8")
            else:
                obj = dict(vec["inbound_obj"])
                # Inject valid caid_token if not explicitly simulating a mismatch
                if obj.get("action") == "DISPATCH" and obj.get("caid_token") is None:
                    obj["caid_token"] = engine.compute_caid_token(
                        obj["operation_id"], obj["amount_minor"], obj["recipient"]
                    )
                inbound_bytes = json.dumps(obj).encode("utf-8")

            # Execute wire call
            t0 = time.perf_counter()
            out_bytes = engine.handle_wire_frame(inbound_bytes)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            out_obj = json.loads(out_bytes.decode("utf-8"))
            expected_out = vec["expected_outbound"]

            # Verify response matches expected outbound frame
            assert out_obj == expected_out, (
                f"Vector {vec_id} (line {line_num}) failed:\n"
                f"  Expected: {expected_out}\n"
                f"  Observed: {out_obj}"
            )

            # Verify state inspection if specified
            if "expected_state" in vec:
                state_bytes = engine.handle_wire_frame(b'{"action":"INSPECT_STATE"}')
                state_obj = json.loads(state_bytes.decode("utf-8"))
                assert state_obj == vec["expected_state"], (
                    f"Vector {vec_id} state mismatch:\n"
                    f"  Expected: {vec['expected_state']}\n"
                    f"  Observed: {state_obj}"
                )

            results.append(
                {
                    "vector_id": vec_id,
                    "elapsed_ms": round(elapsed_ms, 3),
                    "status": "PASS",
                }
            )

    # Invariant: 0 duplicate mutations on the real twin server
    assert twin_server.dataset.duplicate_mutation_bugs == 0, (
        f"Observed {twin_server.dataset.duplicate_mutation_bugs} duplicate mutations on Twin Server!"
    )

    return {
        "status": "PASS",
        "total_vectors": len(results),
        "results": results,
        "twin_raw_mutations": twin_server.dataset.raw_mutation_count,
        "twin_duplicate_bugs": twin_server.dataset.duplicate_mutation_bugs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Black-Box Wire TDD & Real Local Digital Twin Harness."
    )
    parser.add_argument(
        "--vectors-file",
        type=Path,
        default=DEFAULT_VECTORS_PATH,
        help="Path to declarative JSONL test vectors",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Execute internal verification test suite",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit results as structured JSON",
    )
    args = parser.parse_args()

    with RealLocalPaymentTwinServer() as twin:
        engine = CleanRoomBlackBoxEngine(
            target_host=twin.host,
            target_port=twin.port,
            sprint_ceiling_minor=1000_00,
            pinned_recipients={"iban:DE89370400440532013000"},
            shared_secret_key=b"clean-room-wire-secret-2026",
        )

        res = execute_declarative_vectors(args.vectors_file, engine, twin)

        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print("=" * 76)
            print("  BLACK-BOX INTERFACE TDD & REAL LOCAL TWIN SERVER RESULTS")
            print("=" * 76)
            for r in res["results"]:
                print(f"  [✓] {r['vector_id']:<32} : {r['elapsed_ms']:6.3f} ms | PASS")
            print("-" * 76)
            print(f"  Total Vectors Evaluated : {res['total_vectors']}")
            print(f"  Downstream Mutations    : {res['twin_raw_mutations']}")
            print(f"  Duplicate Mutations     : {res['twin_duplicate_bugs']} (0 expected)")
            print(f"  Overall Status          : {res['status']}")
            print("=" * 76)

    return 0


if __name__ == "__main__":
    sys.exit(main())
