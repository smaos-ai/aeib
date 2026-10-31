#!/usr/bin/env python3
"""
SovereignNexus Phase V Unified 5-Station Execution Kernel (src/sovereign_phase_v_kernel.py).

Status: INTERNAL PREVIEW COMMISSIONED
Evaluated under the stated model to unify the 5-Station Autonomous Software Factory
into a single deterministic pipeline:
  - Station 0 (Token & Temporal Truth Intake):
      Executes TokenEconomizerGovernor (AST-diff slicing, log compaction, tool pruning,
      prefix-cache alignment) AND TemporalGraphRouter Truth Decay verification
      (blocking stale legitimate memory via HALT_STALE_MEMORY_NEEDS_RESEARCH).
  - Station 1 (Temporal Authority & Cryptographic Delegation Latch):
      Verifies TemporalIntentEnvelope via TemporalAuthorityGuard (terminal denial latch,
      [not_before, expires_at] TTL, preconditions, session binding).
  - Station 2 (Untrusted Proposal Envelope):
      Binds candidate code and target path to a pre-execution SHA-256 CAID.
  - Station 3 (AST Purity, Async/Daemon Time-Bomb & Persistence Gate):
      Blocks subprocess/fork/setsid/timers/time.sleep and persistence path writes
      (/etc/cron*, systemd, launchd, .bashrc, .ssh/authorized_keys).
  - Station 4 (Network/DNS Egress Gate & RFC 8785 Canonical Audit Receipt):
      Enforces TCP/DNS allowlists (blocking UDP/ICMP and DNS tunneling) and emits an
      immutable RFC 8785 JCS execution receipt with zero floats.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Dict, FrozenSet, Mapping, Optional

from src.jcs_canonicalizer import encode_jcs
from src.sovereign_token_decree import TokenEconomizerGovernor
from src.temporal_authority_guard import (
    TemporalAuthorityGuard,
    TemporalIntentEnvelope,
    sha256_caid,
)
from src.temporal_graph_router import TemporalChunkRecord, TemporalGraphRouter


@dataclasses.dataclass(frozen=True)
class PhaseVKernelReceipt:
    """RFC 8785 canonical receipt across all 5 stations (zero floats, integer bps)."""

    permitted: bool
    halted_at_station: int  # 0..4 for halt station, or 5 when all stations pass
    status_code: str
    intent_caid: str
    proposal_caid: str
    token_savings_bps: int
    memory_confidence_bps: int
    receipt_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "halted_at_station": self.halted_at_station,
            "intent_caid": self.intent_caid,
            "memory_confidence_bps": self.memory_confidence_bps,
            "permitted": self.permitted,
            "proposal_caid": self.proposal_caid,
            "receipt_caid": self.receipt_caid,
            "status_code": self.status_code,
            "token_savings_bps": self.token_savings_bps,
        }


class SovereignPhaseVKernel:
    """
    Unified 5-Station Sovereign Execution Kernel.
    Treats LLM outputs strictly as untrusted stochastic proposals and enforces
    deterministic gates at every station before execution.
    """

    def __init__(
        self,
        authority_guard: TemporalAuthorityGuard,
        token_governor: Optional[TokenEconomizerGovernor] = None,
    ) -> None:
        self.authority_guard = authority_guard
        self.token_governor = token_governor or TokenEconomizerGovernor()

    def execute_five_station_pipeline(
        self,
        *,
        task_id: str,
        static_system_prefix: str,
        task_description: str,
        all_tool_schemas: Mapping[str, Dict[str, Any]],
        old_file_code: str,
        candidate_code: str,
        raw_test_log: str,
        memory_chunk: TemporalChunkRecord,
        current_epoch_sec: int,
        max_memory_ttl_sec: int,
        intent_envelope: TemporalIntentEnvelope,
        live_preconditions: Mapping[str, bool],
        target_file_path: str,
        requested_tool: str,
        requested_amount_minor: int,
        network_protocol: str = "TCP",
        destination_host: str = "api.stripe.com",
        dns_record_type: str = "A",
        dns_query_wire_len: int = 32,
    ) -> PhaseVKernelReceipt:
        """
        Executes Stations 0 through 4 in strict sequence. Any station abnormality
        halts the pipeline fail-closed and emits a signed/CAID-addressed receipt.
        """
        intent_caid = intent_envelope.intent_caid
        proposal_caid = sha256_caid(
            {"candidate_code": candidate_code, "target_file_path": target_file_path}
        )

        # ── STATION 0: Token Economizer & Temporal Memory Truth Decay ─────────
        _, tok_receipt = self.token_governor.optimize_turn_context(
            task_id=task_id,
            static_system_prefix=static_system_prefix,
            task_description=task_description,
            all_tool_schemas=all_tool_schemas,
            old_file_code=old_file_code,
            new_file_code=candidate_code,
            raw_test_log=raw_test_log,
        )
        if not tok_receipt.prefix_cache_aligned:
            return self._seal(
                permitted=False,
                halted_at_station=0,
                status_code="HALT_STATION_0_PREFIX_CACHE_CONTAMINATED",
                intent_caid=intent_caid,
                proposal_caid=proposal_caid,
                token_savings_bps=tok_receipt.savings_bps,
                memory_confidence_bps=0,
            )
        if tok_receipt.loop_halted:
            return self._seal(
                permitted=False,
                halted_at_station=0,
                status_code="HALT_STATION_0_REPETITIVE_ERROR_LOOP",
                intent_caid=intent_caid,
                proposal_caid=proposal_caid,
                token_savings_bps=tok_receipt.savings_bps,
                memory_confidence_bps=0,
            )

        mem_ok, mem_conf_bps, mem_code = TemporalGraphRouter.evaluate_memory_truth_decay(
            chunk=memory_chunk,
            current_epoch_sec=current_epoch_sec,
            max_api_ttl_sec=max_memory_ttl_sec,
        )
        if not mem_ok:
            return self._seal(
                permitted=False,
                halted_at_station=0,
                status_code=mem_code,
                intent_caid=intent_caid,
                proposal_caid=proposal_caid,
                token_savings_bps=tok_receipt.savings_bps,
                memory_confidence_bps=mem_conf_bps,
            )

        # ── STATION 1: Temporal Authority & Precondition Latch ────────────────
        # If not yet registered, register first; if already registered (e.g. after prior denial),
        # preserve existing terminal state in authority_guard.
        if self.authority_guard.get_intent_state(intent_caid) == "UNREGISTERED":
            reg_verdict = self.authority_guard.register_intent(intent_envelope)
            if not reg_verdict.authorized:
                return self._seal(
                    permitted=False,
                    halted_at_station=1,
                    status_code=reg_verdict.status_code,
                    intent_caid=intent_caid,
                    proposal_caid=proposal_caid,
                    token_savings_bps=tok_receipt.savings_bps,
                    memory_confidence_bps=mem_conf_bps,
                )

        # ── STATION 3 (Pre-Commit AST & Storage Persistence Check) ────────────
        # Evaluate AST and persistence path before marking the intent COMMITTED so
        # a malicious code proposal never transitions the intent to COMMITTED.
        persist_ok, persist_code = TemporalAuthorityGuard.evaluate_persistence_write(
            target_file_path
        )
        if not persist_ok:
            return self._seal(
                permitted=False,
                halted_at_station=3,
                status_code=persist_code,
                intent_caid=intent_caid,
                proposal_caid=proposal_caid,
                token_savings_bps=tok_receipt.savings_bps,
                memory_confidence_bps=mem_conf_bps,
            )

        ast_ok, ast_code = TemporalAuthorityGuard.audit_ast_for_async_daemons(
            candidate_code, file_path=target_file_path
        )
        if not ast_ok:
            return self._seal(
                permitted=False,
                halted_at_station=3,
                status_code=ast_code,
                intent_caid=intent_caid,
                proposal_caid=proposal_caid,
                token_savings_bps=tok_receipt.savings_bps,
                memory_confidence_bps=mem_conf_bps,
            )

        # ── STATION 4 (Pre-Commit Network & DNS Tunneling Gate) ───────────────
        net_ok, net_code = self.authority_guard.evaluate_network_and_dns_egress(
            actor_spiffe_id=intent_envelope.actor_spiffe_id,
            protocol=network_protocol,
            destination_host=destination_host,
            allowed_hosts=frozenset(intent_envelope.scope.allowed_hosts),
            dns_record_type=dns_record_type,
            dns_query_wire_len=dns_query_wire_len,
        )
        if not net_ok:
            return self._seal(
                permitted=False,
                halted_at_station=4,
                status_code=net_code,
                intent_caid=intent_caid,
                proposal_caid=proposal_caid,
                token_savings_bps=tok_receipt.savings_bps,
                memory_confidence_bps=mem_conf_bps,
            )

        # ── STATION 1/2/4 Final Atomic Temporal Dispatch Commit ───────────────
        dispatch_verdict = self.authority_guard.evaluate_temporal_dispatch(
            intent_caid=intent_caid,
            current_epoch_sec=current_epoch_sec,
            live_preconditions=live_preconditions,
            requested_host=destination_host,
            requested_tool=requested_tool,
            requested_amount_minor=requested_amount_minor,
        )
        if not dispatch_verdict.authorized:
            return self._seal(
                permitted=False,
                halted_at_station=1,
                status_code=dispatch_verdict.status_code,
                intent_caid=intent_caid,
                proposal_caid=proposal_caid,
                token_savings_bps=tok_receipt.savings_bps,
                memory_confidence_bps=mem_conf_bps,
            )

        return self._seal(
            permitted=True,
            halted_at_station=5,
            status_code="OK_ALL_5_STATIONS_VERIFIED_AND_COMMITTED",
            intent_caid=intent_caid,
            proposal_caid=proposal_caid,
            token_savings_bps=tok_receipt.savings_bps,
            memory_confidence_bps=mem_conf_bps,
        )

    @staticmethod
    def _seal(
        *,
        permitted: bool,
        halted_at_station: int,
        status_code: str,
        intent_caid: str,
        proposal_caid: str,
        token_savings_bps: int,
        memory_confidence_bps: int,
    ) -> PhaseVKernelReceipt:
        core: Dict[str, Any] = {
            "halted_at_station": halted_at_station,
            "intent_caid": intent_caid,
            "memory_confidence_bps": memory_confidence_bps,
            "permitted": permitted,
            "proposal_caid": proposal_caid,
            "status_code": status_code,
            "token_savings_bps": token_savings_bps,
        }
        return PhaseVKernelReceipt(
            permitted=permitted,
            halted_at_station=halted_at_station,
            status_code=status_code,
            intent_caid=intent_caid,
            proposal_caid=proposal_caid,
            token_savings_bps=token_savings_bps,
            memory_confidence_bps=memory_confidence_bps,
            receipt_caid=sha256_caid(encode_jcs(core)),
        )
