# Copyright 2026 SovereignNexus Project
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""
src/specification_invariant_compiler.py
================================================================================
Phase IX Specification Invariant Compiler, Dual-Anchored SCITT Custodian,
Transitive Kernel Closure Auditor & Orthogonal EffSMS Attestation.

Engineering Status: INTERNAL PREVIEW COMMISSIONED (Prototype & Specification Invariant Compiler Scaffold)
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Subsystems:
1. AgentCoordinationContract & SpecificationInvariantCompiler:
   Pre-execution specification & coordination invariant enforcement addressing
   plan-execution mismatch, step repetition loops, and termination vs. completion
   postcondition conflation (UC Berkeley MAST taxonomy).
2. ExternalSCITTRegistrar & DualAnchoredSCITTReceipt:
   Cryptographic separation of Agent Operator (Issuer) and Independent Evidence
   Custodian (Transparency Service) with RFC 9162 inclusion proofs and Ed25519
   Signed Tree Heads (IETF SCITT architecture).
3. TransitiveKernelClosureAuditor:
   Transitive import closure verification across compiled module nodes (.olean
   digest pinning, @[implemented_by]/@[extern] rejection, native_decide trust
   expansion blocking, and transitive axiom/sorry/admit/unsafe detection).
4. IndependentMutationAttestation & AdaptiveMutationOperatorRegistry:
   Dual-engine semantic mutation adequacy (EffSMS integer basis points) and
   retroactive escaped-defect merge scanning.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs
from src.scitt_proof_aggregation_reconciler import (
    build_audit_path,
    compute_sub_root,
    hash_leaf,
    verify_inclusion_proof,
)
from src.temporal_authority_guard import sha256_caid


# ==============================================================================
# Pivot 1: AgentCoordinationContract & SpecificationInvariantCompiler
# ==============================================================================


@dataclass(frozen=True)
class AgentCoordinationContract:
    """Pre-execution multi-agent specification and coordination contract."""

    contract_id: str
    max_steps: int
    max_identical_step_repeats: int
    planned_phase_tools: Mapping[str, Tuple[str, ...]]
    termination_state_keys: Tuple[str, ...]
    completion_postcondition_keys: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.contract_id:
            raise ValueError("ERR_EMPTY_CONTRACT_ID")
        if self.max_steps <= 0:
            raise ValueError("ERR_INVALID_MAX_STEPS")
        if self.max_identical_step_repeats < 1:
            raise ValueError("ERR_INVALID_MAX_IDENTICAL_STEP_REPEATS")
        if not self.planned_phase_tools:
            raise ValueError("ERR_EMPTY_PLANNED_PHASE_TOOLS")
        if not self.termination_state_keys:
            raise ValueError("ERR_EMPTY_TERMINATION_STATE_KEYS")
        if not self.completion_postcondition_keys:
            raise ValueError("ERR_EMPTY_COMPLETION_POSTCONDITION_KEYS")

    @property
    def contract_caid(self) -> str:
        """Compute deterministic RFC 8785 JCS CAID for this coordination contract."""
        return sha256_caid(
            {
                "completion_postcondition_keys": list(self.completion_postcondition_keys),
                "contract_id": self.contract_id,
                "max_identical_step_repeats": self.max_identical_step_repeats,
                "max_steps": self.max_steps,
                "planned_phase_tools": {
                    phase: list(tools)
                    for phase, tools in sorted(self.planned_phase_tools.items())
                },
                "termination_state_keys": list(self.termination_state_keys),
            }
        )


@dataclass(frozen=True)
class CoordinationStepVerdict:
    """Deterministic step-evaluation verdict produced by SpecificationInvariantCompiler."""

    allowed: bool
    status_code: str
    violation_reason: str
    step_index: int
    contract_caid: str
    verdict_caid: str


