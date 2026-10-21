"""
tools/vibe_coding_and_long_horizon_guard.py
================================================================================
2026 Architectural Convergence & Runtime Defense Module:
1. VibeCodingSecurityGate: Mitigates Vibe-Coding access control deficits (64% missing
   backend auth or database Row-Level Security RLS). Enforces deterministic AST route
   inspection and SQL RLS enforcement (fail-closed even if model ignores its own warnings).
2. GitAiDeterministicBisectResolver: Reproduces gitai-style deterministic batch
   verification and O(log2 N) automatic bisect fault isolation, reducing multi-agent
   concurrency merge retries toward 1.0 attempts per change.
3. IapsAgentHoneypotGuard: Implements IAPS autonomous agent honeypot triad
   (Detection -> Incrimination -> Quarantine Deterrence).

Epistemic Calibration:
  Observed, tested, and evaluated under the declared simulation model.
  Zero mock assertions; real AST visitors, real SHA-256 digests.
"""
from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# ============================================================================
# 1. VIBE CODING SECURITY GATE: ROUTE AUTHENTICATION & SQL RLS ENFORCEMENT
# ============================================================================

@dataclass(frozen=True)
class VibeAuditReport:
    passed: bool
    unauthenticated_routes: List[str]
    tables_missing_rls: List[str]
    rejection_code: str


class VibeCodingSecurityGate:
    """
    Evaluates backend Python route ASTs and SQL schema definitions:
    - Verifies exposed endpoints carry explicit authentication decorators or are
      explicitly registered in signed_public_routes.
    - Verifies table creations in SQL migrations are accompanied by ENABLE ROW LEVEL SECURITY.
    """
    ROUTE_DECORATORS = frozenset({"get", "post", "put", "delete", "patch", "route"})
    AUTH_DECORATORS = frozenset({"require_auth", "login_required", "verify_capability"})

    @classmethod
    def audit_backend_and_sql(
        cls,
        python_source: str,
        sql_migration: str,
        signed_public_routes: Set[str],
    ) -> VibeAuditReport:
        tree = ast.parse(python_source)
        unauth_routes: List[str] = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                is_route = False
                has_auth = False
                for dec in node.decorator_list:
                    dec_name = cls._extract_decorator_name(dec)
                    if dec_name in cls.ROUTE_DECORATORS:
                        is_route = True
                    if dec_name in cls.AUTH_DECORATORS:
                        has_auth = True

                if is_route and not has_auth and node.name not in signed_public_routes:
                    unauth_routes.append(node.name)

        # Parse SQL table creations and RLS activation statements
        created_tables: Set[str] = set()
        rls_enabled_tables: Set[str] = set()

        for raw_line in sql_migration.splitlines():
            line = " ".join(raw_line.strip().upper().split())
            if line.startswith("CREATE TABLE "):
                parts = line.replace("IF NOT EXISTS ", "").split()
                if len(parts) >= 3:
                    tbl = parts[2].strip("();").strip('"')
                    created_tables.add(tbl)
            elif "ENABLE ROW LEVEL SECURITY" in line and line.startswith("ALTER TABLE "):
                parts = line.split()
                if len(parts) >= 3:
                    tbl = parts[2].strip("();").strip('"')
                    rls_enabled_tables.add(tbl)

        missing_rls = sorted(created_tables - rls_enabled_tables)

        if unauth_routes or missing_rls:
            return VibeAuditReport(
                passed=False,
                unauthenticated_routes=sorted(unauth_routes),
                tables_missing_rls=missing_rls,
                rejection_code="HALT_VIBE_CODING_ACCESS_CONTROL_OR_RLS_MISSING",
            )

        return VibeAuditReport(
            passed=True,
            unauthenticated_routes=[],
            tables_missing_rls=[],
            rejection_code="OK",
        )

    @staticmethod
    def _extract_decorator_name(dec: ast.expr) -> str:
        if isinstance(dec, ast.Name):
            return dec.id
        if isinstance(dec, ast.Attribute):
            return dec.attr
        if isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Name):
                return dec.func.id
            if isinstance(dec.func, ast.Attribute):
                return dec.func.attr
        return ""


