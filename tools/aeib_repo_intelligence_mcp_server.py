#!/usr/bin/env python3
"""
tools/aeib_repo_intelligence_mcp_server.py — JSON-RPC 2.0 Stdio MCP Server for Antigravity.

Exposes AEIB repository intelligence, reverse blast-radius analysis, log compression,
asymmetric diff review, sovereign oracle verification, slice-only escalation packets,
and organizational behavioral assurance to Antigravity Chat via Model Context Protocol (MCP).

Tools exposed:
1. `repo_map`             — AST skeletons, Merkle roots, and Tarjan SCC topological order
2. `repo_slice`           — Task-scoped target + forward-import + reverse-caller slice pack
3. `blast_radius`         — Reverse callers with audited omission latch (`fail_on_budget_overflow`)
4. `compress_test_output` — Extracts failing assertions + SHA-256 digest within token budget
5. `verify_diff`          — Asymmetric diff reflector + AcceptanceOracle + Ed25519 JCS receipt
6. `escalation_pack`      — Bounded repair packet (B <= 3) containing only the failed slice
7. `behavioral_check`     — Evaluates proposal via BehavioralAssuranceGate & DerivativeNoOpGate

Epistemic notice: prototype, evaluated under the stated model. No outbound network calls.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.accuracy_cascade_router import (  # noqa: E402
    AcceptanceOracle,
    BPS_SCALE,
    OracleVerdict,
    build_escalation_packet,
)
from src.behavioral_assurance_gate import (  # noqa: E402
    ActionProposal,
    BehavioralAssuranceGate,
    DerivativeNoOpGate,
    OrganizationalPolicy,
    TrajectoryStep,
)
from src.jcs_canonicalizer import encode_jcs  # noqa: E402
from tools.finalize_repo_intelligence_packer import (  # noqa: E402
    OpenCodeReviewAsymmetricReflector,
    PolyglotASTExtractor,
    RipwireBlastRadiusAnalyzer,
    TarjanSCCTopologicalScheduler,
    estimate_lexical_tokens,
    estimate_tokens,
    sha256_exact,
)

JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2025-03-26"

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "name": "repo_map",
        "description": "Return compact AST/interface map and Tarjan SCC topological order for repository files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "files": {"type": "object"},
                "max_tokens": {"type": "integer", "default": 4000},
            },
            "required": ["files"],
        },
    },
    {
        "name": "repo_slice",
        "description": "Return minimal import closure, reverse caller signatures, and target skeleton within token_budget.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "files": {"type": "object"},
                "target_file": {"type": "string"},
                "target_symbol": {"type": "string"},
                "token_budget": {"type": "integer", "default": 1500},
            },
            "required": ["files", "target_file", "target_symbol"],
        },
    },
    {
        "name": "blast_radius",
        "description": "Return reverse callers and affected public API surface with optional budget-overflow halt.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "files": {"type": "object"},
                "target_file": {"type": "string"},
                "target_symbol": {"type": "string"},
                "token_budget": {"type": "integer", "default": 1000},
                "fail_on_budget_overflow": {"type": "boolean", "default": True},
            },
            "required": ["files", "target_file", "target_symbol"],
        },
    },
    {
        "name": "compress_test_output",
        "description": "Compress failing test output while preserving failure assertions and full-log sha256 digest.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "log": {"type": "string"},
                "budget_tokens": {"type": "integer", "default": 400},
            },
            "required": ["log"],
        },
    },
    {
        "name": "verify_diff",
        "description": "Check unified diff against asymmetric reflector, AcceptanceOracle, and UTBoost mutation floor.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "files": {"type": "object"},
                "target_file": {"type": "string"},
                "target_symbol": {"type": "string"},
                "diff": {"type": "string"},
                "risk_tier": {"type": "string", "default": "T1"},
                "evidence": {"type": "object"},
                "produced_by": {"type": "string", "default": "cheap"},
                "reviewed_by": {"type": "string", "default": "independent_reflector"},
                "mutation_kill_ratio_bps": {"type": "integer"},
                "min_mutation_kill_bps": {"type": "integer", "default": 0},
                "hard_rules": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["files", "target_file", "target_symbol", "diff", "evidence"],
        },
    },
    {
        "name": "escalation_pack",
        "description": "Build minimal failed-slice repair packet (B <= 3) for stronger model adjudication.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "object"},
                "contract": {"type": "object"},
                "failed_candidate_diff": {"type": "string"},
                "failed_checks": {"type": "array", "items": {"type": "string"}},
                "missing_checks": {"type": "array", "items": {"type": "string"}},
                "failing_output": {"type": "string"},
                "affected_symbols": {"type": "array", "items": {"type": "string"}},
                "reverse_callers": {"type": "array", "items": {"type": "string"}},
                "constraints": {"type": "array", "items": {"type": "string"}},
                "attempt": {"type": "integer", "default": 1},
            },
            "required": ["task", "contract", "failed_candidate_diff", "failing_output"],
        },
    },
    {
        "name": "behavioral_check",
        "description": "Evaluate action proposal and trajectory against BehavioralAssuranceGate and DerivativeNoOpGate.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action_id": {"type": "string"},
                "subject_agent_id": {"type": "string"},
                "tool_id": {"type": "string"},
                "capability_id": {"type": "string"},
                "amount_minor": {"type": "integer"},
                "unattended_steps": {"type": "integer"},
                "nlah_harness_digest": {"type": "string"},
                "initial_state_digest": {"type": "string"},
                "trajectory_digests": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "action_id",
                "subject_agent_id",
                "tool_id",
                "capability_id",
                "amount_minor",
                "unattended_steps",
                "nlah_harness_digest",
            ],
        },
    },
]


class AEIBRepoIntelligenceMCPServer:
    """Deterministic JSON-RPC 2.0 MCP Server for AEIB Repository Intelligence."""

    def __init__(self, signing_key: Optional[Ed25519PrivateKey] = None) -> None:
        self._signing_key = signing_key or Ed25519PrivateKey.generate()
        self._public_key_hex = (
            self._signing_key.public_key()
            .public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
            .hex()
        )

    def tool_repo_map(self, args: Mapping[str, Any]) -> Dict[str, Any]:
        files: Dict[str, str] = dict(args["files"])
        max_tokens = int(args.get("max_tokens", 4000))
        nodes = PolyglotASTExtractor.index_files(files)
        plan = TarjanSCCTopologicalScheduler.schedule_refactoring(nodes)
        modules = []
        used_tokens = 0
        truncated = False
        for rel_path in plan.execution_order:
            node = nodes[rel_path]
            if used_tokens + node.token_cost > max_tokens:
                truncated = True
                break
            used_tokens += node.token_cost
            modules.append(
                {
                    "path": rel_path,
                    "language": node.language,
                    "defined_symbols": list(node.defined_symbols),
                    "local_imports": list(node.local_imports),
                    "chunk_merkle_root": node.chunk_merkle_root,
                    "token_cost": node.token_cost,
                    "skeleton": node.skeleton_source,
                }
            )
        return {
            "is_dag": plan.is_dag,
            "scc_cycles_found": plan.scc_cycles_found,
            "execution_order": list(plan.execution_order),
            "modules": modules,
            "total_token_cost": used_tokens,
            "truncated": truncated,
        }

    def tool_blast_radius(self, args: Mapping[str, Any]) -> Dict[str, Any]:
        files: Dict[str, str] = dict(args["files"])
        target_file = str(args["target_file"])
        target_symbol = str(args["target_symbol"])
        token_budget = int(args.get("token_budget", 1000))
        fail_on_overflow = bool(args.get("fail_on_budget_overflow", True))
        nodes = PolyglotASTExtractor.index_files(files)
        rep = RipwireBlastRadiusAnalyzer.compute_blast_radius(
            target_file=target_file,
            target_symbol=target_symbol,
            nodes=nodes,
            token_budget=token_budget,
            fail_on_budget_overflow=fail_on_overflow,
        )
        return {
            "target_file": rep.target_file,
            "target_symbol": rep.target_symbol,
            "forward_import_files": list(rep.forward_import_files),
            "reverse_caller_files": list(rep.reverse_caller_files),
            "reverse_caller_signatures": list(rep.reverse_caller_signatures),
            "blast_radius_token_cost": rep.blast_radius_token_cost,
            "truncated_due_to_budget": rep.truncated_due_to_budget,
            "omitted_caller_count": rep.omitted_caller_count,
        }

    def tool_repo_slice(self, args: Mapping[str, Any]) -> Dict[str, Any]:
        files: Dict[str, str] = dict(args["files"])
        target_file = str(args["target_file"])
        target_symbol = str(args["target_symbol"])
        token_budget = int(args.get("token_budget", 1500))
        nodes = PolyglotASTExtractor.index_files(files)
        blast = RipwireBlastRadiusAnalyzer.compute_blast_radius(
            target_file=target_file,
            target_symbol=target_symbol,
            nodes=nodes,
            token_budget=token_budget,
            fail_on_budget_overflow=False,
        )
        target_node = nodes[target_file]
        full_tokens = sum(estimate_tokens(c) for c in files.values())
        slice_tokens = target_node.token_cost + blast.blast_radius_token_cost
        return {
            "target_file": target_file,
            "target_symbol": target_symbol,
            "target_skeleton": target_node.skeleton_source,
            "target_merkle_root": target_node.chunk_merkle_root,
            "forward_imports": list(blast.forward_import_files),
            "reverse_caller_files": list(blast.reverse_caller_files),
            "reverse_caller_signatures": list(blast.reverse_caller_signatures),
            "slice_char4_tokens": slice_tokens,
            "full_repo_char4_tokens": full_tokens,
            "slice_lexical_tokens": estimate_lexical_tokens(target_node.skeleton_source),
            "recovery_manifest_sha256": sha256_exact(target_node.raw_source.encode("utf-8")),
        }

    def tool_compress_test_output(self, args: Mapping[str, Any]) -> Dict[str, Any]:
        raw_log = str(args["log"])
        budget_tokens = int(args.get("budget_tokens", 400))
        if budget_tokens < 10:
            raise ValueError("ERR_INVALID_LOG_BUDGET")
        full_digest = sha256_exact(raw_log.encode("utf-8"))
        lines = raw_log.splitlines()
        failing_assertions = [
            ln.strip()
            for ln in lines
            if ln.lstrip().startswith(("E   ", "FAILED ", "AssertionError", "RuntimeError", "ValueError"))
        ]
        max_chars = budget_tokens * 4
        if len(raw_log) <= max_chars:
            summary = raw_log
            truncated = False
        else:
            half = max_chars // 2
            summary = raw_log[:half] + "\n...[compressed]...\n" + raw_log[-half:]
            truncated = True
        return {
            "full_log_sha256": full_digest,
            "failing_assertions": failing_assertions[:20],
            "summary": summary,
            "truncated": truncated,
            "raw_char4_tokens": estimate_tokens(raw_log),
            "compressed_char4_tokens": estimate_tokens(summary),
        }

    def tool_verify_diff(self, args: Mapping[str, Any]) -> Dict[str, Any]:
        files: Dict[str, str] = dict(args["files"])
        target_file = str(args["target_file"])
        target_symbol = str(args["target_symbol"])
        diff_text = str(args["diff"])
        risk_tier = str(args.get("risk_tier", "T1"))
        raw_evidence: Dict[str, bool] = dict(args["evidence"])
        produced_by = str(args.get("produced_by", "cheap"))
        reviewed_by = str(args.get("reviewed_by", "independent_reflector"))
        mut_kill_bps: Optional[int] = args.get("mutation_kill_ratio_bps")
        min_mut_bps = int(args.get("min_mutation_kill_bps", 0))
        hard_rules: Sequence[str] = tuple(args.get("hard_rules", ("C1: Preserve callers",)))

        nodes = PolyglotASTExtractor.index_files(files)
        blast = RipwireBlastRadiusAnalyzer.compute_blast_radius(
            target_file=target_file,
            target_symbol=target_symbol,
            nodes=nodes,
        )
        diff_review = OpenCodeReviewAsymmetricReflector.evaluate_diff(
            unified_diff=diff_text,
            blast_radius=blast,
            hard_rules=hard_rules,
        )

        merged_evidence = dict(raw_evidence)
        merged_evidence["no_stub_signals"] = (
            merged_evidence.get("no_stub_signals", True) and len(diff_review.unregistered_mutations) == 0
        )
        if risk_tier in ("T2", "T3"):
            merged_evidence["independent_diff_only_review"] = (
                merged_evidence.get("independent_diff_only_review", True) and diff_review.approved
            )
            merged_evidence["blast_radius_updated"] = (
                merged_evidence.get("blast_radius_updated", True) and len(diff_review.broken_callers) == 0
            )

        verdict = AcceptanceOracle.evaluate(
            risk_tier=risk_tier,
            evidence=merged_evidence,
            produced_by=produced_by,
            reviewed_by=reviewed_by,
            mutation_kill_ratio_bps=mut_kill_bps,
            min_mutation_kill_bps=min_mut_bps,
        )

        jcs_receipt: Dict[str, object] = {
            "schema": "aeib.mcp_diff_verification_receipt.v1",
            "target_file": target_file,
            "target_symbol": target_symbol,
            "risk_tier": risk_tier,
            "diff_sha256": sha256_exact(diff_text.encode("utf-8")),
            "asymmetric_diff_approved": diff_review.approved,
            "broken_callers": list(diff_review.broken_callers),
            "oracle_accepted": verdict.accepted,
            "oracle_reason": verdict.reason,
            "missing_checks": list(verdict.missing_checks),
            "failed_checks": list(verdict.failed_checks),
            "mutation_kill_ratio_bps": mut_kill_bps if mut_kill_bps is not None else -1,
            "min_mutation_kill_bps": min_mut_bps,
        }
        canonical_bytes = encode_jcs(jcs_receipt)
        sig_hex = self._signing_key.sign(canonical_bytes).hex()
        return {
            "accepted": verdict.accepted,
            "oracle_reason": verdict.reason,
            "asymmetric_review": diff_review.verdict_message,
            "broken_callers": list(diff_review.broken_callers),
            "unregistered_mutations": list(diff_review.unregistered_mutations),
            "missing_checks": list(verdict.missing_checks),
            "failed_checks": list(verdict.failed_checks),
            "jcs_receipt": jcs_receipt,
            "receipt_digest": sha256_exact(canonical_bytes),
            "ed25519_signature_hex": sig_hex,
            "public_key_hex": self._public_key_hex,
        }

    def tool_escalation_pack(self, args: Mapping[str, Any]) -> Dict[str, Any]:
        failed_checks = tuple(args.get("failed_checks", ("contract_tests_pass",)))
        missing_checks = tuple(args.get("missing_checks", ()))
        verdict = OracleVerdict(
            accepted=False,
            reason="REJECT_FAILED_CHECKS",
            missing_checks=missing_checks,
            failed_checks=failed_checks,
        )
        return build_escalation_packet(
            task=dict(args["task"]),
            contract=dict(args["contract"]),
            failed_candidate_diff=str(args["failed_candidate_diff"]),
            verdict=verdict,
            failing_output=str(args["failing_output"]),
            affected_symbols=list(args.get("affected_symbols", ())),
            reverse_callers=list(args.get("reverse_callers", ())),
            constraints=list(args.get("constraints", ())),
            attempt=int(args.get("attempt", 1)),
        )

    def tool_behavioral_check(self, args: Mapping[str, Any]) -> Dict[str, Any]:
        policy = OrganizationalPolicy(
            policy_id=str(args.get("policy_id", "org-default-v1")),
            nlah_harness_digest=str(args.get("expected_nlah_digest", args["nlah_harness_digest"])),
            allowed_capabilities=tuple(
                args.get("allowed_capabilities", ("read_repo", "run_tests", "propose_diff", "wire_transfer"))
            ),
            high_stakes_capabilities=tuple(args.get("high_stakes_capabilities", ("wire_transfer",))),
            max_single_action_minor=int(args.get("max_single_action_minor", 100000)),
            max_epoch_cumulative_minor=int(args.get("max_epoch_cumulative_minor", 250000)),
            max_unattended_steps=int(args.get("max_unattended_steps", 5)),
        )
        gate = BehavioralAssuranceGate(policy, self._signing_key.public_key())
        proposal = ActionProposal(
            action_id=str(args["action_id"]),
            subject_agent_id=str(args["subject_agent_id"]),
            tool_id=str(args["tool_id"]),
            capability_id=str(args["capability_id"]),
            amount_minor=int(args["amount_minor"]),
            unattended_steps=int(args["unattended_steps"]),
            nlah_harness_digest=str(args["nlah_harness_digest"]),
            warrant_signature_hex=str(args.get("warrant_signature_hex", "")),
        )
        b_verdict = gate.evaluate(proposal)

        init_digest = str(args.get("initial_state_digest", "sha256:init"))
        traj_digests = list(args.get("trajectory_digests", [init_digest]))
        steps = [
            TrajectoryStep(idx, proposal.tool_id, d, compensable=True)
            for idx, d in enumerate(traj_digests)
        ]
        d_verdict = DerivativeNoOpGate(max_allowed_noop_variation=0).evaluate_trajectory(
            init_digest, steps
        )
        return {
            "behavioral_allowed": b_verdict.allowed,
            "behavioral_reason": b_verdict.reason,
            "canonical_act_digest": b_verdict.canonical_act_digest,
            "noop_valid": d_verdict.is_valid_noop,
            "noop_reason": d_verdict.reason,
            "trajectory_total_variation": d_verdict.total_variation,
        }

    def handle_jsonrpc(self, request: Mapping[str, Any]) -> Dict[str, Any]:
        req_id = request.get("id")
        if request.get("jsonrpc") != JSONRPC_VERSION or "method" not in request:
            return {
                "jsonrpc": JSONRPC_VERSION,
                "id": req_id,
                "error": {"code": -32600, "message": "ERR_INVALID_JSONRPC_REQUEST"},
            }
        method = str(request["method"])
        params = request.get("params") or {}

        if method == "initialize":
            return {
                "jsonrpc": JSONRPC_VERSION,
                "id": req_id,
                "result": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "serverInfo": {"name": "aeib-repo-intelligence", "version": "1.0.0"},
                    "capabilities": {"tools": {"listChanged": False}},
                },
            }

        if method == "tools/list":
            return {
                "jsonrpc": JSONRPC_VERSION,
                "id": req_id,
                "result": {"tools": TOOL_SCHEMAS},
            }

        if method == "tools/call":
            tool_name = str(params.get("name", ""))
            tool_args = params.get("arguments") or {}
            dispatch = {
                "repo_map": self.tool_repo_map,
                "repo_slice": self.tool_repo_slice,
                "blast_radius": self.tool_blast_radius,
                "compress_test_output": self.tool_compress_test_output,
                "verify_diff": self.tool_verify_diff,
                "escalation_pack": self.tool_escalation_pack,
                "behavioral_check": self.tool_behavioral_check,
            }
            if tool_name not in dispatch:
                return {
                    "jsonrpc": JSONRPC_VERSION,
                    "id": req_id,
                    "error": {"code": -32601, "message": f"ERR_UNKNOWN_MCP_TOOL:{tool_name}"},
                }
            try:
                payload = dispatch[tool_name](tool_args)
                return {
                    "jsonrpc": JSONRPC_VERSION,
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(payload, sort_keys=True)}],
                        "structuredContent": payload,
                        "isError": False,
                    },
                }
            except Exception as exc:
                return {
                    "jsonrpc": JSONRPC_VERSION,
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": str(exc)}],
                        "isError": True,
                    },
                }

        return {
            "jsonrpc": JSONRPC_VERSION,
            "id": req_id,
            "error": {"code": -32601, "message": f"ERR_METHOD_NOT_FOUND:{method}"},
        }


def main() -> None:
    server = AEIBRepoIntelligenceMCPServer()
    for line in sys.stdin:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            req = json.loads(stripped)
        except json.JSONDecodeError:
            resp = {
                "jsonrpc": JSONRPC_VERSION,
                "id": None,
                "error": {"code": -32700, "message": "ERR_PARSE_ERROR"},
            }
        else:
            resp = server.handle_jsonrpc(req)
        sys.stdout.write(json.dumps(resp, sort_keys=True) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
