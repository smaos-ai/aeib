#!/usr/bin/env python3
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
src/industrial_dev_flow_engine.py
================================================================================
Industrial Software Development Cycle Commissioning Engine.

Evaluated under the stated model (Nuclear 10 CFR 50 App B, IEEE 603, DO-178C DAL A,
and IEEE C37.2 Protection Principles adapted to Autonomous AI Engineering).

Core Architectural Invariants:
  1. Zero Trust on Probabilistic Model Tokens:
     LLM outputs carry zero inherent authority. The deterministic harness alone
     evaluates truth, correctness, and execution readiness.
  2. Plane 1 (Poka-Yoke Spec Boundaries):
     Strict input validation rejects unfloored domains, float money values,
     and ambiguous execution scopes before candidate generation begins.
  3. Plane 2 (Recursive 5-Whys Causal DAG):
     Decomposes complex problems into an acyclic dependency graph of atomic
     tasks with independent verification postconditions.
  4. Plane 3 (Process Isolation):
     Untrusted code runs in process-isolated environments with zero network egress.
  5. Plane 4 (Class 1E Protection & ANSI 86 Lockout Relay):
     - ANSI 50 Instantaneous Trip: Scaffolds, stubs, and syntax errors trip immediately.
     - Test-Tamper Trip: Modification of pinned evaluation tests trips fail-closed.
     - ANSI 86 Lockout Relay: Exceeding B <= 3 repair attempts permanently latches
       the task into EFFECT_INDETERMINATE_LOCKOUT. Automated retries are refused
       until cleared by an out-of-band operator cryptographic signature.
  6. Plane 5 (Cryptographic Commissioning Receipt):
     Successful candidates are sealed with RFC 8785 JCS canonical bytes and an
     Ed25519 signature over deterministic outcome CAIDs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs
from src.scaffold_detector import detect_scaffolds


class TripReasonCode(str, Enum):
    """Deterministic trip codes for dev-flow protection trips."""

    TRIP_SPEC_VALIDATION_FAILED = "TRIP_SPEC_VALIDATION_FAILED"
    TRIP_DAG_CYCLE_DETECTED = "TRIP_DAG_CYCLE_DETECTED"
    TRIP_DAG_DEPENDENCY_UNSATISFIED = "TRIP_DAG_DEPENDENCY_UNSATISFIED"
    TRIP_SCAFFOLD_DETECTED = "TRIP_SCAFFOLD_DETECTED"
    TRIP_TEST_TAMPER_DETECTED = "TRIP_TEST_TAMPER_DETECTED"
    TRIP_SCOPE_VIOLATION = "TRIP_SCOPE_VIOLATION"
    TRIP_MUTATION_INADEQUATE = "TRIP_MUTATION_INADEQUATE"
    TRIP_SYNTAX_ERROR = "TRIP_SYNTAX_ERROR"
    TRIP_EXECUTION_FAILURE = "TRIP_EXECUTION_FAILURE"
    TRIP_ANSI_86_LOCKOUT = "TRIP_ANSI_86_LOCKOUT"


@dataclass(frozen=True)
class TaskSpec:
    """Formal Poka-Yoke specification contract for an autonomous task."""

    task_id: str
    description: str
    editable_files: Tuple[str, ...]
    pinned_test_hashes: Mapping[str, str]
    domain_floor_min_cardinality: int = 4
    required_boundary_values: Tuple[int, ...] = (-1, 0, 1, 2)

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, str) or not self.task_id.strip():
            raise ValueError("ERR_INVALID_TASK_ID: task_id must be non-empty string")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("ERR_INVALID_DESCRIPTION: description must be non-empty string")
        if not isinstance(self.editable_files, (tuple, list)) or not self.editable_files:
            raise ValueError("ERR_EMPTY_SCOPE: editable_files must define at least one target path")
        for f in self.editable_files:
            if not isinstance(f, str) or not f.strip():
                raise ValueError("ERR_INVALID_EDITABLE_FILE: file paths must be non-empty strings")
        if type(self.domain_floor_min_cardinality) is not int or self.domain_floor_min_cardinality <= 0:
            raise ValueError("ERR_INVALID_DOMAIN_FLOOR: domain floor cardinality must be positive integer")
        if not isinstance(self.required_boundary_values, (tuple, list)) or len(self.required_boundary_values) < 2:
            raise ValueError("ERR_INVALID_BOUNDARY_VALUES: required_boundary_values must contain at least 2 elements")
        if 0 not in self.required_boundary_values or 2 not in self.required_boundary_values:
            raise ValueError("ERR_MISSING_BOUNDARY: boundary values must include 0 and 2")