# ============================================================================
# 2. GITAI DETERMINISTIC BATCH MERGE & AUTOMATIC BISECT RESOLVER (O(log2 N))
# ============================================================================

@dataclass(frozen=True)
class AgentPatch:
    patch_id: str
    agent_id: str
    touched_symbols: Set[str]
    passes_verification: bool  # Evaluates whether this patch preserves test invariants


class GitAiDeterministicBisectResolver:
    """
    Implements deterministic batching and automatic bisection for concurrent agent patches:
    1. Disjoint Write-Set Filtering: Identifies symbol collisions before running tests.
    2. Automatic Bisect Verification: Bisection isolates breaking patches in O(log2 N)
       verifications, allowing clean candidate patches to commit in a single batch.
    """

    @classmethod
    def resolve_and_merge_batch(
        cls,
        patches: List[AgentPatch],
        batch_verifier_fn: Callable[[List[AgentPatch]], bool],
    ) -> Dict[str, Any]:
        # Step 1: Disjoint symbol set filtering
        orthogonal_batch: List[AgentPatch] = []
        conflicted_patch_ids: List[str] = []
        claimed_symbols: Set[str] = set()

        for p in patches:
            if p.touched_symbols & claimed_symbols:
                conflicted_patch_ids.append(p.patch_id)
            else:
                claimed_symbols.update(p.touched_symbols)
                orthogonal_batch.append(p)

        verify_runs = [0]

        def _verify(subset: List[AgentPatch]) -> bool:
            verify_runs[0] += 1
            return batch_verifier_fn(subset)

        # Step 2: Automatic bisection of clean subset
        accepted, reverted = cls._bisect_clean_subset(orthogonal_batch, _verify)

        return {
            "total_submitted": len(patches),
            "merged_patch_ids": [p.patch_id for p in accepted],
            "reverted_breaking_patch_ids": [p.patch_id for p in reverted],
            "conflicted_patch_ids": conflicted_patch_ids,
            "verification_invocations": verify_runs[0],
        }

    @classmethod
    def _bisect_clean_subset(
        cls,
        subset: List[AgentPatch],
        verify_fn: Callable[[List[AgentPatch]], bool],
    ) -> Tuple[List[AgentPatch], List[AgentPatch]]:
        if not subset:
            return [], []
        if verify_fn(subset):
            return subset, []
        if len(subset) == 1:
            return [], subset

        mid = len(subset) // 2
        left_clean, left_bad = cls._bisect_clean_subset(subset[:mid], verify_fn)
        right_clean, right_bad = cls._bisect_clean_subset(subset[mid:], verify_fn)
        return left_clean + right_clean, left_bad + right_bad


# ============================================================================
# 3. IAPS AGENT HONEYPOT GUARD (DETECTION -> INCRIMINATION -> DETERRENCE)
# ============================================================================

@dataclass
class HoneypotForensicRecord:
    agent_id: str
    root_sponsor_id: str
    decoy_target: str
    taint_tier: str
    incrimination_hash: str
    action_taken: str


class IapsAgentHoneypotGuard:
    """
    Deploys decoy resources and canary credentials in agent working environments:
    - Any touch to a canary resource generates a cryptographic incrimination receipt
      and triggers immediate sponsor tree quarantine.
    """
    DECOY_RESOURCES = frozenset(
        {
            "file://.env.production.canary",
            "tool://admin.override_rls_policy",
            "tool://treasury.export_master_seed",
        }
    )

    def __init__(self) -> None:
        self.quarantined_sponsors: Set[str] = set()
        self.forensic_log: List[HoneypotForensicRecord] = []

    def inspect_request(
        self,
        agent_id: str,
        root_sponsor_id: str,
        target_resource: str,
        taint_tier: str,
        payload_bytes: bytes,
    ) -> Dict[str, str]:
        if root_sponsor_id in self.quarantined_sponsors:
            return {
                "disposition": "NOT_DISPATCHED",
                "code": "HALT_SPONSOR_QUARANTINED_BY_HONEYPOT",
            }

        if target_resource in self.DECOY_RESOURCES:
            # 1. Detection & 2. Incrimination
            evidence_material = (
                f"{agent_id}|{root_sponsor_id}|{target_resource}|{taint_tier}|".encode("utf-8")
                + payload_bytes
            )
            incrim_hash = f"sha256:{hashlib.sha256(evidence_material).hexdigest()}"

            # 3. Quarantine Deterrence
            self.quarantined_sponsors.add(root_sponsor_id)
            self.forensic_log.append(
                HoneypotForensicRecord(
                    agent_id=agent_id,
                    root_sponsor_id=root_sponsor_id,
                    decoy_target=target_resource,
                    taint_tier=taint_tier,
                    incrimination_hash=incrim_hash,
                    action_taken="QUARANTINE_ROOT_SPONSOR_AND_HALT",
                )
            )
            return {
                "disposition": "NOT_DISPATCHED",
                "code": "HALT_HONEYPOT_TRIPWIRE_ENGAGED",
                "incrimination_hash": incrim_hash,
            }

        return {"disposition": "AUTHORIZED", "code": "OK"}


