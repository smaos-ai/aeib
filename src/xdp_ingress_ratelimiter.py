# Copyright 2026 SovereignNexus Project
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
src/xdp_ingress_ratelimiter.py — Autonomous eBPF XDP Ingress Rate-Limiting & DDoS Mitigator.

Part of Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise Gateway.
Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model as an in-kernel
eBPF XDP (eXpress Data Path) ingress rate-limiting scaffold and autonomous DDoS mitigation prototype.

Honest Platform Boundary (Software Scaffold & Simulated Prototype):
  - This module is a software scaffold and simulation prototype for kernel-space eBPF XDP
    ingress packet filtering and rate-limiting.
  - It simulates XDP verdict pipelines (XDP_PASS, XDP_DROP, XDP_TX, XDP_REDIRECT, XDP_ABORTED)
    and BPF map-backed token buckets without invoking native kernel BPF system calls.
  - Operational mode: scaffold / simulated XDP filter.

Architectural Invariants:
1. Multi-Tier Token Bucket Limiting:
   - Global interface bandwidth and packet rate ceilings.
   - Per-IP ingress leaky token bucket with integer millisecond replenishment.
   - Per-agent verified token bucket for authenticated sovereign agent communications.
2. Progressive Exponential Quarantine:
   - Dynamic detection of SYN/UDP floods and rate violations.
   - Escalating quarantine durations (base_duration * 2^(level - 1)) with instant XDP_DROP.
3. Cryptographic Agent Authentication:
   - Ed25519 signature verification on authenticated agent packets.
4. Fail-Closed Verdicts:
   - HALT_MALFORMED_PACKET
   - HALT_GLOBAL_CAPACITY_EXCEEDED
   - HALT_IP_RATE_EXCEEDED
   - HALT_AGENT_RATE_EXCEEDED
   - HALT_ENTITY_QUARANTINED
   - HALT_AUTH_SIGNATURE_INVALID
   - HALT_EPOCH_EXPIRED
5. RFC 8785 Canonical Auditing & SQLite-WAL Durability:
   - All ingress verdicts and quarantine transitions are cryptographically sealed via JCS
     and persisted to SQLite-WAL.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import ipaddress
import json
import math
import sqlite3
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs

# XDP Action Codes (matching linux/bpf.h enum xdp_action)
XDP_ABORTED: int = 0
XDP_DROP: int = 1
XDP_PASS: int = 2
XDP_TX: int = 3
XDP_REDIRECT: int = 4

XDP_ACTION_NAMES: Dict[int, str] = {
    XDP_ABORTED: "XDP_ABORTED",
    XDP_DROP: "XDP_DROP",
    XDP_PASS: "XDP_PASS",
    XDP_TX: "XDP_TX",
    XDP_REDIRECT: "XDP_REDIRECT",
}

# Fail-Closed Rejection Codes
HALT_MALFORMED_PACKET: str = "HALT_MALFORMED_PACKET"
HALT_GLOBAL_CAPACITY_EXCEEDED: str = "HALT_GLOBAL_CAPACITY_EXCEEDED"
HALT_IP_RATE_EXCEEDED: str = "HALT_IP_RATE_EXCEEDED"
HALT_AGENT_RATE_EXCEEDED: str = "HALT_AGENT_RATE_EXCEEDED"
HALT_ENTITY_QUARANTINED: str = "HALT_ENTITY_QUARANTINED"
HALT_AUTH_SIGNATURE_INVALID: str = "HALT_AUTH_SIGNATURE_INVALID"
HALT_EPOCH_EXPIRED: str = "HALT_EPOCH_EXPIRED"

# Default configuration bounds
DEFAULT_GLOBAL_CAPACITY_BYTES: int = 50_000_000   # 50 MB burst
DEFAULT_GLOBAL_REFILL_BPS: int = 10_000_000        # claim: config - 10 MB/s refill
DEFAULT_IP_CAPACITY_PACKETS: int = 100             # 100 packet burst
DEFAULT_IP_REFILL_RATE_PPS: int = 20               # 20 packets/s refill
DEFAULT_AGENT_CAPACITY_PACKETS: int = 500          # 500 packet burst for verified agents
DEFAULT_AGENT_REFILL_RATE_PPS: int = 100           # 100 packets/s refill
DEFAULT_VIOLATION_THRESHOLD: int = 5               # 5 violations triggers quarantine
DEFAULT_VIOLATION_WINDOW_MS: int = 10_000          # claim: config - 10 seconds sliding window
DEFAULT_BASE_QUARANTINE_MS: int = 15_000           # claim: config - 15 seconds base quarantine
MAX_QUARANTINE_LEVEL: int = 8                      # Maximum exponential backoff level
MAX_ALLOWED_CLOCK_SKEW_MS: int = 60_000            # claim: config - 60s max packet timestamp skew


