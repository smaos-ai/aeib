#!/usr/bin/env python3
"""
Live Kill-Chain Attestor & DNS Tunneling Firewall (src/live_killchain_attestor.py).

Status: INTERNAL PREVIEW COMMISSIONED
Evaluated under the stated model to execute sub-15ms SIGKILL canary drills
and block covert DNS tunneling across record types, wire sizes, and label entropy.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
import signal
import subprocess
import sys
import time
from typing import Callable, FrozenSet, Optional, Sequence

from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs

ALLOWED_DNS_RECORD_TYPES: FrozenSet[str] = frozenset({"A", "AAAA"})


@dataclass(frozen=True)
class KillChainDrillReceipt:
    """Cryptographically signed receipt for a live subprocess SIGKILL drill."""

    drill_id: str
    canary_pid: int
    termination_latency_us: int
    max_allowed_latency_us: int
    process_verified_dead: bool
    passed_sla: bool
    system_state: str
    receipt_caid: str
    signature_hex: str


@dataclass(frozen=True)
class DNSEgressVerdict:
    """Deterministic verdict for DNS egress query inspection."""

    allowed: bool
    status_code: str
    violation_reason: str
    query_domain: str
    record_type: str
    wire_bytes_len: int
    max_label_len: int
    verdict_caid: str


def _has_tunnel_encoding(labels: Sequence[str]) -> bool:
    """Detect hex-encoded or base64-like high digit/consonant ratio in labels >= 8 chars."""
    vowels = frozenset("aeiou")
    for label in labels:
        if len(label) >= 8:
            non_vowel_count = sum(1 for ch in label if ch not in vowels)
            if non_vowel_count * 5 >= len(label) * 4:
                return True
    return False


class LiveKillChainAttestor:
    """Executes live subprocess kill-chain drills and enforces DNS egress firewall rules."""

    def __init__(
        self,
        max_kill_latency_us: int = 15_000,  # claim: config
        allowed_dns_domains: Sequence[str] = (),
        max_dns_wire_bytes: int = 128,  # claim: config
        max_label_length: int = 24,  # claim: config
        signing_key: Optional[ed25519.Ed25519PrivateKey] = None,
        clock_ns: Callable[[], int] = time.perf_counter_ns,
    ) -> None:
        if max_kill_latency_us <= 0:
            raise ValueError("max_kill_latency_us must be > 0")
        if max_dns_wire_bytes <= 0:
            raise ValueError("max_dns_wire_bytes must be > 0")
        if max_label_length <= 0:
            raise ValueError("max_label_length must be > 0")
        self._max_kill_latency_us: int = max_kill_latency_us
        self._allowed_domains: FrozenSet[str] = frozenset(
            d.strip().rstrip(".").lower() for d in allowed_dns_domains if d.strip()
        )
        self._max_dns_wire_bytes: int = max_dns_wire_bytes
        self._max_label_length: int = max_label_length
        self._signing_key: ed25519.Ed25519PrivateKey = (
            signing_key if signing_key is not None else ed25519.Ed25519PrivateKey.generate()
        )
        self._clock_ns: Callable[[], int] = clock_ns
        self._circuit_breaker_tripped: bool = False

    @property
    def circuit_breaker_tripped(self) -> bool:
        """Return whether the kill-chain circuit breaker is currently tripped."""
        return self._circuit_breaker_tripped

    @property
    def public_key(self) -> ed25519.Ed25519PublicKey:
        """Return the Ed25519 public key corresponding to the attestor signing key."""
        return self._signing_key.public_key()

    def execute_live_kill_drill(
        self,
        drill_id: str,
        simulated_delay_us: int = 0,  # claim: config
    ) -> KillChainDrillReceipt:
        """Spawn a sleeper subprocess, terminate with SIGKILL, and sign the SLA receipt."""
        if simulated_delay_us < 0:
            raise ValueError("simulated_delay_us must be >= 0")
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        start_ns = self._clock_ns()
        if simulated_delay_us:
            time.sleep(simulated_delay_us / 1_000_000.0)
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait(timeout=1.0)
        elapsed_us = (self._clock_ns() - start_ns) // 1000
        is_dead = proc.poll() is not None
        passed_sla = is_dead and (elapsed_us <= self._max_kill_latency_us)

        if not passed_sla:
            self._circuit_breaker_tripped = True
            system_state = "HALT_SYSTEM_FROZEN_KILL_PATH_FAILED"
        else:
            system_state = "NOMINAL_KILL_PATH_VERIFIED"

        payload = {
            "canary_pid": proc.pid,
            "drill_id": drill_id,
            "max_allowed_latency_us": self._max_kill_latency_us,
            "passed_sla": passed_sla,
            "process_verified_dead": is_dead,
            "system_state": system_state,
            "termination_latency_us": elapsed_us,
        }
        canonical_bytes = encode_jcs(payload)
        receipt_caid = hashlib.sha256(canonical_bytes).hexdigest()
        signature_hex = self._signing_key.sign(canonical_bytes).hex()

        return KillChainDrillReceipt(
            drill_id=drill_id,
            canary_pid=proc.pid,
            termination_latency_us=elapsed_us,
            max_allowed_latency_us=self._max_kill_latency_us,
            process_verified_dead=is_dead,
            passed_sla=passed_sla,
            system_state=system_state,
            receipt_caid=receipt_caid,
            signature_hex=signature_hex,
        )

    def _build_dns_verdict(
        self,
        allowed: bool,
        status_code: str,
        violation_reason: str,
        query_domain: str,
        record_type: str,
        wire_bytes_len: int,
        max_label_len: int,
    ) -> DNSEgressVerdict:
        payload = {
            "allowed": allowed,
            "max_label_len": max_label_len,
            "query_domain": query_domain,
            "record_type": record_type,
            "status_code": status_code,
            "violation_reason": violation_reason,
            "wire_bytes_len": wire_bytes_len,
        }
        verdict_caid = hashlib.sha256(encode_jcs(payload)).hexdigest()
        return DNSEgressVerdict(
            allowed=allowed,
            status_code=status_code,
            violation_reason=violation_reason,
            query_domain=query_domain,
            record_type=record_type,
            wire_bytes_len=wire_bytes_len,
            max_label_len=max_label_len,
            verdict_caid=verdict_caid,
        )

    def inspect_dns_query(
        self,
        query_domain: str,
        record_type: str,
        wire_bytes_len: int,
    ) -> DNSEgressVerdict:
        """Inspect outbound DNS query for circuit-breaker state, record type, wire size, and tunneling."""
        norm_domain = query_domain.strip().rstrip(".").lower()
        norm_type = record_type.strip().upper()
        labels = [lbl for lbl in norm_domain.split(".") if lbl]
        max_label_len = max((len(lbl) for lbl in labels), default=0)

        if self._circuit_breaker_tripped:
            return self._build_dns_verdict(
                allowed=False,
                status_code="HALT_CIRCUIT_BREAKER_FROZEN",
                violation_reason="REASON_KILL_PATH_CIRCUIT_BREAKER_TRIPPED",
                query_domain=norm_domain,
                record_type=norm_type,
                wire_bytes_len=wire_bytes_len,
                max_label_len=max_label_len,
            )

        if norm_type not in ALLOWED_DNS_RECORD_TYPES:
            return self._build_dns_verdict(
                allowed=False,
                status_code="HALT_DNS_TUNNEL_RECORD_TYPE_FORBIDDEN",
                violation_reason=f"Record type {norm_type} forbidden",
                query_domain=norm_domain,
                record_type=norm_type,
                wire_bytes_len=wire_bytes_len,
                max_label_len=max_label_len,
            )

        if wire_bytes_len > self._max_dns_wire_bytes:
            return self._build_dns_verdict(
                allowed=False,
                status_code="HALT_DNS_PACKET_OVERSIZE",
                violation_reason=f"Wire bytes {wire_bytes_len} > max {self._max_dns_wire_bytes}",
                query_domain=norm_domain,
                record_type=norm_type,
                wire_bytes_len=wire_bytes_len,
                max_label_len=max_label_len,
            )

        if max_label_len > self._max_label_length or _has_tunnel_encoding(labels):
            return self._build_dns_verdict(
                allowed=False,
                status_code="HALT_DNS_SUBDOMAIN_TUNNEL_DETECTED",
                violation_reason="REASON_SUBDOMAIN_LABEL_LENGTH_OR_ENTROPY_EXCEEDED",
                query_domain=norm_domain,
                record_type=norm_type,
                wire_bytes_len=wire_bytes_len,
                max_label_len=max_label_len,
            )

        if norm_domain not in self._allowed_domains:
            return self._build_dns_verdict(
                allowed=False,
                status_code="HALT_DNS_DOMAIN_NOT_ALLOWLISTED",
                violation_reason=f"Domain {norm_domain} not allowlisted",
                query_domain=norm_domain,
                record_type=norm_type,
                wire_bytes_len=wire_bytes_len,
                max_label_len=max_label_len,
            )

        return self._build_dns_verdict(
            allowed=True,
            status_code="ALLOW_DNS_QUERY_CLEAN",
            violation_reason="NONE",
            query_domain=norm_domain,
            record_type=norm_type,
            wire_bytes_len=wire_bytes_len,
            max_label_len=max_label_len,
        )