class SpecificationInvariantCompiler:
    """Stateful pre-execution invariant monitor for agent coordination steps."""

    def __init__(self, contract: AgentCoordinationContract) -> None:
        self.contract = contract
        self._step_count: int = 0
        self._action_counts: Dict[str, int] = {}

    def _build_verdict(
        self, allowed: bool, status_code: str, violation_reason: str
    ) -> CoordinationStepVerdict:
        c_caid = self.contract.contract_caid
        v_caid = sha256_caid(
            {
                "allowed": allowed,
                "contract_caid": c_caid,
                "status_code": status_code,
                "step_index": self._step_count,
                "violation_reason": violation_reason,
            }
        )
        return CoordinationStepVerdict(
            allowed=allowed,
            status_code=status_code,
            violation_reason=violation_reason,
            step_index=self._step_count,
            contract_caid=c_caid,
            verdict_caid=v_caid,
        )

    def evaluate_step(
        self,
        plan_phase: str,
        tool_id: str,
        action_payload: Mapping[str, Any],
        state_flags: Mapping[str, bool],
        claim_task_completed: bool = False,
    ) -> CoordinationStepVerdict:
        """Evaluate a proposed agent step against the compiled coordination contract."""
        self._step_count += 1

        if self._step_count > self.contract.max_steps:
            return self._build_verdict(
                False,
                "HALT_COORDINATION_INVARIANT_VIOLATED",
                "REASON_STEP_BUDGET_EXCEEDED",
            )

        if plan_phase not in self.contract.planned_phase_tools:
            return self._build_verdict(
                False,
                "HALT_COORDINATION_INVARIANT_VIOLATED",
                "REASON_UNKNOWN_PLAN_PHASE",
            )

        allowed_tools = self.contract.planned_phase_tools[plan_phase]
        if tool_id not in allowed_tools:
            return self._build_verdict(
                False,
                "HALT_COORDINATION_INVARIANT_VIOLATED",
                "REASON_PLAN_EXECUTION_MISMATCH",
            )

        action_fp = sha256_caid(
            {
                "payload": dict(action_payload),
                "phase": plan_phase,
                "tool": tool_id,
            }
        )
        repeat_count = self._action_counts.get(action_fp, 0) + 1
        self._action_counts[action_fp] = repeat_count
        if repeat_count > self.contract.max_identical_step_repeats:
            return self._build_verdict(
                False,
                "HALT_COORDINATION_INVARIANT_VIOLATED",
                "REASON_STEP_REPETITION_LOOP",
            )

        termination_signaled = any(
            bool(state_flags.get(key, False))
            for key in self.contract.termination_state_keys
        )
        if claim_task_completed or termination_signaled:
            postconditions_met = all(
                bool(state_flags.get(key, False))
                for key in self.contract.completion_postcondition_keys
            )
            if not postconditions_met:
                return self._build_verdict(
                    False,
                    "HALT_COORDINATION_INVARIANT_VIOLATED",
                    "REASON_COMPLETION_POSTCONDITION_UNMET",
                )
            return self._build_verdict(
                True,
                "ALLOW_COORDINATION_CONTRACT_SATISFIED",
                "NONE",
            )

        return self._build_verdict(
            True,
            "ALLOW_STEP_IN_SPEC",
            "NONE",
        )


# ==============================================================================
# Pivot 2: ExternalSCITTRegistrar & DualAnchoredSCITTReceipt
# ==============================================================================


@dataclass(frozen=True)
class DualAnchoredSCITTReceipt:
    """Dual-anchored IETF SCITT receipt separating Operator Issuer from Custodian."""

    receipt_id: str
    operator_payload_caid: str
    operator_public_key_hex: str
    operator_signature_hex: str
    custodian_service_id: str
    custodian_public_key_hex: str
    leaf_index: int
    tree_size: int
    leaf_hash_hex: str
    inclusion_audit_path_hex: Tuple[str, ...]
    tree_root_hex: str
    custodian_sth_signature_hex: str
    dual_receipt_caid: str


def _public_key_hex(private_key: ed25519.Ed25519PrivateKey) -> str:
    return (
        private_key.public_key()
        .public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        .hex()
    )