@dataclass(frozen=True)
class DAGNode:
    """An atomic step in the 5-Whys recursive decomposition."""

    node_id: str
    why_level: int  # 1 to 5
    hypothesis_or_action: str
    dependencies: Tuple[str, ...] = ()
    verified: bool = False


@dataclass
class FiveWhysDecompositionDAG:
    """Directed Acyclic Graph of 5-Whys causal decomposition."""

    nodes: Dict[str, DAGNode] = field(default_factory=dict)

    def add_node(
        self,
        node_id: str,
        why_level: int,
        hypothesis_or_action: str,
        dependencies: Tuple[str, ...] = (),
    ) -> None:
        if why_level < 1 or why_level > 5:
            raise ValueError(f"ERR_INVALID_WHY_LEVEL: {why_level} must be between 1 and 5")
        if node_id in self.nodes:
            raise ValueError(f"ERR_DUPLICATE_NODE_ID: {node_id}")
        for dep in dependencies:
            if dep not in self.nodes:
                raise ValueError(f"ERR_UNRESOLVED_DEPENDENCY: {dep} not present in DAG")

        node = DAGNode(
            node_id=node_id,
            why_level=why_level,
            hypothesis_or_action=hypothesis_or_action,
            dependencies=dependencies,
            verified=False,
        )
        self.nodes[node_id] = node

    def is_acyclic(self) -> bool:
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def _dfs(curr: str) -> bool:
            visited.add(curr)
            rec_stack.add(curr)
            for dep in self.nodes[curr].dependencies:
                if dep not in visited:
                    if _dfs(dep) is True:
                        return True
                elif dep in rec_stack:
                    return True
            rec_stack.remove(curr)
            return False

        for node_id in self.nodes:
            if node_id not in visited:
                if _dfs(node_id):
                    return False
        return True


@dataclass(frozen=True)
class IndustrialCommissionVerdict:
    """Cryptographic outcome verdict of the industrial dev-flow evaluation."""

    task_id: str
    approved: bool
    disposition: str
    trip_code: Optional[str]
    attempt_count: int
    lockout_latched: bool
    mutation_kill_ratio_bps: int
    deterministic_outcome_caid: str
    provenance_signature_hex: str
    authority_public_key_hex: str

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "attempt_count": self.attempt_count,
            "authority_public_key_hex": self.authority_public_key_hex,
            "deterministic_outcome_caid": self.deterministic_outcome_caid,
            "disposition": self.disposition,
            "lockout_latched": self.lockout_latched,
            "mutation_kill_ratio_bps": self.mutation_kill_ratio_bps,
            "provenance_signature_hex": self.provenance_signature_hex,
            "task_id": self.task_id,
            "trip_code": self.trip_code if self.trip_code is not None else "NONE",
        }


def lockout_clearance_message(task_id: str, nonce: str) -> bytes:
    """Canonical RFC 8785 bytes an operator signs to clear one task's ANSI 86 latch.

    Binding task_id and a single-use nonce prevents replaying a clearance for
    task A against task B, or replaying the same clearance twice.
    """
    if not isinstance(task_id, str) or not task_id:
        raise ValueError("ERR_INVALID_TASK_ID")
    if not isinstance(nonce, str) or not nonce:
        raise ValueError("ERR_INVALID_CLEARANCE_NONCE")
    return encode_jcs({"action": "ANSI_86_CLEAR_LOCKOUT", "nonce": nonce, "task_id": task_id})


def _normalize_sha256(value: str) -> str:
    return value[len("sha256:"):] if value.startswith("sha256:") else value


