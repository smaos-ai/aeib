#!/usr/bin/env python3
# File: src/wave7_steward_sphinx_and_escalation.py
"""
Wave 7 prototype gates (evaluated under the stated model; prototype, not a sandbox).

1. StewardInvariantCoreGuard: path-scoped self-modification policy separating an
   immutable core from a reflective shell (pattern from arXiv:2610.30557; the 30 bps
   default drawdown cap is a configured value, not a number taken from that paper).
2. NonPenalizedBlockerEscalationGate: a non-penalized "escalate" outcome for broken
   tests / contradictory specs. The gate itself computes the tests-manifest digest
   and runs the named failing test out-of-process; it does not trust agent-reported
   booleans. Motivation: arXiv:2608.29460 (escalation channel + policy reduced test
   cheating in that study); no effect on our agents has been measured.
3. SphinxCognitiveDebtGate: structured reviewer attestation. The expected answers
   are computable by anyone running the same AST extractor (including an agent), so
   a match shows the attestation was filled in against the real code; it does NOT
   measure human comprehension.
4. ShadowWorkflowAndIncidentEmitter: records unmapped workflow transitions and emits
   Ed25519-signed internal incident notices. The field set is our own; it is not an
   official EU AI Act Art. 73 or bilateral-government template.

All canonical serialization routes through src.jcs_canonicalizer.encode_jcs
(single source, RFC 8785); floats are rejected before hashing.
"""
from __future__ import annotations

import ast
import hashlib
import hmac
import os
import posixpath
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.jcs_canonicalizer import encode_jcs