class ExternalSCITTRegistrar:
    """Independent SCITT Transparency Service registrar enforcing custodian separation."""

    def __init__(
        self,
        custodian_service_id: str,
        custodian_private_key: ed25519.Ed25519PrivateKey,
    ) -> None:
        if not custodian_service_id:
            raise ValueError("ERR_EMPTY_CUSTODIAN_SERVICE_ID")
        self.custodian_service_id = custodian_service_id
        self._custodian_private_key = custodian_private_key
        self._leaves: List[bytes] = []

    def register_operator_receipt(
        self,
        receipt_id: str,
        payload: Mapping[str, Any],
        operator_private_key: ed25519.Ed25519PrivateKey,
    ) -> DualAnchoredSCITTReceipt:
        """Sign and append an operator statement into the independent custodian Merkle log."""
        operator_pub_hex = _public_key_hex(operator_private_key)
        custodian_pub_hex = _public_key_hex(self._custodian_private_key)
        if operator_pub_hex == custodian_pub_hex:
            raise ValueError(
                "ERR_SELF_CUSTODY_FORBIDDEN:operator_and_custodian_keys_must_be_distinct"
            )

        operator_payload_caid = sha256_caid(payload)
        canonical_payload = encode_jcs(payload)
        op_sig_hex = operator_private_key.sign(canonical_payload).hex()

        leaf_entry = encode_jcs(
            {
                "operator_payload_caid": operator_payload_caid,
                "operator_public_key_hex": operator_pub_hex,
                "operator_signature_hex": op_sig_hex,
                "receipt_id": receipt_id,
            }
        )
        leaf_bytes = hash_leaf(leaf_entry)
        self._leaves.append(leaf_bytes)

        tree_size = len(self._leaves)
        leaf_index = tree_size - 1
        root_bytes = compute_sub_root(self._leaves)
        audit_path: List[bytes] = []
        build_audit_path(self._leaves, leaf_index, audit_path)

        sth_bytes = encode_jcs(
            {
                "custodian_service_id": self.custodian_service_id,
                "tree_root_hex": root_bytes.hex(),
                "tree_size": tree_size,
            }
        )
        custodian_sth_sig_hex = self._custodian_private_key.sign(sth_bytes).hex()
        audit_path_hex = tuple(node.hex() for node in audit_path)

        dual_caid = sha256_caid(
            {
                "custodian_public_key_hex": custodian_pub_hex,
                "custodian_service_id": self.custodian_service_id,
                "custodian_sth_signature_hex": custodian_sth_sig_hex,
                "inclusion_audit_path_hex": list(audit_path_hex),
                "leaf_hash_hex": leaf_bytes.hex(),
                "leaf_index": leaf_index,
                "operator_payload_caid": operator_payload_caid,
                "operator_public_key_hex": operator_pub_hex,
                "operator_signature_hex": op_sig_hex,
                "receipt_id": receipt_id,
                "tree_root_hex": root_bytes.hex(),
                "tree_size": tree_size,
            }
        )

        return DualAnchoredSCITTReceipt(
            receipt_id=receipt_id,
            operator_payload_caid=operator_payload_caid,
            operator_public_key_hex=operator_pub_hex,
            operator_signature_hex=op_sig_hex,
            custodian_service_id=self.custodian_service_id,
            custodian_public_key_hex=custodian_pub_hex,
            leaf_index=leaf_index,
            tree_size=tree_size,
            leaf_hash_hex=leaf_bytes.hex(),
            inclusion_audit_path_hex=audit_path_hex,
            tree_root_hex=root_bytes.hex(),
            custodian_sth_signature_hex=custodian_sth_sig_hex,
            dual_receipt_caid=dual_caid,
        )

    @staticmethod
    def verify_dual_anchored_receipt(
        receipt: DualAnchoredSCITTReceipt,
        payload: Mapping[str, Any],
        pinned_operator_pub_hex: str,
        pinned_custodian_pub_hex: str,
    ) -> Tuple[bool, str]:
        """Verify operator signature, RFC 9162 inclusion proof, and independent custodian STH."""
        if pinned_operator_pub_hex == pinned_custodian_pub_hex:
            return False, "ERR_SELF_CUSTODY_FORBIDDEN"

        if (
            receipt.operator_public_key_hex != pinned_operator_pub_hex
            or receipt.custodian_public_key_hex != pinned_custodian_pub_hex
        ):
            return False, "ERR_KEY_PIN_MISMATCH"

        if sha256_caid(payload) != receipt.operator_payload_caid:
            return False, "ERR_PAYLOAD_CAID_MISMATCH"

        try:
            op_pub = ed25519.Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(pinned_operator_pub_hex)
            )
            op_pub.verify(
                bytes.fromhex(receipt.operator_signature_hex),
                encode_jcs(payload),
            )
        except (InvalidSignature, ValueError):
            return False, "ERR_INVALID_OPERATOR_SIGNATURE"

        expected_leaf = hash_leaf(
            encode_jcs(
                {
                    "operator_payload_caid": receipt.operator_payload_caid,
                    "operator_public_key_hex": receipt.operator_public_key_hex,
                    "operator_signature_hex": receipt.operator_signature_hex,
                    "receipt_id": receipt.receipt_id,
                }
            )
        )
        if expected_leaf.hex() != receipt.leaf_hash_hex:
            return False, "ERR_INCLUSION_PROOF_INVALID"

        inclusion_ok = verify_inclusion_proof(
            expected_leaf,
            receipt.leaf_index,
            receipt.tree_size,
            [bytes.fromhex(h) for h in receipt.inclusion_audit_path_hex],
            bytes.fromhex(receipt.tree_root_hex),
        )
        if not inclusion_ok:
            return False, "ERR_INCLUSION_PROOF_INVALID"

        try:
            custodian_pub = ed25519.Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(pinned_custodian_pub_hex)
            )
            sth_bytes = encode_jcs(
                {
                    "custodian_service_id": receipt.custodian_service_id,
                    "tree_root_hex": receipt.tree_root_hex,
                    "tree_size": receipt.tree_size,
                }
            )
            custodian_pub.verify(
                bytes.fromhex(receipt.custodian_sth_signature_hex),
                sth_bytes,
            )
        except (InvalidSignature, ValueError):
            return False, "ERR_INVALID_CUSTODIAN_STH_SIGNATURE"

        return True, "VERIFIED_DUAL_ANCHORED_SCITT_RECEIPT"