class IndustrialDevFlowGovernor:
    """Governor enforcing the 5-plane industrial software development lifecycle.

    Limits (stated, not hidden): ``mutation_kill_ratio_bps`` and
    ``execution_passed`` are evidence supplied by the caller; this governor
    adjudicates them but cannot recompute them. They must come from the
    out-of-process runners (tools/mutation_adequacy_gate.py,
    benchmarks/scaffold_depth_v2/score_v2.py). ``candidate_files`` is also
    caller-supplied; score_v2 diffs a real tree instead. Pinned test files,
    however, are hashed by the governor itself from ``repo_root``.
    """

    MAX_REPAIR_ATTEMPTS: int = 3
    MIN_MUTATION_KILL_RATIO_BPS: int = 9000  # claim: config - 90.00% minimum kill ratio

    def __init__(
        self,
        authority_private_key: Optional[ed25519.Ed25519PrivateKey] = None,
        *,
        operator_public_keys_hex: Tuple[str, ...],
    ) -> None:
        if not isinstance(operator_public_keys_hex, (tuple, list)) or not operator_public_keys_hex:
            raise ValueError("ERR_NO_PINNED_OPERATOR_KEYS")
        pinned: Set[str] = set()
        for key_hex in operator_public_keys_hex:
            if not isinstance(key_hex, str) or len(key_hex) != 64:
                raise ValueError("ERR_INVALID_OPERATOR_KEY")
            ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(key_hex))
            pinned.add(key_hex.lower())
        self._operator_keys: frozenset = frozenset(pinned)

        self._priv_key = authority_private_key or ed25519.Ed25519PrivateKey.generate()
        self._pub_key = self._priv_key.public_key()
        self._pub_hex = self._pub_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex()

        self._task_attempts: Dict[str, int] = {}
        self._lockout_relays: Dict[str, bool] = {}  # task_id -> is_locked_out
        self._used_clearance_nonces: Set[Tuple[str, str]] = set()

    @property
    def authority_public_key_hex(self) -> str:
        return self._pub_hex

    def is_locked_out(self, task_id: str) -> bool:
        """Checks if the ANSI 86 Lockout Relay is tripped for a task."""
        return self._lockout_relays.get(task_id, False)

    def operator_clear_lockout(
        self,
        task_id: str,
        nonce: str,
        operator_signature_hex: str,
        operator_public_key_hex: str,
    ) -> bool:
        """Clears an ANSI 86 lockout with a pinned operator's Ed25519 signature.

        Returns False (no state change) when the task is not latched, the key is
        not pinned at construction, the nonce was already used for this task,
        or the signature does not cover ``lockout_clearance_message(task_id, nonce)``.
        """
        if not self.is_locked_out(task_id):
            return False
        if not isinstance(operator_public_key_hex, str) or \
                operator_public_key_hex.lower() not in self._operator_keys:
            return False
        if (task_id, nonce) in self._used_clearance_nonces:
            return False
        try:
            message = lockout_clearance_message(task_id, nonce)
            op_pub = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(operator_public_key_hex))
            op_pub.verify(bytes.fromhex(operator_signature_hex), message)
        except (ValueError, TypeError, InvalidSignature):
            return False

        self._used_clearance_nonces.add((task_id, nonce))
        self._lockout_relays[task_id] = False
        self._task_attempts[task_id] = 0
        return True

    @staticmethod
    def _hash_pinned_tests(spec: TaskSpec, repo_root: Path) -> Dict[str, Optional[str]]:
        """Hashes each pinned test file from disk; None for missing or escaping paths."""
        root = Path(repo_root).resolve()
        out: Dict[str, Optional[str]] = {}
        for rel in spec.pinned_test_hashes:
            target = (root / rel).resolve()
            if root != target and root not in target.parents:
                out[rel] = None
                continue
            try:
                out[rel] = hashlib.sha256(target.read_bytes()).hexdigest()
            except OSError:
                out[rel] = None
        return out

    def evaluate_candidate(
        self,
        spec: TaskSpec,
        candidate_files: Mapping[str, str],
        baseline_files: Mapping[str, str],
        *,
        repo_root: Path,
        mutation_kill_ratio_bps: int,
        execution_passed: bool,
    ) -> IndustrialCommissionVerdict:
        """Evaluates an untrusted candidate against all industrial protection planes."""
        if type(mutation_kill_ratio_bps) is not int or not 0 <= mutation_kill_ratio_bps <= 10000:
            raise ValueError("ERR_INVALID_MUTATION_BPS")
        if type(execution_passed) is not bool:
            raise ValueError("ERR_INVALID_EXECUTION_PASSED")
        active_test_hashes = self._hash_pinned_tests(spec, repo_root)
        task_id = spec.task_id

        # 0. Check ANSI 86 Lockout Relay state
        if self.is_locked_out(task_id):
            return self._build_verdict(
                task_id=task_id,
                approved=False,
                disposition="REJECTED_LOCKED_OUT",
                trip_code=TripReasonCode.TRIP_ANSI_86_LOCKOUT,
                lockout_latched=True,
                mutation_kill_ratio_bps=0,
            )

        attempts = self._task_attempts.get(task_id, 0) + 1
        self._task_attempts[task_id] = attempts

        trip: Optional[TripReasonCode] = None
        disposition = "PENDING"

        # 1. Plane 1 Scope Violation Check
        for changed_file in candidate_files:
            if changed_file not in spec.editable_files:
                trip = TripReasonCode.TRIP_SCOPE_VIOLATION
                disposition = f"REJECTED_UNAUTHORIZED_SCOPE:{changed_file}"
                break

        # 2. Plane 4B Test Tamper Detection
        if trip is None:
            for test_path, pinned_hash in spec.pinned_test_hashes.items():
                active_hash = active_test_hashes.get(test_path)
                if active_hash is None or active_hash != _normalize_sha256(pinned_hash).lower():
                    trip = TripReasonCode.TRIP_TEST_TAMPER_DETECTED
                    disposition = f"REJECTED_TEST_TAMPER:{test_path}"
                    break

        # 3. Plane 4A AST Scaffold & Stub Detection
        if trip is None:
            for filepath, candidate_src in candidate_files.items():
                base_src = baseline_files.get(filepath, "")
                result = detect_scaffolds(
                    before_source=base_src,
                    after_source=candidate_src,
                    is_test_file=False,
                    test_doubles_allowed=False,
                )
                if any(f.category == "SYNTAX_ERROR" for f in result.findings):
                    trip = TripReasonCode.TRIP_SYNTAX_ERROR
                    disposition = f"REJECTED_SYNTAX_ERROR:{filepath}"
                    break
                if result.scaffold_count > 0:
                    trip = TripReasonCode.TRIP_SCAFFOLD_DETECTED
                    disposition = f"REJECTED_SCAFFOLD_PRESENT:{result.findings[0].category}"
                    break

        # 4. Plane 4 Dynamic Execution Verification
        if trip is None:
            if not execution_passed:
                trip = TripReasonCode.TRIP_EXECUTION_FAILURE
                disposition = "REJECTED_TEST_SUITE_FAILED"

        # 5. Plane 4C Mutation Adequacy Threshold Check
        if trip is None:
            if mutation_kill_ratio_bps < self.MIN_MUTATION_KILL_RATIO_BPS:
                trip = TripReasonCode.TRIP_MUTATION_INADEQUATE
                disposition = (
                    f"REJECTED_MUTATION_INADEQUATE:{mutation_kill_ratio_bps}bps"
                )

        # Adjudicate Pass / Fail
        approved = trip is None
        if approved:
            disposition = "COMMISSIONED_VERIFIED_OUTCOME"
            lockout = False
        else:
            # Check ANSI 86 trip condition: B <= 3 repair limit exceeded
            if attempts >= self.MAX_REPAIR_ATTEMPTS:
                self._lockout_relays[task_id] = True
                trip = TripReasonCode.TRIP_ANSI_86_LOCKOUT
                disposition = f"LATCHED_ANSI_86_LOCKOUT_AFTER_{attempts}_ATTEMPTS"
                lockout = True
            else:
                lockout = False

        return self._build_verdict(
            task_id=task_id,
            approved=approved,
            disposition=disposition,
            trip_code=trip,
            lockout_latched=lockout,
            mutation_kill_ratio_bps=mutation_kill_ratio_bps if approved else 0,
        )

    def _build_verdict(
        self,
        task_id: str,
        approved: bool,
        disposition: str,
        trip_code: Optional[TripReasonCode],
        lockout_latched: bool,
        mutation_kill_ratio_bps: int,
    ) -> IndustrialCommissionVerdict:
        raw_outcomes = {
            "approved": approved,
            "disposition": disposition,
            "lockout_latched": lockout_latched,
            "mutation_kill_ratio_bps": mutation_kill_ratio_bps,
            "task_id": task_id,
            "trip_code": trip_code.value if trip_code is not None else "NONE",
        }
        outcome_bytes = encode_jcs(raw_outcomes)
        outcome_caid = "sha256:" + hashlib.sha256(outcome_bytes).hexdigest()

        # Sign canonical outcome digest with authority Ed25519 key
        sig_bytes = self._priv_key.sign(outcome_bytes)

        return IndustrialCommissionVerdict(
            task_id=task_id,
            approved=approved,
            disposition=disposition,
            trip_code=trip_code.value if trip_code is not None else None,
            attempt_count=self._task_attempts.get(task_id, 0),
            lockout_latched=lockout_latched,
            mutation_kill_ratio_bps=mutation_kill_ratio_bps,
            deterministic_outcome_caid=outcome_caid,
            provenance_signature_hex=sig_bytes.hex(),
            authority_public_key_hex=self._pub_hex,
        )