_SHA256_CAID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _reject_floats(node: Any) -> None:
    if isinstance(node, float):
        raise ValueError("ERR_FLOAT_FORBIDDEN_IN_JCS")
    if isinstance(node, dict):
        for value in node.values():
            _reject_floats(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            _reject_floats(item)


def sha256_jcs_caid(payload: Any) -> str:
    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        _reject_floats(payload)
        raw = encode_jcs(payload)
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _is_strict_int(value: Any) -> bool:
    return type(value) is int


def _canonicalize_repo_path(target_path: Any) -> Tuple[Optional[str], str]:
    """Fail-closed lexical canonicalization of a repo-relative POSIX path."""
    if not isinstance(target_path, str) or not target_path:
        return None, "HALT_ABSOLUTE_OR_EMPTY_REFLECTION_PATH"
    if target_path.startswith("/") or "\x00" in target_path:
        return None, "HALT_ABSOLUTE_OR_EMPTY_REFLECTION_PATH"
    if "\\" in target_path:
        return None, "HALT_BACKSLASH_PATH_SEPARATOR_FORBIDDEN"
    normed = posixpath.normpath(target_path)
    if normed == ".." or normed.startswith("../"):
        return None, "HALT_PATH_TRAVERSAL_IN_REFLECTION_TARGET"
    if normed != target_path:
        return None, "HALT_NON_CANONICAL_REFLECTION_PATH"
    return normed, ""


# ============================================================================
# 1. Steward invariant core vs reflective shell
# ============================================================================


@dataclass(frozen=True)
class StewardReflectionProposal:
    proposal_id: str
    target_path: str
    memory_layer: int
    proposed_max_drawdown_bps: int
    proposed_diff_summary: str


@dataclass(frozen=True)
class StewardEvolutionVerdict:
    allowed: bool
    zone_classification: str
    reason_code: str
    receipt_caid: str


class StewardInvariantCoreGuard:
    """
    Lexical policy plus optional filesystem check. When `repo_root` is given, the
    resolved real path must equal the lexical path (no symlink redirection out of
    the shell). Core-prefix matching is case-insensitive because APFS/NTFS default
    volumes are case-insensitive; shell matching stays case-sensitive (fail closed).
    """

    IMMUTABLE_CORE_PREFIXES: Tuple[str, ...] = (
        "src/jcs_canonicalizer.py",
        "src/eo1_write_before_execute.py",
        "src/pre_tool_use_chain.py",
        "src/parallel_tracks_abcde_engine.py",
        "src/wave7_steward_sphinx_and_escalation.py",
        "compliance/",
        "tests/",
    )
    ALLOWED_SHELL_PREFIXES: Tuple[str, ...] = (
        ".agents/skills/generated/",
        "memory/reflective_layer_",
        "docs/notes/",
    )

    def __init__(
        self, hard_max_drawdown_cap_bps: int = 30, repo_root: Optional[str] = None
    ) -> None:
        if (
            not _is_strict_int(hard_max_drawdown_cap_bps)
            or hard_max_drawdown_cap_bps <= 0
            or hard_max_drawdown_cap_bps > 5000
        ):
            raise ValueError("ERR_INVALID_DRAWDOWN_CAP_BPS")
        self.hard_max_drawdown_cap_bps = hard_max_drawdown_cap_bps
        self.repo_root = os.path.realpath(repo_root) if repo_root is not None else None

    def _verdict(
        self, allowed: bool, zone: str, reason: str, caid: str
    ) -> StewardEvolutionVerdict:
        return StewardEvolutionVerdict(allowed, zone, reason, caid)

    def evaluate_reflection(
        self, proposal: StewardReflectionProposal
    ) -> StewardEvolutionVerdict:
        caid = sha256_jcs_caid(
            {
                "memory_layer": proposal.memory_layer,
                "proposal_id": proposal.proposal_id,
                "proposed_diff_summary": proposal.proposed_diff_summary,
                "proposed_max_drawdown_bps": proposal.proposed_max_drawdown_bps,
                "target_path": proposal.target_path,
            }
        )
        if (
            not _is_strict_int(proposal.memory_layer)
            or proposal.memory_layer < 1
            or proposal.memory_layer > 7
        ):
            return self._verdict(
                False, "INVALID_LAYER", "HALT_STEWARD_MEMORY_LAYER_OUT_OF_RANGE", caid
            )

        normed, halt_reason = _canonicalize_repo_path(proposal.target_path)
        if normed is None:
            return self._verdict(False, "INVARIANT_CORE", halt_reason, caid)

        folded = normed.casefold()
        for core_prefix in self.IMMUTABLE_CORE_PREFIXES:
            if folded.startswith(core_prefix.casefold()):
                return self._verdict(
                    False, "INVARIANT_CORE", f"HALT_INVARIANT_CORE_IMMUTABLE:{normed}", caid
                )

        if (
            not _is_strict_int(proposal.proposed_max_drawdown_bps)
            or proposal.proposed_max_drawdown_bps < 0
            or proposal.proposed_max_drawdown_bps > self.hard_max_drawdown_cap_bps
        ):
            return self._verdict(False, "INVARIANT_CORE", "HALT_STEWARD_RISK_CAP_BREACH", caid)

        if not any(normed.startswith(p) for p in self.ALLOWED_SHELL_PREFIXES):
            return self._verdict(
                False, "UNCLASSIFIED_PATH", f"HALT_PATH_OUTSIDE_REFLECTIVE_SHELL:{normed}", caid
            )

        if self.repo_root is not None:
            resolved = os.path.realpath(os.path.join(self.repo_root, normed))
            expected = os.path.join(self.repo_root, normed)
            if resolved != expected:
                return self._verdict(
                    False, "INVARIANT_CORE", "HALT_SYMLINK_REDIRECT_IN_REFLECTION_TARGET", caid
                )

        return self._verdict(True, "REFLECTIVE_SHELL", "OK_STEWARD_SHELL_EVOLUTION_AUTHORIZED", caid)


# ============================================================================
# 2. Non-penalized blocker escalation (gate-computed evidence)
# ============================================================================


def compute_tests_manifest_digest(tests_root: str) -> str:
    """sha256 over JCS of sorted (relative POSIX path, file sha256) for every
    regular file under tests_root. Symlinks are refused (fail closed)."""
    root = Path(tests_root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("ERR_TESTS_ROOT_NOT_A_DIRECTORY")
    rows: List[List[str]] = []
    for path in sorted(root.rglob("*")):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise ValueError("ERR_SYMLINK_IN_TESTS_MANIFEST")
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            rows.append([rel, hashlib.sha256(path.read_bytes()).hexdigest()])
    return sha256_jcs_caid({"files": rows})


@dataclass(frozen=True)
class BlockerEscalationPacket:
    task_id: str
    spec_caid: str
    failing_test_id: str
    contradiction_kind: str
    minimal_reproducer_code: str
    observed_assertion_error: str


@dataclass(frozen=True)
class EscalationGateVerdict:
    terminal_disposition: str
    agent_penalized: bool
    escalation_receipt_caid: str


class NonPenalizedBlockerEscalationGate:
    """
    Accepts an escalation only when (a) the tests manifest digest computed now equals
    the baseline recorded by the harness before the agent ran, (b) the named failing
    test actually exits with pytest code 1 when run in a separate interpreter
    (process isolation, not a sandbox; empty env, timeout), and (c) the reproducer
    parses and contains an assert/raise. (c) is a structural hint only; it does not
    show the reproducer reproduces the failure. Residual: an agent that edits src/
    to break a test still passes (a)-(b); the escalation goes to a human anyway.
    """

    VALID_KINDS: FrozenSet[str] = frozenset(
        {"BROKEN_TEST_ORACLE", "CONTRADICTORY_SPEC", "MISSING_FIXTURE"}
    )
    _NODEID_RE = re.compile(r"^tests/[A-Za-z0-9_/]+\.py::[A-Za-z0-9_\[\]-]+$")

    def __init__(
        self,
        project_root: str,
        baseline_tests_manifest_digest: str,
        test_timeout_s: int = 60,
    ) -> None:
        if not _SHA256_CAID_RE.match(baseline_tests_manifest_digest or ""):
            raise ValueError("ERR_INVALID_BASELINE_MANIFEST_DIGEST")
        if not _is_strict_int(test_timeout_s) or test_timeout_s <= 0:
            raise ValueError("ERR_INVALID_TEST_TIMEOUT")
        self.project_root = os.path.realpath(project_root)
        self.baseline_tests_manifest_digest = baseline_tests_manifest_digest
        self.test_timeout_s = test_timeout_s

    def _run_failing_test(self, node_id: str) -> int:
        try:
            completed = subprocess.run(
                [sys.executable, "-I", "-m", "pytest", "-q", "-p", "no:cacheprovider", node_id],
                cwd=self.project_root,
                env={"PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                timeout=self.test_timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return -1
        return completed.returncode

    def evaluate_escalation(self, packet: BlockerEscalationPacket) -> EscalationGateVerdict:
        caid = sha256_jcs_caid(
            {
                "contradiction_kind": packet.contradiction_kind,
                "failing_test_id": packet.failing_test_id,
                "minimal_reproducer_code": packet.minimal_reproducer_code,
                "observed_assertion_error": packet.observed_assertion_error,
                "spec_caid": packet.spec_caid,
                "task_id": packet.task_id,
            }
        )

        def halt(code: str) -> EscalationGateVerdict:
            return EscalationGateVerdict(code, True, caid)

        current = compute_tests_manifest_digest(os.path.join(self.project_root, "tests"))
        if not hmac.compare_digest(current, self.baseline_tests_manifest_digest):
            return halt("HALT_REWARD_HACKING_TEST_TAMPER_DURING_ESCALATION")
        if packet.contradiction_kind not in self.VALID_KINDS:
            return halt("HALT_INVALID_CONTRADICTION_KIND")
        if not packet.observed_assertion_error.strip():
            return halt("HALT_EMPTY_ASSERTION_EVIDENCE")
        try:
            tree = ast.parse(packet.minimal_reproducer_code)
        except SyntaxError:
            return halt("HALT_INVALID_REPRODUCER_SYNTAX")
        if not tree.body:
            return halt("HALT_EMPTY_REPRODUCER_AST")
        if not any(isinstance(n, (ast.Assert, ast.Raise)) for n in ast.walk(tree)):
            return halt("HALT_REPRODUCER_LACKS_ASSERT_OR_RAISE")
        if not self._NODEID_RE.match(packet.failing_test_id):
            return halt("HALT_INVALID_FAILING_TEST_ID")
        exit_code = self._run_failing_test(packet.failing_test_id)
        if exit_code == -1:
            return halt("HALT_FAILING_TEST_TIMEOUT")
        if exit_code != 1:
            return halt(f"HALT_NAMED_TEST_DID_NOT_FAIL:exit_{exit_code}")
        return EscalationGateVerdict("ESCALATED_CLEANLY_NO_PENALTY", False, caid)


# ============================================================================
# 3. Sphinx structured reviewer attestation
# ============================================================================


@dataclass(frozen=True)
class ComprehensionQuizChallenge:
    challenge_caid: str
    expected_function_names: Tuple[str, ...]
    expected_halt_codes: Tuple[str, ...]
    expected_integer_constants: Tuple[int, ...]


class SphinxCognitiveDebtGate:
    """See module docstring: attestation, not a comprehension measurement."""

    @staticmethod
    def extract_ast_challenge(python_source: str) -> ComprehensionQuizChallenge:
        tree = ast.parse(python_source)
        parent_map: Dict[int, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parent_map[id(child)] = node

        fn_names: List[str] = []
        halt_codes: List[str] = []
        int_consts: List[int] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_names.append(node.name)
            elif isinstance(node, ast.Constant):
                if isinstance(node.value, str) and node.value.startswith("HALT_"):
                    halt_codes.append(node.value)
                elif _is_strict_int(node.value):
                    value = node.value
                    parent = parent_map.get(id(node))
                    if isinstance(parent, ast.UnaryOp) and isinstance(parent.op, ast.USub):
                        value = -value
                        parent = parent_map.get(id(parent))
                    if value not in (0, 1) or isinstance(parent, ast.Compare):
                        int_consts.append(value)

        sorted_fns = tuple(sorted(set(fn_names)))
        sorted_halts = tuple(sorted(set(halt_codes)))
        sorted_ints = tuple(sorted(set(int_consts)))
        caid = sha256_jcs_caid(
            {
                "functions": list(sorted_fns),
                "halt_codes": list(sorted_halts),
                "int_constants": list(sorted_ints),
            }
        )
        return ComprehensionQuizChallenge(caid, sorted_fns, sorted_halts, sorted_ints)

    @classmethod
    def verify_reviewer_attestation(
        cls,
        python_source: str,
        attested_functions: Sequence[str],
        attested_halt_codes: Sequence[str],
        attested_int_constants: Sequence[int],
    ) -> Tuple[bool, str, str]:
        challenge = cls.extract_ast_challenge(python_source)
        if tuple(sorted(set(attested_functions))) != challenge.expected_function_names:
            return False, "HALT_COGNITIVE_DEBT_FUNCTION_MISMATCH", challenge.challenge_caid
        if tuple(sorted(set(attested_halt_codes))) != challenge.expected_halt_codes:
            return False, "HALT_COGNITIVE_DEBT_HALT_CODE_MISMATCH", challenge.challenge_caid
        if tuple(sorted(set(attested_int_constants))) != challenge.expected_integer_constants:
            return False, "HALT_COGNITIVE_DEBT_CONSTANT_MISMATCH", challenge.challenge_caid
        return True, "OK_REVIEWER_ATTESTATION_MATCHES_AST", challenge.challenge_caid


# ============================================================================
# 4. Shadow workflow recorder & signed incident notice
# ============================================================================


@dataclass(frozen=True)
class ShadowWorkflowExceptionRecord:
    workflow_id: str
    last_known_sop_node: str
    observed_shadow_action: str
    operator_note: str
    candidate_caid: str


class ShadowWorkflowAndIncidentEmitter:
    VALID_SEVERITY_TIERS: FrozenSet[str] = frozenset(
        {"SEV_1_CRITICAL", "SEV_2_HIGH", "SEV_3_MEDIUM"}
    )
    REQUIRED_ACTION_TAKEN = "FAIL_CLOSED_KERNEL_OR_HOOK_VETO"
    _SIGNED_FIELDS: Tuple[str, ...] = (
        "action_taken",
        "containment_latency_us",
        "evidence_bundle_caid",
        "halt_reason_code",
        "incident_id",
        "issuer_public_key_hex",
        "jurisdictions_notified",
        "severity_tier",
    )

    @staticmethod
    def record_shadow_exception(
        workflow_id: str,
        last_known_sop_node: str,
        observed_shadow_action: str,
        operator_note: str,
    ) -> ShadowWorkflowExceptionRecord:
        payload = {
            "last_known_sop_node": last_known_sop_node,
            "observed_shadow_action": observed_shadow_action,
            "operator_note": operator_note,
            "workflow_id": workflow_id,
        }
        return ShadowWorkflowExceptionRecord(
            workflow_id, last_known_sop_node, observed_shadow_action, operator_note,
            sha256_jcs_caid(payload),
        )

    @classmethod
    def _body_invariants_hold(cls, body: Dict[str, Any]) -> bool:
        latency = body.get("containment_latency_us")
        jurisdictions = body.get("jurisdictions_notified")
        halt_code = body.get("halt_reason_code")
        incident_id = body.get("incident_id")
        return (
            body.get("severity_tier") in cls.VALID_SEVERITY_TIERS
            and body.get("action_taken") == cls.REQUIRED_ACTION_TAKEN
            and _is_strict_int(latency)
            and latency >= 0
            and isinstance(halt_code, str)
            and halt_code.startswith("HALT_")
            and isinstance(incident_id, str)
            and bool(incident_id.strip())
            and isinstance(body.get("evidence_bundle_caid"), str)
            and bool(_SHA256_CAID_RE.match(body["evidence_bundle_caid"]))
            and isinstance(jurisdictions, list)
            and bool(jurisdictions)
            and all(isinstance(j, str) and j for j in jurisdictions)
            and jurisdictions == sorted(set(jurisdictions))
        )

    @classmethod
    def emit_incident_notice(
        cls,
        incident_id: str,
        severity_tier: str,
        halt_reason_code: str,
        containment_latency_us: int,
        evidence_bundle_caid: str,
        jurisdictions: Sequence[str],
        signing_key: Ed25519PrivateKey,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "action_taken": cls.REQUIRED_ACTION_TAKEN,
            "containment_latency_us": containment_latency_us,
            "evidence_bundle_caid": evidence_bundle_caid,
            "halt_reason_code": halt_reason_code,
            "incident_id": incident_id,
            "issuer_public_key_hex": signing_key.public_key().public_bytes_raw().hex(),
            "jurisdictions_notified": sorted(set(jurisdictions)),
            "severity_tier": severity_tier,
        }
        if not cls._body_invariants_hold(body):
            raise ValueError("ERR_INVALID_INCIDENT_NOTICE_FIELDS")
        notice = dict(body)
        notice["notification_caid"] = sha256_jcs_caid(body)
        notice["signature_hex"] = signing_key.sign(encode_jcs(body)).hex()
        return notice

    @classmethod
    def verify_incident_notice(
        cls, notice: Dict[str, Any], trusted_issuer_public_key_hex: str
    ) -> bool:
        """Verifies field invariants, JCS CAID, pinned issuer key and Ed25519
        signature. Unknown extra fields fail closed."""
        expected_keys = set(cls._SIGNED_FIELDS) | {"notification_caid", "signature_hex"}
        if set(notice.keys()) != expected_keys:
            return False
        body = {k: notice[k] for k in cls._SIGNED_FIELDS}
        if not cls._body_invariants_hold(body):
            return False
        if not hmac.compare_digest(
            str(body["issuer_public_key_hex"]), trusted_issuer_public_key_hex
        ):
            return False
        if not hmac.compare_digest(str(notice["notification_caid"]), sha256_jcs_caid(body)):
            return False
        try:
            Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(trusted_issuer_public_key_hex)
            ).verify(bytes.fromhex(str(notice["signature_hex"])), encode_jcs(body))
        except (InvalidSignature, ValueError):
            return False
        return True