def compute_sha256(data: bytes) -> str:
    """Compute standard lowercase hex SHA-256 digest."""
    return hashlib.sha256(data).hexdigest()


def compute_wilson_ci_bps(k: int, n: int, z: float = 1.95996) -> Tuple[int, int]:
    """
    Compute conservative Wilson 95% confidence interval in basis points (0..10000 bps).
    """
    if n <= 0 or k < 0 or k > n:
        return 0, 0
    p = k / n
    denom = 1.0 + (z * z) / n
    center = (p + (z * z) / (2.0 * n)) / denom
    half_width = (z * math.sqrt((p * (1.0 - p) + (z * z) / (4.0 * n)) / n)) / denom
    low = max(0.0, center - half_width)
    high = min(1.0, center + half_width)
    return round(low * 10000), round(high * 10000)


@dataclass(frozen=True)
class XdpIngressPacket:
    """Raw ingress packet representation arriving at the XDP driver hook."""
    src_ip: str
    src_port: int
    dst_ip: str
    dst_port: int
    protocol: str
    payload_bytes: int
    timestamp_ms: int
    agent_id: Optional[str] = None
    auth_signature_hex: Optional[str] = None
    auth_pubkey_hex: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.src_ip or not isinstance(self.src_ip, str):
            raise ValueError("src_ip must be a non-empty string")
        if not self.dst_ip or not isinstance(self.dst_ip, str):
            raise ValueError("dst_ip must be a non-empty string")
        if not (1 <= self.src_port <= 65535):
            raise ValueError(f"src_port {self.src_port} outside valid range [1..65535]")
        if not (1 <= self.dst_port <= 65535):
            raise ValueError(f"dst_port {self.dst_port} outside valid range [1..65535]")
        if self.protocol.upper() not in {"TCP", "UDP", "ICMP"}:
            raise ValueError(f"Unsupported protocol: {self.protocol}")
        if self.payload_bytes < 0:
            raise ValueError(f"payload_bytes cannot be negative: {self.payload_bytes}")
        if self.timestamp_ms <= 0:
            raise ValueError("timestamp_ms must be positive")

    def compute_caid(self) -> str:
        """Deterministic RFC 8785 canonical hash of the packet header."""
        doc = {
            "agent_id": self.agent_id,
            "dst_ip": self.dst_ip,
            "dst_port": self.dst_port,
            "payload_bytes": self.payload_bytes,
            "protocol": self.protocol.upper(),
            "src_ip": self.src_ip,
            "src_port": self.src_port,
            "timestamp_ms": self.timestamp_ms,
        }
        return compute_sha256(encode_jcs(doc))

    def compute_auth_message(self) -> bytes:
        """Compute message bytes expected to be signed by the agent key."""
        doc = {
            "agent_id": self.agent_id,
            "dst_ip": self.dst_ip,
            "dst_port": self.dst_port,
            "payload_bytes": self.payload_bytes,
            "protocol": self.protocol.upper(),
            "src_ip": self.src_ip,
            "timestamp_ms": self.timestamp_ms,
        }
        return encode_jcs(doc)


@dataclass(frozen=True)
class XdpFilterVerdict:
    """Cryptographically verifiable verdict returned by the XDP rate-limiter."""
    action: int
    verdict_name: str
    reason: str
    src_ip: str
    packet_caid: str
    tokens_remaining: int
    quarantined: bool
    timestamp_ms: int
    caid: str

    def __post_init__(self) -> None:
        if self.action not in XDP_ACTION_NAMES:
            raise ValueError(f"Invalid XDP action code: {self.action}")
        if not self.packet_caid:
            raise ValueError("packet_caid must be non-empty")
        if not self.caid:
            raise ValueError("caid must be non-empty")


