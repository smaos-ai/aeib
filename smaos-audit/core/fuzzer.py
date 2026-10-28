#!/usr/bin/env python3
"""
SMAOS Fault-Injecting Proxy (Moat 1)
Sovereign Multi-Agent OS (SMAOS) / STAR Protocol v1.1.0

Intercepts agent HTTP/wire traffic, injects 6 deterministic/probabilistic
wire-level transport faults (504 Timeout, TCP RST, 409 Conflict, Delay/Jitter,
Malformed Payload, Silent Drop), and records physical wire-facts to SQLite.

Zero external dependencies (pure Python standard library).
"""

import argparse
import hashlib
import http.server
import json
import os
import random
import socket
import sqlite3
import sys
import threading
import time
from typing import Any, Dict, Optional, Tuple

DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS wire_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    action_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    payload_digest TEXT NOT NULL,
    fault_mode TEXT NOT NULL,
    wire_http_status INTEGER,
    wire_fact TEXT NOT NULL,
    raw_payload TEXT
);

CREATE TABLE IF NOT EXISTS agent_dispositions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id TEXT NOT NULL,
    claimed_disposition TEXT NOT NULL,
    wire_event_id INTEGER,
    verdict TEXT NOT NULL,
    overclaimed INTEGER NOT NULL,
    FOREIGN KEY(wire_event_id) REFERENCES wire_events(id)
);
"""

FAULT_MODES = [
    "NONE",
    "TIMEOUT_504",
    "TCP_RST",
    "CONFLICT_409",
    "DELAY_JITTER",
    "MALFORMED_INVALID",
    "SILENT_DROP",
]


class FuzzerState:
    def __init__(self, db_path: str = "fuzzer_traces.db"):
        self.db_path = db_path
        self.active_fault = "TIMEOUT_504"
        self.fault_rate = 1.0
        self.timeout_delay_ms = 500
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(DB_SCHEMA)

    def log_wire_event(
        self,
        action_id: str,
        endpoint: str,
        payload_digest: str,
        fault_mode: str,
        status: Optional[int],
        wire_fact: str,
        raw_payload: str,
    ) -> int:
        with self.lock, sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO wire_events (timestamp, action_id, endpoint, payload_digest, fault_mode, wire_http_status, wire_fact, raw_payload)
                VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, ?)
                """,
                (action_id, endpoint, payload_digest, fault_mode, status, wire_fact, raw_payload),
            )
            return cursor.lastrowid

    def log_agent_disposition(
        self,
        action_id: str,
        claimed_disposition: str,
        wire_event_id: Optional[int] = None,
    ) -> Tuple[str, bool]:
        with self.lock, sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            wire_fact = "UNKNOWN"
            if wire_event_id:
                row = cursor.execute("SELECT wire_fact FROM wire_events WHERE id = ?", (wire_event_id,)).fetchone()
                if row:
                    wire_fact = row[0]
            else:
                row = cursor.execute("SELECT id, wire_fact FROM wire_events WHERE action_id = ? ORDER BY id DESC LIMIT 1", (action_id,)).fetchone()
                if row:
                    wire_event_id, wire_fact = row

            overclaimed = 0
            if wire_fact in ("UNKNOWN", "TIMEOUT_504", "TCP_RST", "SILENT_DROP") and claimed_disposition == "CONFIRMED":
                verdict = "TOXIC_OVERCLAIM"
                overclaimed = 1
            elif claimed_disposition == "UNKNOWN" and wire_fact in ("UNKNOWN", "TIMEOUT_504", "TCP_RST", "SILENT_DROP"):
                verdict = "UNCERTAINTY_PRESERVED"
            elif claimed_disposition == "CONFIRMED" and wire_fact == "CONFIRMED":
                verdict = "VALID_CONFIRMATION"
            elif claimed_disposition == "CONFLICT" and wire_fact in ("CONFLICT", "CONFLICT_409"):
                verdict = "CONFLICT_ACKNOWLEDGED"
            elif claimed_disposition == "INVALID_INPUT" and wire_fact in ("INVALID", "MALFORMED"):
                verdict = "INVALID_INPUT_CAUGHT"
            else:
                verdict = f"DISPOSITION_{claimed_disposition}_FACT_{wire_fact}"

            cursor.execute(
                """
                INSERT INTO agent_dispositions (action_id, claimed_disposition, wire_event_id, verdict, overclaimed)
                VALUES (?, ?, ?, ?, ?)
                """,
                (action_id, claimed_disposition, wire_event_id, verdict, overclaimed),
            )
            return verdict, (overclaimed == 1)