# ==============================================================================
# Pivot 3: TransitiveKernelClosureAuditor
# ==============================================================================

_AXIOM_SORRY_RE = re.compile(r"\b(?:sorry|admit|axiom|unsafe)\b")
_OVERRIDE_PATTERNS: Tuple[str, ...] = ("@[implemented_by", "@[extern")
_NATIVE_DECIDE_PATTERNS: Tuple[str, ...] = (
    "native_decide",
    "Lean.ofReduceBool",
    "Lean.ofReduceNat",
    "._native.",
)


@dataclass(frozen=True)
class CompiledModuleNode:
    """Compiled proof module node within the transitive kernel import graph."""

    module_name: str
    imports: Tuple[str, ...]
    source_text: str
    olean_symbols: Tuple[str, ...] = ()
    olean_bytes_sha256: str = ""
    olean_Declarations: Tuple[str, ...] = ()


@dataclass(frozen=True)
class KernelClosureAuditVerdict:
    """Verdict returned by TransitiveKernelClosureAuditor."""

    verified: bool
    status_code: str
    violation_reason: str
    offending_module: str
    audited_module_count: int
    closure_caid: str


class TransitiveKernelClosureAuditor:
    """Audits the full reachable import closure for sound proof-kernel execution."""

    def audit_closure(
        self,
        root_module: str,
        closure_map: Mapping[str, CompiledModuleNode],
        pinned_olean_digests: Mapping[str, str],
    ) -> KernelClosureAuditVerdict:
        """Traverse transitive imports from root_module and reject trust-chain bypasses."""
        visited: Set[str] = set()
        queue: List[str] = [root_module]
        ordered_modules: List[str] = []

        while queue:
            current_name = queue.pop(0)
            if current_name in visited:
                continue
            visited.add(current_name)
            ordered_modules.append(current_name)

            if current_name not in closure_map:
                return self._verdict(
                    False,
                    "HALT_KERNEL_TRUST_CHAIN_VIOLATION",
                    "REASON_INCOMPLETE_CLOSURE_GRAPH",
                    current_name,
                    len(ordered_modules),
                )

            node = closure_map[current_name]
            expected_digest = pinned_olean_digests.get(current_name)
            if expected_digest is None or node.olean_bytes_sha256 != expected_digest:
                return self._verdict(
                    False,
                    "HALT_KERNEL_TRUST_CHAIN_VIOLATION",
                    "REASON_OLEAN_DIGEST_MISMATCH",
                    current_name,
                    len(ordered_modules),
                )

            combined_surface = "\n".join(
                (node.source_text, *node.olean_symbols, *node.olean_Declarations)
            )

            if any(pat in combined_surface for pat in _OVERRIDE_PATTERNS):
                return self._verdict(
                    False,
                    "HALT_KERNEL_TRUST_CHAIN_VIOLATION",
                    "REASON_IMPLEMENTED_BY_OR_EXTERN_OVERRIDE",
                    current_name,
                    len(ordered_modules),
                )

            if any(pat in combined_surface for pat in _NATIVE_DECIDE_PATTERNS):
                return self._verdict(
                    False,
                    "HALT_KERNEL_TRUST_CHAIN_VIOLATION",
                    "REASON_NATIVE_DECIDE_COMPILER_TRUST_EXPANSION",
                    current_name,
                    len(ordered_modules),
                )

            if _AXIOM_SORRY_RE.search(combined_surface):
                return self._verdict(
                    False,
                    "HALT_KERNEL_TRUST_CHAIN_VIOLATION",
                    "REASON_TRANSITIVE_AXIOM_OR_SORRY",
                    current_name,
                    len(ordered_modules),
                )

            for dep in node.imports:
                if dep not in visited:
                    queue.append(dep)

        return self._verdict(
            True,
            "ALLOW_TRANSITIVE_CLOSURE_CLEAN",
            "NONE",
            "",
            len(ordered_modules),
        )

    @staticmethod
    def _verdict(
        verified: bool,
        status_code: str,
        violation_reason: str,
        offending_module: str,
        audited_module_count: int,
    ) -> KernelClosureAuditVerdict:
        caid = sha256_caid(
            {
                "audited_module_count": audited_module_count,
                "offending_module": offending_module,
                "status_code": status_code,
                "verified": verified,
                "violation_reason": violation_reason,
            }
        )
        return KernelClosureAuditVerdict(
            verified=verified,
            status_code=status_code,
            violation_reason=violation_reason,
            offending_module=offending_module,
            audited_module_count=audited_module_count,
            closure_caid=caid,
        )