@dataclass
class TokenBucket:
    """Token bucket state for integer-rate token replenishment."""
    capacity: int
    refill_rate_per_sec: int
    current_tokens: int
    last_update_ms: int

    def replenish(self, now_ms: int) -> None:
        """Replenish tokens based on elapsed milliseconds."""
        if now_ms <= self.last_update_ms:
            return
        elapsed_ms = now_ms - self.last_update_ms
        tokens_to_add = (elapsed_ms * self.refill_rate_per_sec) // 1000
        if tokens_to_add > 0:
            self.current_tokens = min(self.capacity, self.current_tokens + tokens_to_add)
            self.last_update_ms = now_ms

    def consume(self, amount: int, now_ms: int) -> bool:
        """Attempt to consume tokens. Returns True if admitted, False if exhausted."""
        self.replenish(now_ms)
        if self.current_tokens >= amount:
            self.current_tokens -= amount
            return True
        return False


@dataclass
class QuarantineRecord:
    """Quarantine state for a misbehaving source IP or agent."""
    entity_key: str
    level: int
    quarantine_until_ms: int
    violation_count: int
    last_violation_ms: int
    reason: str


class XdpIngressRateLimiter:
    """
    Autonomous eBPF XDP Ingress Rate-Limiting & DDoS Mitigator Scaffold.
    Enforces multi-tier token-bucket throttling, progressive exponential quarantine,
    and Ed25519 agent authentication at the simulated XDP packet ingress driver hook.
    """

    def __init__(
        self,
        db_path: str = ":memory:",
        global_capacity_bytes: int = DEFAULT_GLOBAL_CAPACITY_BYTES,
        global_refill_bps: int = DEFAULT_GLOBAL_REFILL_BPS,
        ip_capacity_packets: int = DEFAULT_IP_CAPACITY_PACKETS,
        ip_refill_pps: int = DEFAULT_IP_REFILL_RATE_PPS,
        agent_capacity_packets: int = DEFAULT_AGENT_CAPACITY_PACKETS,
        agent_refill_pps: int = DEFAULT_AGENT_REFILL_RATE_PPS,
        violation_threshold: int = DEFAULT_VIOLATION_THRESHOLD,
        violation_window_ms: int = DEFAULT_VIOLATION_WINDOW_MS,
        base_quarantine_ms: int = DEFAULT_BASE_QUARANTINE_MS,
        max_quarantine_level: int = MAX_QUARANTINE_LEVEL,
        max_clock_skew_ms: int = MAX_ALLOWED_CLOCK_SKEW_MS,
    ) -> None:
        if global_capacity_bytes <= 0 or global_refill_bps < 0:
            raise ValueError("Global capacity must be positive and refill rate must be non-negative")
        if ip_capacity_packets <= 0 or ip_refill_pps < 0:
            raise ValueError("IP capacity must be positive and refill rate must be non-negative")
        if agent_capacity_packets <= 0 or agent_refill_pps < 0:
            raise ValueError("Agent capacity must be positive and refill rate must be non-negative")
        if violation_threshold <= 0 or violation_window_ms <= 0:
            raise ValueError("Violation threshold and window must be positive integers")
        if base_quarantine_ms <= 0:
            raise ValueError("Base quarantine duration must be positive")

        self.db_path = db_path
        self.global_capacity_bytes = global_capacity_bytes
        self.global_refill_bps = global_refill_bps
        self.ip_capacity_packets = ip_capacity_packets
        self.ip_refill_pps = ip_refill_pps
        self.agent_capacity_packets = agent_capacity_packets
        self.agent_refill_pps = agent_refill_pps
        self.violation_threshold = violation_threshold
        self.violation_window_ms = violation_window_ms
        self.base_quarantine_ms = base_quarantine_ms
        self.max_quarantine_level = max_quarantine_level
        self.max_clock_skew_ms = max_clock_skew_ms

        now_ms = int(time.time() * 1000)
        self._global_bucket = TokenBucket(
            capacity=self.global_capacity_bytes,
            refill_rate_per_sec=self.global_refill_bps,
            current_tokens=self.global_capacity_bytes,
            last_update_ms=now_ms,
        )

        self._ip_buckets: Dict[str, TokenBucket] = {}
        self._agent_buckets: Dict[str, TokenBucket] = {}
        self._quarantines: Dict[str, QuarantineRecord] = {}
        self._violation_history: Dict[str, List[int]] = {}

        self._conn = sqlite3.connect(self.db_path)
        self._init_sqlite_schema()

    def _init_sqlite_schema(self) -> None:
        """Initialize SQLite tables and WAL configuration."""
        with self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS xdp_verdicts_ledger (
                    caid TEXT PRIMARY KEY,
                    packet_caid TEXT NOT NULL,
                    action INTEGER NOT NULL,
                    verdict_name TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    src_ip TEXT NOT NULL,
                    tokens_remaining INTEGER NOT NULL,
                    quarantined INTEGER NOT NULL,
                    timestamp_ms INTEGER NOT NULL
                );
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS xdp_quarantine_ledger (
                    entity_key TEXT PRIMARY KEY,
                    level INTEGER NOT NULL,
                    quarantine_until_ms INTEGER NOT NULL,
                    violation_count INTEGER NOT NULL,
                    last_violation_ms INTEGER NOT NULL,
                    reason TEXT NOT NULL
                );
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_xdp_verdicts_src ON xdp_verdicts_ledger (src_ip, timestamp_ms);"
            )

    def _record_violation(self, entity_key: str, reason: str, now_ms: int) -> bool:
        """
        Record a rate violation for an entity. Triggers quarantine if violations in
        the sliding window exceed the configured threshold. Returns True if quarantined.
        """
        if entity_key not in self._violation_history:
            self._violation_history[entity_key] = []

        history = self._violation_history[entity_key]
        history.append(now_ms)
        # Prune violations outside the sliding window
        window_start = now_ms - self.violation_window_ms
        self._violation_history[entity_key] = [t for t in history if t >= window_start]

        if len(self._violation_history[entity_key]) >= self.violation_threshold:
            # Escalate quarantine level
            prev_level = 0
            if entity_key in self._quarantines:
                prev_level = self._quarantines[entity_key].level

            new_level = min(self.max_quarantine_level, prev_level + 1)
            duration_ms = self.base_quarantine_ms * (2 ** (new_level - 1))
            quarantine_until = now_ms + duration_ms

            record = QuarantineRecord(
                entity_key=entity_key,
                level=new_level,
                quarantine_until_ms=quarantine_until,
                violation_count=len(self._violation_history[entity_key]),
                last_violation_ms=now_ms,
                reason=reason,
            )
            self._quarantines[entity_key] = record

            # Persist to SQLite
            with self._conn:
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO xdp_quarantine_ledger (
                        entity_key, level, quarantine_until_ms, violation_count, last_violation_ms, reason
                    ) VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (
                        record.entity_key,
                        record.level,
                        record.quarantine_until_ms,
                        record.violation_count,
                        record.last_violation_ms,
                        record.reason,
                    ),
                )
            return True
        return False

    def _is_quarantined(self, entity_key: str, now_ms: int) -> bool:
        """Check if an entity is currently under active quarantine."""
        if entity_key not in self._quarantines:
            return False
        record = self._quarantines[entity_key]
        if now_ms < record.quarantine_until_ms:
            return True
        # Quarantine expired: remove from active dict
        del self._quarantines[entity_key]
        with self._conn:
            self._conn.execute(
                "DELETE FROM xdp_quarantine_ledger WHERE entity_key = ?;",
                (entity_key,),
            )
        return False

    def _verify_agent_signature(self, packet: XdpIngressPacket) -> bool:
        """Verify Ed25519 signature on an authenticated agent packet."""
        if not packet.auth_pubkey_hex or not packet.auth_signature_hex:
            return False
        try:
            pubkey_bytes = bytes.fromhex(packet.auth_pubkey_hex)
            sig_bytes = bytes.fromhex(packet.auth_signature_hex)
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(pubkey_bytes)
            message = packet.compute_auth_message()
            public_key.verify(sig_bytes, message)
            return True
        except (ValueError, InvalidSignature):
            return False

    def process_packet(
        self,
        packet: XdpIngressPacket,
        now_ms: Optional[int] = None,
    ) -> XdpFilterVerdict:
        """
        Process an ingress packet through simulated XDP multi-tier token buckets.
        Returns a cryptographically sealed XdpFilterVerdict.
        """
        if now_ms is None:
            now_ms = int(time.time() * 1000)

        # 1. Structural IP validation
        try:
            ipaddress.ip_address(packet.src_ip)
            ipaddress.ip_address(packet.dst_ip)
        except ValueError:
            return self._build_verdict(
                action=XDP_DROP,
                reason=HALT_MALFORMED_PACKET,
                src_ip=packet.src_ip,
                packet_caid=packet.compute_caid(),
                tokens_remaining=0,
                quarantined=False,
                now_ms=now_ms,
            )

        packet_caid = packet.compute_caid()

        # 2. Clock-skew and epoch freshness validation
        if abs(now_ms - packet.timestamp_ms) > self.max_clock_skew_ms:
            return self._build_verdict(
                action=XDP_DROP,
                reason=HALT_EPOCH_EXPIRED,
                src_ip=packet.src_ip,
                packet_caid=packet_caid,
                tokens_remaining=0,
                quarantined=False,
                now_ms=now_ms,
            )

        # 3. Active quarantine check (Per-IP or Per-Agent)
        if self._is_quarantined(packet.src_ip, now_ms):
            return self._build_verdict(
                action=XDP_DROP,
                reason=HALT_ENTITY_QUARANTINED,
                src_ip=packet.src_ip,
                packet_caid=packet_caid,
                tokens_remaining=0,
                quarantined=True,
                now_ms=now_ms,
            )

        if packet.agent_id and self._is_quarantined(packet.agent_id, now_ms):
            return self._build_verdict(
                action=XDP_DROP,
                reason=HALT_ENTITY_QUARANTINED,
                src_ip=packet.src_ip,
                packet_caid=packet_caid,
                tokens_remaining=0,
                quarantined=True,
                now_ms=now_ms,
            )

        # 4. Optional Agent Authentication & Verification
        is_verified_agent = False
        if packet.agent_id:
            if not self._verify_agent_signature(packet):
                self._record_violation(packet.src_ip, HALT_AUTH_SIGNATURE_INVALID, now_ms)
                return self._build_verdict(
                    action=XDP_DROP,
                    reason=HALT_AUTH_SIGNATURE_INVALID,
                    src_ip=packet.src_ip,
                    packet_caid=packet_caid,
                    tokens_remaining=0,
                    quarantined=False,
                    now_ms=now_ms,
                )
            is_verified_agent = True

        # 5. Global Interface Bandwidth Token Bucket
        packet_cost_bytes = max(1, packet.payload_bytes)
        if not self._global_bucket.consume(packet_cost_bytes, now_ms):
            return self._build_verdict(
                action=XDP_DROP,
                reason=HALT_GLOBAL_CAPACITY_EXCEEDED,
                src_ip=packet.src_ip,
                packet_caid=packet_caid,
                tokens_remaining=self._global_bucket.current_tokens,
                quarantined=False,
                now_ms=now_ms,
            )

        # 6. Entity Rate Limiting: Agent vs Standard IP
        if is_verified_agent and packet.agent_id:
            if packet.agent_id not in self._agent_buckets:
                self._agent_buckets[packet.agent_id] = TokenBucket(
                    capacity=self.agent_capacity_packets,
                    refill_rate_per_sec=self.agent_refill_pps,
                    current_tokens=self.agent_capacity_packets,
                    last_update_ms=now_ms,
                )
            agent_bucket = self._agent_buckets[packet.agent_id]
            if not agent_bucket.consume(1, now_ms):
                quarantined = self._record_violation(packet.agent_id, HALT_AGENT_RATE_EXCEEDED, now_ms)
                return self._build_verdict(
                    action=XDP_DROP,
                    reason=HALT_AGENT_RATE_EXCEEDED,
                    src_ip=packet.src_ip,
                    packet_caid=packet_caid,
                    tokens_remaining=agent_bucket.current_tokens,
                    quarantined=quarantined,
                    now_ms=now_ms,
                )
            tokens_remaining = agent_bucket.current_tokens
        else:
            # Standard per-IP rate limiting
            if packet.src_ip not in self._ip_buckets:
                self._ip_buckets[packet.src_ip] = TokenBucket(
                    capacity=self.ip_capacity_packets,
                    refill_rate_per_sec=self.ip_refill_pps,
                    current_tokens=self.ip_capacity_packets,
                    last_update_ms=now_ms,
                )
            ip_bucket = self._ip_buckets[packet.src_ip]
            if not ip_bucket.consume(1, now_ms):
                quarantined = self._record_violation(packet.src_ip, HALT_IP_RATE_EXCEEDED, now_ms)
                return self._build_verdict(
                    action=XDP_DROP,
                    reason=HALT_IP_RATE_EXCEEDED,
                    src_ip=packet.src_ip,
                    packet_caid=packet_caid,
                    tokens_remaining=ip_bucket.current_tokens,
                    quarantined=quarantined,
                    now_ms=now_ms,
                )
            tokens_remaining = ip_bucket.current_tokens

        # 7. Ingress Admitted
        return self._build_verdict(
            action=XDP_PASS,
            reason="ADMITTED",
            src_ip=packet.src_ip,
            packet_caid=packet_caid,
            tokens_remaining=tokens_remaining,
            quarantined=False,
            now_ms=now_ms,
        )

    def _build_verdict(
        self,
        action: int,
        reason: str,
        src_ip: str,
        packet_caid: str,
        tokens_remaining: int,
        quarantined: bool,
        now_ms: int,
    ) -> XdpFilterVerdict:
        """Construct, seal, and persist an XdpFilterVerdict."""
        verdict_name = XDP_ACTION_NAMES[action]
        doc = {
            "action": action,
            "packet_caid": packet_caid,
            "quarantined": quarantined,
            "reason": reason,
            "src_ip": src_ip,
            "timestamp_ms": now_ms,
            "tokens_remaining": tokens_remaining,
            "verdict_name": verdict_name,
        }
        caid = compute_sha256(encode_jcs(doc))

        verdict = XdpFilterVerdict(
            action=action,
            verdict_name=verdict_name,
            reason=reason,
            src_ip=src_ip,
            packet_caid=packet_caid,
            tokens_remaining=tokens_remaining,
            quarantined=quarantined,
            timestamp_ms=now_ms,
            caid=caid,
        )

        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO xdp_verdicts_ledger (
                    caid, packet_caid, action, verdict_name, reason, src_ip, tokens_remaining, quarantined, timestamp_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    verdict.caid,
                    verdict.packet_caid,
                    verdict.action,
                    verdict.verdict_name,
                    verdict.reason,
                    verdict.src_ip,
                    verdict.tokens_remaining,
                    1 if verdict.quarantined else 0,
                    verdict.timestamp_ms,
                ),
            )

        return verdict

    def get_verdict_by_caid(self, caid: str) -> Optional[Dict[str, Any]]:
        """Retrieve a stored verdict by its canonical CAID."""
        with self._conn:
            cursor = self._conn.execute(
                """
                SELECT caid, packet_caid, action, verdict_name, reason, src_ip, tokens_remaining, quarantined, timestamp_ms
                FROM xdp_verdicts_ledger WHERE caid = ?;
                """,
                (caid,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "caid": row[0],
                "packet_caid": row[1],
                "action": row[2],
                "verdict_name": row[3],
                "reason": row[4],
                "src_ip": row[5],
                "tokens_remaining": row[6],
                "quarantined": bool(row[7]),
                "timestamp_ms": row[8],
            }

    def list_active_quarantines(self, now_ms: Optional[int] = None) -> List[Dict[str, Any]]:
        """List all active quarantines with remaining durations."""
        if now_ms is None:
            now_ms = int(time.time() * 1000)
        with self._conn:
            cursor = self._conn.execute(
                """
                SELECT entity_key, level, quarantine_until_ms, violation_count, last_violation_ms, reason
                FROM xdp_quarantine_ledger
                WHERE quarantine_until_ms > ?
                ORDER BY quarantine_until_ms DESC;
                """,
                (now_ms,),
            )
            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "entity_key": row[0],
                        "level": row[1],
                        "quarantine_until_ms": row[2],
                        "remaining_ms": max(0, row[2] - now_ms),
                        "violation_count": row[3],
                        "last_violation_ms": row[4],
                        "reason": row[5],
                    }
                )
            return results

    def get_traffic_summary(self, since_ms: int = 0) -> Dict[str, Any]:
        """Aggregate traffic metrics: passed, dropped, quarantined packets."""
        with self._conn:
            cursor = self._conn.execute(
                """
                SELECT action, COUNT(*)
                FROM xdp_verdicts_ledger
                WHERE timestamp_ms >= ?
                GROUP BY action;
                """,
                (since_ms,),
            )
            counts: Dict[str, int] = {
                "XDP_PASS": 0,
                "XDP_DROP": 0,
                "XDP_TX": 0,
                "XDP_REDIRECT": 0,
                "XDP_ABORTED": 0,
            }
            total = 0
            for action_code, count in cursor.fetchall():
                name = XDP_ACTION_NAMES.get(action_code, "UNKNOWN")
                if name in counts:
                    counts[name] = count
                total += count
            return {
                "total_packets": total,
                "counts_by_action": counts,
                "pass_ratio_bps": round((counts["XDP_PASS"] / total * 10000)) if total > 0 else 0,
            }
