#!/usr/bin/env python3
"""
SovereignNexus Temporal Authority, Delegation & Async Execution Guard (src/temporal_authority_guard.py).

Status: INTERNAL PREVIEW COMMISSIONED
Evaluated under the stated model to enforce the 14-item Temporal Authority specification:
  1. Terminal Denial Latch: Intents denied at T0 (e.g., 402/policy/precondition) enter
     DENIED_TERMINAL and cannot execute at T+future when limits reset.
  2. CAID Time Binding & Snapshot-Resume Reauthorization: Strict [not_before, expires_at]
     checks on both initial dispatch and post-suspend snapshot resumption.
  3. Monotonic Cryptographic Delegation Chain: Child scope is a subset of Parent scope,
     Child expires_at <= Parent expires_at, Child taint >= Parent taint.
  4. Storage Persistence Guard: Blocks writes to cron, systemd, launchd, shell rc,
     and SSH authorized_keys.
  5. Network & DNS Tunneling Guard: Denies raw UDP/ICMP, restricts DNS to proxied A/AAAA
     queries <= 128 bytes on allowlisted domains, and rate-limits repeated queries.
  6. Layered AST & Process-Tree Async Guard: Blocks daemonization (setsid, fork, daemon=True),
     timers, schedulers, and deferred time.sleep calls.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
from typing import Any, Dict, FrozenSet, Mapping, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs


def sha256_caid(payload: Any) -> str:
    """Compute deterministic SHA-256 CAID over RFC 8785 canonical bytes."""
    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = encode_jcs(payload)
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


BANNED_ASYNC_MODULES: FrozenSet[str] = frozenset(
    {
        "subprocess",
        "sched",
        "schedule",
        "atexit",
        "celery",
        "crontab",
        "multiprocessing",
    }
)

BANNED_ASYNC_CALLS: FrozenSet[str] = frozenset(
    {
        "fork",
        "setsid",
        "daemon",
        "system",
        "popen",
        "Popen",
        "spawnl",
        "spawnle",
        "spawnlp",
        "spawnlpe",
        "spawnv",
        "spawnve",
        "spawnvp",
        "spawnvpe",
        "Timer",
        "alarm",
        "create_task",
        "delay",
    }
)

FORBIDDEN_PERSISTENCE_PATH_MARKERS: Tuple[str, ...] = (
    "/etc/cron",
    "/var/spool/cron",
    "crontab",
    "/etc/systemd/system",
    ".config/systemd/user",
    "library/launchagents",
    "library/launchdaemons",
    ".bashrc",
    ".bash_profile",
    ".zshrc",
    ".zprofile",
    ".profile",
    ".ssh/authorized_keys",
)


@dataclasses.dataclass(frozen=True)
class IntentScope:
    """Monotonic capability boundary for an authorized intent."""

    allowed_hosts: Tuple[str, ...]
    allowed_tools: Tuple[str, ...]
    max_amount_minor: int
    max_blast_radius_bps: int = 3000  # claim: config

    def __post_init__(self) -> None:
        if self.max_amount_minor < 0:
            raise ValueError(f"ERR_NEGATIVE_AMOUNT_MINOR:{self.max_amount_minor}")
        if self.max_blast_radius_bps < 0 or self.max_blast_radius_bps > 10000:
            raise ValueError(f"ERR_INVALID_BLAST_RADIUS_BPS:{self.max_blast_radius_bps}")
        object.__setattr__(self, "allowed_hosts", tuple(sorted(set(self.allowed_hosts))))
        object.__setattr__(self, "allowed_tools", tuple(sorted(set(self.allowed_tools))))

    def is_subset_of(self, parent: "IntentScope") -> bool:
        if not set(self.allowed_hosts).issubset(set(parent.allowed_hosts)):
            return False
        if not set(self.allowed_tools).issubset(set(parent.allowed_tools)):
            return False
        if self.max_amount_minor > parent.max_amount_minor:
            return False
        if self.max_blast_radius_bps > parent.max_blast_radius_bps:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed_hosts": list(self.allowed_hosts),
            "allowed_tools": list(self.allowed_tools),
            "max_amount_minor": self.max_amount_minor,
            "max_blast_radius_bps": self.max_blast_radius_bps,
        }


@dataclasses.dataclass(frozen=True)
class TemporalIntentEnvelope:
    """Cryptographically bound intent envelope with explicit temporal standing."""

    actor_spiffe_id: str
    effect_class: str
    idempotency_key: str
    policy_version: str
    session_id: str
    issued_at_epoch_sec: int
    not_before_epoch_sec: int
    expires_at_epoch_sec: int
    max_retries: int
    delegation_chain: Tuple[str, ...]
    taint_level: int
    scope: IntentScope
    preconditions: Dict[str, bool]
    payload: Dict[str, Any]
    signature_hex: str = ""

    def with_signature(self, sig_hex: str) -> "TemporalIntentEnvelope":
        return dataclasses.replace(self, signature_hex=sig_hex)

    def canonical_unsigned_bytes(self) -> bytes:
        body: Dict[str, Any] = {
            "actor_spiffe_id": self.actor_spiffe_id,
            "delegation_chain": list(self.delegation_chain),
            "effect_class": self.effect_class,
            "expires_at_epoch_sec": self.expires_at_epoch_sec,
            "idempotency_key": self.idempotency_key,
            "issued_at_epoch_sec": self.issued_at_epoch_sec,
            "max_retries": self.max_retries,
            "not_before_epoch_sec": self.not_before_epoch_sec,
            "payload": self.payload,
            "policy_version": self.policy_version,
            "preconditions": self.preconditions,
            "scope": self.scope.to_dict(),
            "session_id": self.session_id,
            "taint_level": self.taint_level,
        }
        return encode_jcs(body)

    @property
    def intent_caid(self) -> str:
        return sha256_caid(self.canonical_unsigned_bytes())


@dataclasses.dataclass(frozen=True)
class TemporalGuardVerdict:
    """Deterministic decision receipt emitted by TemporalAuthorityGuard."""

    authorized: bool
    state: str
    status_code: str
    intent_caid: str
    verdict_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "authorized": self.authorized,
            "intent_caid": self.intent_caid,
            "state": self.state,
            "status_code": self.status_code,
            "verdict_caid": self.verdict_caid,
        }


class TemporalAuthorityGuard:
    """
    Station 1 Temporal Authority, Delegation, Storage Persistence & DNS/Egress Controller.
    """

    ALLOWED_DNS_TYPES: FrozenSet[str] = frozenset({"A", "AAAA"})
    DNS_MAX_QUERY_LENGTH: int = 128
    DNS_MAX_LABEL_LENGTH: int = 52

    def __init__(
        self,
        trust_store: Mapping[str, ed25519.Ed25519PublicKey],
        active_session_id: str = "session_live_01",
        dns_max_queries_per_window: int = 5,
    ) -> None:
        if dns_max_queries_per_window <= 0:
            raise ValueError(f"ERR_INVALID_DNS_WINDOW:{dns_max_queries_per_window}")
        self.trust_store = dict(trust_store)
        self.active_session_id = active_session_id
        self.dns_max_queries_per_window = dns_max_queries_per_window
        self._intent_registry: Dict[str, TemporalIntentEnvelope] = {}
        self._intent_state: Dict[str, str] = {}
        self._attempt_counts: Dict[str, int] = {}
        self._dns_window_counts: Dict[str, int] = {}

    def get_intent_state(self, intent_caid: str) -> str:
        return self._intent_state.get(intent_caid, "UNREGISTERED")

    def register_intent(self, envelope: TemporalIntentEnvelope) -> TemporalGuardVerdict:
        caid = envelope.intent_caid
        pubkey = self.trust_store.get(envelope.actor_spiffe_id)
        if not pubkey:
            self._intent_state[caid] = "DENIED_TERMINAL"
            return self._mint(
                False,
                "DENIED_TERMINAL",
                f"HALT_UNKNOWN_ISSUER:{envelope.actor_spiffe_id}",
                caid,
            )

        try:
            pubkey.verify(
                bytes.fromhex(envelope.signature_hex),
                envelope.canonical_unsigned_bytes(),
            )
        except (ValueError, InvalidSignature):
            self._intent_state[caid] = "DENIED_TERMINAL"
            return self._mint(
                False,
                "DENIED_TERMINAL",
                "HALT_INVALID_INTENT_SIGNATURE",
                caid,
            )

        if (
            envelope.expires_at_epoch_sec < envelope.not_before_epoch_sec
            or envelope.not_before_epoch_sec < envelope.issued_at_epoch_sec
        ):
            self._intent_state[caid] = "DENIED_TERMINAL"
            return self._mint(
                False,
                "DENIED_TERMINAL",
                "HALT_INVALID_TTL_WINDOW",
                caid,
            )

        self._intent_registry[caid] = envelope
        if caid not in self._intent_state:
            self._intent_state[caid] = "INTENT_REGISTERED"
            self._attempt_counts[caid] = 0
        return self._mint(True, self._intent_state[caid], "OK_INTENT_REGISTERED", caid)

    def evaluate_temporal_dispatch(
        self,
        intent_caid: str,
        current_epoch_sec: int,
        live_preconditions: Mapping[str, bool],
        requested_host: str,
        requested_tool: str,
        requested_amount_minor: int,
        caller_session_id: Optional[str] = None,
    ) -> TemporalGuardVerdict:
        envelope = self._intent_registry.get(intent_caid)
        if not envelope:
            return self._mint(False, "DENIED_TERMINAL", "HALT_INTENT_NOT_FOUND", intent_caid)

        curr_state = self._intent_state.get(intent_caid, "INTENT_REGISTERED")

        # Rule 1: Prior denial is terminal (cannot wait out a 402/403 and replay at T+1h)
        if curr_state == "DENIED_TERMINAL":
            return self._mint(
                False,
                "DENIED_TERMINAL",
                "HALT_PRIOR_DENIAL_IS_TERMINAL:REAUTH_REQUIRED",
                intent_caid,
            )
        if curr_state == "COMMITTED":
            return self._mint(
                False,
                "COMMITTED",
                "HALT_DUPLICATE_COMMITTED_INTENT",
                intent_caid,
            )
        if curr_state == "FROZEN_INDETERMINATE":
            return self._mint(
                False,
                "FROZEN_INDETERMINATE",
                "HALT_INDETERMINATE_REQUIRES_RECONCILIATION",
                intent_caid,
            )

        # Rule 12: Token persisted to disk from another session cannot authorize a future session
        effective_session = caller_session_id or self.active_session_id
        if envelope.session_id != effective_session:
            self._intent_state[intent_caid] = "DENIED_TERMINAL"
            return self._mint(
                False,
                "DENIED_TERMINAL",
                f"HALT_STALE_SESSION_TOKEN:expected_{effective_session}_got_{envelope.session_id}",
                intent_caid,
            )

        # Rule 2: Temporal validity window check
        if current_epoch_sec < envelope.not_before_epoch_sec:
            return self._mint(
                False,
                curr_state,
                f"HALT_INTENT_PREMATURE:now={current_epoch_sec}<not_before={envelope.not_before_epoch_sec}",
                intent_caid,
            )
        if current_epoch_sec > envelope.expires_at_epoch_sec:
            self._intent_state[intent_caid] = "EXPIRED_NEEDS_REAUTH"
            return self._mint(
                False,
                "EXPIRED_NEEDS_REAUTH",
                f"HALT_INTENT_EXPIRED:now={current_epoch_sec}>expires_at={envelope.expires_at_epoch_sec}",
                intent_caid,
            )

        # Scope checks
        if requested_host not in envelope.scope.allowed_hosts:
            self._intent_state[intent_caid] = "DENIED_TERMINAL"
            return self._mint(
                False,
                "DENIED_TERMINAL",
                f"HALT_SCOPE_HOST_DENIED:{requested_host}",
                intent_caid,
            )
        if requested_tool not in envelope.scope.allowed_tools:
            self._intent_state[intent_caid] = "DENIED_TERMINAL"
            return self._mint(
                False,
                "DENIED_TERMINAL",
                f"HALT_SCOPE_TOOL_DENIED:{requested_tool}",
                intent_caid,
            )
        if requested_amount_minor > envelope.scope.max_amount_minor:
            self._intent_state[intent_caid] = "DENIED_TERMINAL"
            return self._mint(
                False,
                "DENIED_TERMINAL",
                f"HALT_SCOPE_AMOUNT_EXCEEDED:{requested_amount_minor}>{envelope.scope.max_amount_minor}",
                intent_caid,
            )

        # Live preconditions check: failure at T0 latches DENIED_TERMINAL
        for cond_name, required_val in sorted(envelope.preconditions.items()):
            live_val = live_preconditions.get(cond_name)
            if live_val is None or live_val != required_val:
                self._intent_state[intent_caid] = "DENIED_TERMINAL"
                return self._mint(
                    False,
                    "DENIED_TERMINAL",
                    f"HALT_PRECONDITION_DENIED_TERMINAL:{cond_name}",
                    intent_caid,
                )

        # Rule 13: Retry ceiling & single commit enforcement
        attempts = self._attempt_counts.get(intent_caid, 0)
        if attempts > envelope.max_retries:
            self._intent_state[intent_caid] = "DENIED_TERMINAL"
            return self._mint(
                False,
                "DENIED_TERMINAL",
                f"HALT_RETRY_BUDGET_EXHAUSTED:{attempts}>{envelope.max_retries}",
                intent_caid,
            )

        self._attempt_counts[intent_caid] = attempts + 1
        self._intent_state[intent_caid] = "COMMITTED"
        return self._mint(True, "COMMITTED", "OK_TEMPORAL_AUTHORITY_COMMITTED", intent_caid)

    def suspend_intent(self, intent_caid: str) -> str:
        if intent_caid not in self._intent_registry:
            raise KeyError(f"ERR_UNKNOWN_INTENT:{intent_caid}")
        self._intent_state[intent_caid] = "FROZEN_INDETERMINATE"
        return "FROZEN_INDETERMINATE"

    def resume_and_reconcile_snapshot(
        self,
        intent_caid: str,
        current_epoch_sec: int,
        live_preconditions: Mapping[str, bool],
        reconciliation_probe_status: str,
    ) -> TemporalGuardVerdict:
        """
        Enforces Rules 2, 3 & 14 on Snapshot Resume:
          - If expired while suspended -> HALT_EXPIRED_SNAPSHOT_INTENT_REQUIRES_REAUTHORIZATION.
          - If preconditions fail -> DENIED_TERMINAL.
          - If probe is UNKNOWN -> remain FROZEN_INDETERMINATE (actor kept halted).
          - If probe is EXECUTED -> transition to COMMITTED (no duplicate retry).
          - If probe is NOT_EXECUTED -> restore to INTENT_REGISTERED for single retry.
        """
        envelope = self._intent_registry.get(intent_caid)
        if not envelope:
            return self._mint(False, "DENIED_TERMINAL", "HALT_INTENT_NOT_FOUND", intent_caid)

        if current_epoch_sec > envelope.expires_at_epoch_sec:
            self._intent_state[intent_caid] = "EXPIRED_NEEDS_REAUTH"
            return self._mint(
                False,
                "EXPIRED_NEEDS_REAUTH",
                "HALT_EXPIRED_SNAPSHOT_INTENT_REQUIRES_REAUTHORIZATION",
                intent_caid,
            )

        for cond_name, required_val in sorted(envelope.preconditions.items()):
            if live_preconditions.get(cond_name) != required_val:
                self._intent_state[intent_caid] = "DENIED_TERMINAL"
                return self._mint(
                    False,
                    "DENIED_TERMINAL",
                    f"HALT_RESUME_PRECONDITION_FAILED:{cond_name}",
                    intent_caid,
                )

        if reconciliation_probe_status == "UNKNOWN":
            self._intent_state[intent_caid] = "FROZEN_INDETERMINATE"
            return self._mint(
                False,
                "FROZEN_INDETERMINATE",
                "HALT_RECONCILIATION_UNKNOWN_KEEP_HALTED",
                intent_caid,
            )

        if reconciliation_probe_status == "EXECUTED":
            self._intent_state[intent_caid] = "COMMITTED"
            return self._mint(
                False,
                "COMMITTED",
                "OK_RECONCILED_ALREADY_EXECUTED_NO_RETRY",
                intent_caid,
            )

        if reconciliation_probe_status == "NOT_EXECUTED":
            self._intent_state[intent_caid] = "INTENT_REGISTERED"
            return self._mint(
                True,
                "INTENT_REGISTERED",
                "OK_SNAPSHOT_RECONCILED_SINGLE_RETRY_PERMITTED",
                intent_caid,
            )

        raise ValueError(f"ERR_INVALID_PROBE_STATUS:{reconciliation_probe_status}")

    def verify_delegation_monotonicity(
        self,
        parent_envelope: TemporalIntentEnvelope,
        child_envelope: TemporalIntentEnvelope,
    ) -> TemporalGuardVerdict:
        # Rule 11: Child scope must be a subset of parent scope
        if not child_envelope.scope.is_subset_of(parent_envelope.scope):
            return self._mint(
                False,
                "DENIED_TERMINAL",
                "HALT_DELEGATION_SCOPE_VIOLATION:Child_exceeds_Parent",
                child_envelope.intent_caid,
            )

        # Rule 10: Delegated child cannot outlive parent authorization
        if child_envelope.expires_at_epoch_sec > parent_envelope.expires_at_epoch_sec:
            return self._mint(
                False,
                "DENIED_TERMINAL",
                f"HALT_DELEGATION_EXPIRY_VIOLATION:Child={child_envelope.expires_at_epoch_sec}>Parent={parent_envelope.expires_at_epoch_sec}",
                child_envelope.intent_caid,
            )

        if child_envelope.issued_at_epoch_sec < parent_envelope.issued_at_epoch_sec:
            return self._mint(
                False,
                "DENIED_TERMINAL",
                "HALT_DELEGATION_ISSUED_BEFORE_PARENT",
                child_envelope.intent_caid,
            )

        # Rule 11: Child taint must be >= parent taint
        if child_envelope.taint_level < parent_envelope.taint_level:
            return self._mint(
                False,
                "DENIED_TERMINAL",
                f"HALT_DELEGATION_TAINT_DECREASE:Child={child_envelope.taint_level}<Parent={parent_envelope.taint_level}",
                child_envelope.intent_caid,
            )

        if (
            not child_envelope.delegation_chain
            or child_envelope.delegation_chain[-1] != parent_envelope.intent_caid
        ):
            return self._mint(
                False,
                "DENIED_TERMINAL",
                "HALT_DELEGATION_CHAIN_DISCONNECTED",
                child_envelope.intent_caid,
            )

        return self._mint(
            True,
            "INTENT_REGISTERED",
            "OK_DELEGATION_MONOTONIC",
            child_envelope.intent_caid,
        )

    @staticmethod
    def evaluate_persistence_write(file_path: str) -> Tuple[bool, str]:
        """
        Rule 4: Blocks writes to cron, systemd units, launchd plists, shell rc files,
        and SSH authorized_keys.
        """
        norm = file_path.replace("\\", "/").lower()
        for marker in FORBIDDEN_PERSISTENCE_PATH_MARKERS:
            if marker in norm:
                return False, f"HALT_PERSISTENCE_WRITE_DENIED:{marker}"
        return True, "OK_STORAGE_WRITE_PERMITTED"

    def evaluate_network_and_dns_egress(
        self,
        actor_spiffe_id: str,
        protocol: str,
        destination_host: str,
        allowed_hosts: FrozenSet[str],
        dns_record_type: str = "A",
        dns_query_wire_len: int = 0,
    ) -> Tuple[bool, str]:
        """
        Rules 6, 7, 8 & 9:
          - Denies raw UDP and ICMP egress unconditionally.
          - Restricts DNS to A/AAAA records, query wire length <= 128 bytes,
            max label length <= 52 chars, allowlisted domains, and per-actor rate limits.
          - Enforces destination allowlist on TCP.
        """
        proto = protocol.upper()
        if proto in ("UDP", "ICMP"):
            return False, f"HALT_RAW_PROTOCOL_DENIED:{proto}"

        if proto == "DNS":
            if dns_record_type.upper() not in self.ALLOWED_DNS_TYPES:
                return False, f"HALT_DNS_RECORD_TYPE_DENIED:{dns_record_type}"

            if (
                dns_query_wire_len > self.DNS_MAX_QUERY_LENGTH
                or len(destination_host) > self.DNS_MAX_QUERY_LENGTH
            ):
                return (
                    False,
                    f"HALT_DNS_TUNNEL_OVERSIZED_QUERY:{max(dns_query_wire_len, len(destination_host))}",
                )

            labels = destination_host.split(".")
            if any(len(lbl) > self.DNS_MAX_LABEL_LENGTH for lbl in labels):
                return False, "HALT_DNS_TUNNEL_HIGH_ENTROPY_SUBDOMAIN"

            if destination_host not in allowed_hosts:
                return False, f"HALT_DNS_DOMAIN_NOT_ALLOWLISTED:{destination_host}"

            count = self._dns_window_counts.get(actor_spiffe_id, 0) + 1
            self._dns_window_counts[actor_spiffe_id] = count
            if count > self.dns_max_queries_per_window:
                return (
                    False,
                    f"HALT_DNS_TUNNEL_RATE_LIMIT_EXCEEDED:{count}>{self.dns_max_queries_per_window}",
                )
            return True, "OK_DNS_RESOLUTION_PERMITTED"

        if proto == "TCP":
            if destination_host not in allowed_hosts:
                return False, f"HALT_EGRESS_DESTINATION_DENIED:{destination_host}"
            return True, "OK_TCP_EGRESS_PERMITTED"

        return False, f"HALT_UNKNOWN_PROTOCOL:{proto}"

    @classmethod
    def audit_ast_for_async_daemons(
        cls, source_code: str, file_path: str = "<memory>"
    ) -> Tuple[bool, str]:
        """
        Rule 5: Scans Python AST for detached child processes, schedulers, timers,
        and deferred time.sleep calls.
        """
        try:
            tree = ast.parse(source_code, filename=file_path)
        except SyntaxError as exc:
            return False, f"HALT_SYNTAX_ERROR:{exc.msg}"

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    if root_mod in BANNED_ASYNC_MODULES:
                        return False, f"HALT_FORBIDDEN_ASYNC_MODULE:{root_mod}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                root_mod = node.module.split(".")[0]
                if root_mod in BANNED_ASYNC_MODULES:
                    return False, f"HALT_FORBIDDEN_ASYNC_MODULE:{root_mod}"

            if isinstance(node, ast.Call):
                func_name = None
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name in BANNED_ASYNC_CALLS:
                    return False, f"HALT_FORBIDDEN_ASYNC_INVOCATION:{func_name}"

                for kw in node.keywords:
                    if (
                        kw.arg in ("daemon", "start_new_session")
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value is True
                    ):
                        return False, f"HALT_DETACHED_PROCESS_KEYWORD:{kw.arg}"

                if (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "time"
                    and node.func.attr == "sleep"
                ):
                    return False, "HALT_DEFERRED_SLEEP_BLOCKED"

        return True, "OK_AST_CLEAN"

    @staticmethod
    def _mint(
        authorized: bool, state: str, status_code: str, intent_caid: str
    ) -> TemporalGuardVerdict:
        payload: Dict[str, Any] = {
            "authorized": authorized,
            "intent_caid": intent_caid,
            "state": state,
            "status_code": status_code,
        }
        return TemporalGuardVerdict(
            authorized=authorized,
            state=state,
            status_code=status_code,
            intent_caid=intent_caid,
            verdict_caid=sha256_caid(payload),
        )