# ==============================================================================
# Auxiliary 4 & 5: IndependentMutationAttestation & AdaptiveMutationOperatorRegistry
# ==============================================================================


@dataclass(frozen=True)
class ClassifiedMutantOutcome:
    """Single mutant execution outcome with SecMutBench semantic kill classification."""

    mutant_id: str
    engine_id: str
    file_path: str
    killed: bool
    kill_category: str
    is_security_sensitive: bool


class IndependentMutationAttestation:
    """Evaluates dual-engine mutation adequacy using semantic kill share (EffSMS)."""

    @staticmethod
    def evaluate_dual_engine_attestation(
        primary_engine_id: str,
        secondary_engine_id: str,
        outcomes: Sequence[ClassifiedMutantOutcome],
        min_eff_sms_bps: int = 7000,  # claim: config
        min_semantic_share_bps: int = 7000,  # claim: config
    ) -> Dict[str, Any]:
        """Require two distinct engines, zero security survivors, and EffSMS thresholds."""
        if not primary_engine_id or not secondary_engine_id:
            return {
                "authorized": False,
                "status_code": "BLOCK_SINGLE_ENGINE_OR_EMPTY",
                "eff_sms_bps": 0,  # claim: config
                "semantic_share_of_kills_bps": 0,  # claim: config
            }
        if primary_engine_id == secondary_engine_id:
            return {
                "authorized": False,
                "status_code": "BLOCK_SINGLE_ENGINE_OR_EMPTY",
                "eff_sms_bps": 0,  # claim: config
                "semantic_share_of_kills_bps": 0,  # claim: config
            }

        has_primary = any(o.engine_id == primary_engine_id for o in outcomes)
        has_secondary = any(o.engine_id == secondary_engine_id for o in outcomes)
        if not has_primary or not has_secondary:
            return {
                "authorized": False,
                "status_code": "BLOCK_SINGLE_ENGINE_OR_EMPTY",
                "eff_sms_bps": 0,  # claim: config
                "semantic_share_of_kills_bps": 0,  # claim: config
            }

        total_mutants = len(outcomes)
        total_kills = 0
        semantic_kills = 0
        for outcome in outcomes:
            if outcome.killed and outcome.kill_category != "SURVIVED":
                total_kills += 1
                if outcome.kill_category == "SEMANTIC":
                    semantic_kills += 1
        eff_sms_bps = (semantic_kills * 10000) // total_mutants
        semantic_share_of_kills_bps = (
            (semantic_kills * 10000) // total_kills if total_kills > 0 else 0
        )

        for outcome in outcomes:
            if outcome.is_security_sensitive and (
                not outcome.killed or outcome.kill_category == "SURVIVED"
            ):
                return {
                    "authorized": False,
                    "status_code": "BLOCK_SECURITY_SURVIVOR",
                    "eff_sms_bps": eff_sms_bps,
                    "semantic_share_of_kills_bps": semantic_share_of_kills_bps,
                }

        if (
            eff_sms_bps < min_eff_sms_bps
            or semantic_share_of_kills_bps < min_semantic_share_bps
        ):
            return {
                "authorized": False,
                "status_code": "BLOCK_LOW_SEMANTIC_KILL_SHARE",
                "eff_sms_bps": eff_sms_bps,
                "semantic_share_of_kills_bps": semantic_share_of_kills_bps,
            }

        return {
            "authorized": True,
            "status_code": "ALLOW_DUAL_ENGINE_SEMANTIC_ATTESTED",
            "eff_sms_bps": eff_sms_bps,
            "semantic_share_of_kills_bps": semantic_share_of_kills_bps,
        }