def test_vibe_coding_gitai_bisect_and_iaps_honeypot() -> None:
    # 1. Vibe Coding Audit Gate Test
    vibe_python_code = """
@app.get("/health")
def health_check():
    return {"ok": True}

@app.post("/v1/new_transfer")
@require_auth
def new_transfer():
    return {"status": "ok"}

@app.post("/v1/legacy_admin_payout")
def legacy_admin_payout():
    return {"status": "leaked"}
"""
    vibe_sql = """
CREATE TABLE customer_wallets (id TEXT PRIMARY KEY, balance INT);
CREATE TABLE audit_logs (id TEXT PRIMARY KEY);
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
"""
    audit_res = VibeCodingSecurityGate.audit_backend_and_sql(
        vibe_python_code,
        vibe_sql,
        signed_public_routes={"health_check"},
    )
    assert audit_res.passed is False
    assert audit_res.unauthenticated_routes == ["legacy_admin_payout"]
    assert audit_res.tables_missing_rls == ["CUSTOMER_WALLETS"]
    assert audit_res.rejection_code == "HALT_VIBE_CODING_ACCESS_CONTROL_OR_RLS_MISSING"

    # 2. GitAi Deterministic Bisect Resolver Test
    patches = [
        AgentPatch(
            patch_id=f"p-{i}",
            agent_id=f"agent-{i}",
            touched_symbols={f"sym_{i}"},
            passes_verification=(i != 5),
        )
        for i in range(1, 9)
    ]
    merge_res = GitAiDeterministicBisectResolver.resolve_and_merge_batch(
        patches,
        lambda subset: all(p.passes_verification for p in subset),
    )
    assert merge_res["reverted_breaking_patch_ids"] == ["p-5"]
    assert len(merge_res["merged_patch_ids"]) == 7
    assert merge_res["verification_invocations"] <= 7

    # 3. IAPS Agent Honeypot Test
    honeypot = IapsAgentHoneypotGuard()
    trap_res = honeypot.inspect_request(
        agent_id="subagent-rogue-07",
        root_sponsor_id="sponsor-alpha",
        target_resource="file://.env.production.canary",
        taint_tier="TIER_2_UNTRUSTED_EXTERNAL",
        payload_bytes=b"cat .env.production.canary",
    )
    assert trap_res["disposition"] == "NOT_DISPATCHED"
    assert trap_res["code"] == "HALT_HONEYPOT_TRIPWIRE_ENGAGED"
    assert len(honeypot.forensic_log) == 1

    subsequent_res = honeypot.inspect_request(
        agent_id="subagent-worker-02",
        root_sponsor_id="sponsor-alpha",
        target_resource="tool://normal.read_docs",
        taint_tier="TIER_1_INTERNAL_DB",
        payload_bytes=b"{}",
    )
    assert subsequent_res["disposition"] == "NOT_DISPATCHED"
    assert subsequent_res["code"] == "HALT_SPONSOR_QUARANTINED_BY_HONEYPOT"


if __name__ == "__main__":
    test_vibe_coding_gitai_bisect_and_iaps_honeypot()
    print("VIBE CODING AST/RLS GATE, GITAI BISECT RESOLVER, AND IAPS HONEYPOT VERIFIED.")