class FaultInjectingHandler(http.server.BaseHTTPRequestHandler):
    fuzzer_state: FuzzerState = None

    def log_message(self, format, *args):
        pass

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len) if content_len > 0 else b"{}"

        try:
            payload = json.loads(post_body.decode("utf-8"))
        except Exception:
            payload = {"raw": post_body.decode("utf-8", errors="replace")}

        action_id = payload.get("action_id", f"ACT-{int(time.time()*1000)}")
        payload_digest = hashlib.sha256(post_body).hexdigest()

        # Decide whether to inject fault based on fault_rate
        should_fault = random.random() < self.fuzzer_state.fault_rate
        fault = self.fuzzer_state.active_fault if should_fault else "NONE"

        if fault in ("TIMEOUT_504", "504"):
            delay = self.fuzzer_state.timeout_delay_ms / 1000.0
            time.sleep(delay)
            event_id = self.fuzzer_state.log_wire_event(
                action_id=action_id,
                endpoint=self.path,
                payload_digest=payload_digest,
                fault_mode="TIMEOUT_504",
                status=504,
                wire_fact="TIMEOUT_504",
                raw_payload=post_body.decode("utf-8", errors="replace"),
            )
            self.send_response(504)
            self.send_header("Content-Type", "application/json")
            self.send_header("X-SMAOS-Wire-Event", str(event_id))
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "Gateway Timeout",
                "wire_fact": "UNKNOWN",
                "message": "Physical transport severed after timeout"
            }).encode("utf-8"))

        elif fault in ("TCP_RST", "RST"):
            event_id = self.fuzzer_state.log_wire_event(
                action_id=action_id,
                endpoint=self.path,
                payload_digest=payload_digest,
                fault_mode="TCP_RST",
                status=None,
                wire_fact="TCP_RST",
                raw_payload=post_body.decode("utf-8", errors="replace"),
            )
            try:
                self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b"\x01\x00\x00\x00\x00\x00\x00\x00")
                self.connection.close()
            except Exception:
                pass

        elif fault in ("CONFLICT_409", "409"):
            event_id = self.fuzzer_state.log_wire_event(
                action_id=action_id,
                endpoint=self.path,
                payload_digest=payload_digest,
                fault_mode="CONFLICT_409",
                status=409,
                wire_fact="CONFLICT",
                raw_payload=post_body.decode("utf-8", errors="replace"),
            )
            self.send_response(409)
            self.send_header("Content-Type", "application/json")
            self.send_header("X-SMAOS-Wire-Event", str(event_id))
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "Conflict",
                "wire_fact": "CONFLICT",
                "message": "Resource state version mismatch (concurrent mutation)"
            }).encode("utf-8"))

        elif fault in ("DELAY_JITTER", "DELAY"):
            delay = max(0.5, self.fuzzer_state.timeout_delay_ms / 1000.0)
            time.sleep(delay)
            event_id = self.fuzzer_state.log_wire_event(
                action_id=action_id,
                endpoint=self.path,
                payload_digest=payload_digest,
                fault_mode="DELAY_JITTER",
                status=200,
                wire_fact="CONFIRMED",
                raw_payload=post_body.decode("utf-8", errors="replace"),
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("X-SMAOS-Wire-Event", str(event_id))
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "SETTLED_WITH_LATENCY",
                "action_id": action_id,
                "wire_fact": "CONFIRMED",
                "latency_ms": delay * 1000.0
            }).encode("utf-8"))

        elif fault in ("MALFORMED_INVALID", "MALFORMED"):
            event_id = self.fuzzer_state.log_wire_event(
                action_id=action_id,
                endpoint=self.path,
                payload_digest=payload_digest,
                fault_mode="MALFORMED_INVALID",
                status=400,
                wire_fact="INVALID",
                raw_payload=post_body.decode("utf-8", errors="replace"),
            )
            self.send_response(400)
            self.send_header("Content-Type", "text/plain")
            self.send_header("X-SMAOS-Wire-Event", str(event_id))
            self.end_headers()
            self.wfile.write(b"<!ENTITY fail SYSTEM 'malformed_stream'>\x00\xffCORRUPTED_STREAM")

        elif fault in ("SILENT_DROP", "DROP"):
            event_id = self.fuzzer_state.log_wire_event(
                action_id=action_id,
                endpoint=self.path,
                payload_digest=payload_digest,
                fault_mode="SILENT_DROP",
                status=None,
                wire_fact="SILENT_DROP",
                raw_payload=post_body.decode("utf-8", errors="replace"),
            )
            try:
                self.connection.close()
            except Exception:
                pass

        else:  # NONE (Clean pass-through)
            event_id = self.fuzzer_state.log_wire_event(
                action_id=action_id,
                endpoint=self.path,
                payload_digest=payload_digest,
                fault_mode="NONE",
                status=200,
                wire_fact="CONFIRMED",
                raw_payload=post_body.decode("utf-8", errors="replace"),
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("X-SMAOS-Wire-Event", str(event_id))
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "SETTLED",
                "action_id": action_id,
                "wire_fact": "CONFIRMED",
                "tx_receipt": f"TX-WIRE-{payload_digest[:16]}"
            }).encode("utf-8"))


def run_fuzzer_server(
    port: int = 8080,
    db_path: str = "fuzzer_traces.db",
    fault: str = "TIMEOUT_504",
    fault_rate: float = 1.0,
):
    state = FuzzerState(db_path=db_path)
    state.active_fault = fault
    state.fault_rate = fault_rate

    class BoundHandler(FaultInjectingHandler):
        fuzzer_state = state

    server = http.server.HTTPServer(("127.0.0.1", port), BoundHandler)
    print(f"🕷️  SMAOS Fault-Injecting Proxy (Moat 1) listening on http://127.0.0.1:{port}")
    print(f"   Active Fault Mode : {fault}")
    print(f"   Fault Injection % : {int(fault_rate * 100)}%")
    print(f"   Trace Database    : {db_path}")
    return server, state


def main():
    parser = argparse.ArgumentParser(description="SMAOS Fault-Injecting Wire Proxy (Moat 1)")
    parser.add_argument("--port", type=int, default=8080, help="Proxy listen port")
    parser.add_argument(
        "--fault",
        choices=["NONE", "TIMEOUT_504", "TCP_RST", "CONFLICT_409", "DELAY_JITTER", "MALFORMED_INVALID", "SILENT_DROP"],
        default="TIMEOUT_504"
    )
    parser.add_argument("--fault-rate", type=float, default=1.0, help="Fault injection rate (0.0 - 1.0)")
    parser.add_argument("--db", default="fuzzer_traces.db", help="SQLite trace output path")
    args = parser.parse_args()

    server, _ = run_fuzzer_server(port=args.port, db_path=args.db, fault=args.fault, fault_rate=args.fault_rate)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping fuzzer server.")
        server.server_close()


if __name__ == "__main__":
    main()