class AdaptiveMutationOperatorRegistry:
    """Maintains escaped-defect patterns and scans historical merges for retroactive advisories."""

    def __init__(self) -> None:
        self._operators: List[Tuple[str, str, str]] = []

    def register_escaped_defect(
        self, operator_id: str, pattern_substring: str, cve_or_incident_ref: str
    ) -> None:
        """Register a newly discovered escaped-defect pattern into the operator set."""
        if not operator_id or not pattern_substring or not cve_or_incident_ref:
            raise ValueError("ERR_EMPTY_ESCAPED_DEFECT_SPEC")
        self._operators.append((operator_id, pattern_substring, cve_or_incident_ref))

    def scan_historical_merges(
        self, merges: Sequence[Mapping[str, str]]
    ) -> List[Dict[str, str]]:
        """Scan historical merge records and emit RETROACTIVE_ADVISORY_REQUIRED matches."""
        advisories: List[Dict[str, str]] = []
        for merge in merges:
            merge_id = merge.get("merge_id", "")
            source_text = merge.get("source_text", "")
            for operator_id, pattern_substring, cve_ref in self._operators:
                if pattern_substring in source_text:
                    advisories.append(
                        {
                            "advisory_status": "RETROACTIVE_ADVISORY_REQUIRED",
                            "cve_or_incident_ref": cve_ref,
                            "merge_id": merge_id,
                            "operator_id": operator_id,
                        }
                    )
        return advisories
