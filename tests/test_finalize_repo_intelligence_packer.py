#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
#
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
tests/test_finalize_repo_intelligence_packer.py
================================================================================
Verification & Falsification Suite for SOTA Repo-Intelligence & Radix KV-Cache Packer.

Grounding & Provenance:
- Mooncake (Moonshot AI / Tsinghua, ASPLOS 2025, arXiv:2407.00079)
- DeepSeek-V3 / Coder MLA (arXiv:2412.19437, arXiv:2405.04434)
- RepoGraph (Peking Univ / Alibaba, ICLR 2025, arXiv:2410.14684)
- LocAgent (Alibaba Qwen, arXiv:2503.09089)
- OpenCodeReview (Alibaba, arXiv:2608.09290)
- Passau Compaction Cliff (Univ of Passau, arXiv:2608.22752)
- Ripwire (redhat-et/ripwire) & GitNexus (abhigyanpatwari/GitNexus)

Evaluated under the declared local AST verification model.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from src.accuracy_cascade_router import (
    AccuracyCascadeRouter,
    BASE_ORACLE_CHECKS,
    CodingTask,
    LedgerEntry,
    RoutingLedger,
    T2_ORACLE_CHECKS,
)
from src.jcs_canonicalizer import encode_jcs
from tools.finalize_repo_intelligence_packer import (
    BlastRadiusReport,
    GitNexusSkillClusterGenerator,
    MemoryWorkingSet,
    OpenCodeReviewAsymmetricReflector,
    PassauTypeAwareMemoryCompactor,
    PolyglotASTExtractor,
    RadixKVCacheAligner,
    RipwireBlastRadiusAnalyzer,
    TarjanSCCTopologicalScheduler,
    estimate_lexical_tokens,
    estimate_tokens,
    execute_verified_cascade_step,
    measure_repository_compression,
    run_self_test,
)


@pytest.fixture
def sample_polyglot_repo() -> dict[str, str]:
    return {
        "src/auth_service.py": (
            "class AuthService:\n"
            "    def authenticate(self, token: str) -> bool:\n"
            "        return len(token) > 10\n"
        ),
        "src/api_gateway.py": (
            "from src.auth_service import AuthService\n\n"
            "class ApiGateway:\n"
            "    def __init__(self, auth: AuthService) -> None:\n"
            "        self.auth = auth\n\n"
            "    def handle_request(self, req: dict) -> int:\n"
            "        if self.auth.authenticate(req.get('token', '')):\n"
            "            return 200\n"
            "        return 401\n"
        ),
        "crates/core-crypto/src/lib.rs": (
            "pub struct KeyPair {\n"
            "    pub secret: [u8; 32],\n"
            "}\n\n"
            "pub fn sign_transaction(kp: &KeyPair, msg: &[u8]) -> [u8; 64] {\n"
            "    [0u8; 64]\n"
            "}\n"
        ),
        "frontend/src/client.ts": (
            "export interface UserProfile {\n"
            "    id: string;\n"
            "    name: string;\n"
            "}\n\n"
            "export function fetchProfile(id: string): UserProfile {\n"
            "    return { id, name: 'Alice' };\n"
            "}\n"
        ),
    }


def test_polyglot_ast_indexing(sample_polyglot_repo: dict[str, str]) -> None:
    """Verifies polyglot AST and regex fallback indexing across Python, Rust, and TypeScript."""
    nodes = PolyglotASTExtractor.index_files(sample_polyglot_repo)
    assert len(nodes) == 4
    assert nodes["src/auth_service.py"].language == "python"
    assert "AuthService.authenticate" in nodes["src/auth_service.py"].defined_symbols
    assert nodes["crates/core-crypto/src/lib.rs"].language == "rust"
    assert "sign_transaction" in nodes["crates/core-crypto/src/lib.rs"].defined_symbols
    assert nodes["frontend/src/client.ts"].language == "typescript"
    assert "fetchProfile" in nodes["frontend/src/client.ts"].defined_symbols


def test_reverse_blast_radius_computation(sample_polyglot_repo: dict[str, str]) -> None:
    """Verifies that reverse blast radius accurately detects callers of AuthService.authenticate."""
    nodes = PolyglotASTExtractor.index_files(sample_polyglot_repo)
    blast = RipwireBlastRadiusAnalyzer.compute_blast_radius(
        target_file="src/auth_service.py",
        target_symbol="authenticate",
        nodes=nodes,
        token_budget=1000,
    )
    assert "src/api_gateway.py" in blast.reverse_caller_files
    assert not blast.truncated_due_to_budget
    assert blast.omitted_caller_count == 0


def test_falsification_budget_overflow_latch(sample_polyglot_repo: dict[str, str]) -> None:
    """Falsification: When token budget is exceeded with fail_on_budget_overflow=True, must halt."""
    nodes = PolyglotASTExtractor.index_files(sample_polyglot_repo)
    with pytest.raises(RuntimeError, match="HALT_REVERSE_CALLER_BUDGET_OVERFLOW"):
        RipwireBlastRadiusAnalyzer.compute_blast_radius(
            target_file="src/auth_service.py",
            target_symbol="authenticate",
            nodes=nodes,
            token_budget=10,  # Deliberately tiny budget to trigger overflow
            fail_on_budget_overflow=True,
        )


def test_tarjan_scc_cycle_breaking() -> None:
    """Verifies that circular dependencies (A -> B -> A) are condensed into atomic SCC nodes."""
    circular_repo = {
        "src/module_a.py": (
            "from src.module_b import func_b\n"
            "def func_a():\n"
            "    return func_b()\n"
        ),
        "src/module_b.py": (
            "from src.module_a import func_a\n"
            "def func_b():\n"
            "    return func_a()\n"
        ),
        "src/module_c.py": (
            "from src.module_a import func_a\n"
            "def func_c():\n"
            "    return func_a()\n"
        ),
    }
    nodes = PolyglotASTExtractor.index_files(circular_repo)
    plan = TarjanSCCTopologicalScheduler.schedule_refactoring(nodes)
    assert not plan.is_dag
    assert plan.scc_cycles_found == 1
    # Modules A and B must be in the same atomic condensed stage
    scc_ab = [s for s in plan.condensed_stages if "src/module_a.py" in s]
    assert len(scc_ab) == 1
    assert "src/module_b.py" in scc_ab[0]


def test_gitnexus_community_skill_generation(sample_polyglot_repo: dict[str, str]) -> None:
    """Verifies GitNexus community clustering with <= 500 token capsule budget."""
    nodes = PolyglotASTExtractor.index_files(sample_polyglot_repo)
    skills = GitNexusSkillClusterGenerator.generate_cluster_skills(nodes, max_tokens_per_skill=500)
    for cid, skill in skills.items():
        assert skill.token_count <= 500
        assert "Negative-Space Invariant" in skill.markdown_content


def test_radix_kv_cache_prefix_alignment_and_cache_lock(sample_polyglot_repo: dict[str, str]) -> None:
    """Verifies Mooncake/SGLang 64-token block boundary alignment and prefix hash lock."""
    nodes = PolyglotASTExtractor.index_files(sample_polyglot_repo)
    skills = GitNexusSkillClusterGenerator.generate_cluster_skills(nodes)
    core_skill = list(skills.values())[0]

    aligner = RadixKVCacheAligner(block_size=64)
    c_rules = [
        "C1: Zero mocks.",
        "C2: RFC 8785 canonical JCS.",
        "C3: Timestamp ephemeral audit token: 2026-10-26T12:00:00Z.",
    ]
    p1 = aligner.build_and_verify_radix_prompt(
        constitution_c_constraints=c_rules,
        cluster_skill=core_skill,
        dynamic_task_payload={"turn": 1},
        enforce_block_alignment=True,
    )
    assert p1.block_boundary_padded
    assert p1.prefix_tokens % 64 == 0

    # Turn 2 with different volatile timestamp -> sanitizer strips it, maintaining exact prefix hash!
    c_rules_t2 = [
        "C1: Zero mocks.",
        "C2: RFC 8785 canonical JCS.",
        "C3: Timestamp ephemeral audit token: 2026-10-26T12:59:59Z.",
    ]
    p2 = aligner.build_and_verify_radix_prompt(
        constitution_c_constraints=c_rules_t2,
        cluster_skill=core_skill,
        dynamic_task_payload={"turn": 2},
        enforce_block_alignment=True,
    )
    assert p2.prefix_tokens % 64 == 0
    assert p1.frozen_prefix_sha256 == p2.frozen_prefix_sha256


def test_falsification_radix_prefix_cache_broken() -> None:
    """Falsification: Mutating an actual rule in the static prefix must raise cache broken exception."""
    nodes = PolyglotASTExtractor.index_files({"src/a.py": "def foo(): pass\n"})
    skills = GitNexusSkillClusterGenerator.generate_cluster_skills(nodes)
    skill = list(skills.values())[0]

    aligner = RadixKVCacheAligner(block_size=64)
    aligner.build_and_verify_radix_prompt(
        constitution_c_constraints=["Rule A"],
        cluster_skill=skill,
        dynamic_task_payload={"task": 1},
    )
    with pytest.raises(RuntimeError, match="HALT_RADIX_PREFIX_CACHE_BROKEN"):
        aligner.build_and_verify_radix_prompt(
            constitution_c_constraints=["Rule B (Drifted!)"],
            cluster_skill=skill,
            dynamic_task_payload={"task": 2},
        )


def test_passau_type_aware_memory_triage() -> None:
    """Verifies that [C] constraints are 100% preserved while [E] episodic logs are evicted."""
    ws = MemoryWorkingSet(
        constraints_c=("C1: Zero mocks.", "C2: JCS only."),
        procedures_p=("pytest tests/ -q",),
        beliefs_b=("Domain cluster core",),
        preferences_f=("Terse output only",),
        episodic_e=(
            "Log turn 1: ok",
            "Log turn 2: " + ("massive trace line dump " * 50),
        ),
    )
    compacted = PassauTypeAwareMemoryCompactor.compact(ws, max_allowed_tokens=60)
    assert len(compacted.constraints_c) == 2
    assert len(compacted.procedures_p) == 1
    assert len(compacted.episodic_e) <= 1


def test_falsification_passau_constraints_exceed_budget() -> None:
    """Falsification: If [C] constraints alone exceed token budget, compactor must refuse to evict."""
    ws = MemoryWorkingSet(
        constraints_c=("Massive statutory constraint rule string " * 30,),
        procedures_p=(),
        beliefs_b=(),
        preferences_f=(),
        episodic_e=(),
    )
    with pytest.raises(ValueError, match="HALT_CONSTRAINTS_EXCEED_BUDGET"):
        PassauTypeAwareMemoryCompactor.compact(ws, max_allowed_tokens=50)


def test_opencode_review_asymmetric_reflector(sample_polyglot_repo: dict[str, str]) -> None:
    """Verifies asymmetric reflector catching signature mutation with missing caller updates."""
    nodes = PolyglotASTExtractor.index_files(sample_polyglot_repo)
    blast = RipwireBlastRadiusAnalyzer.compute_blast_radius(
        target_file="src/auth_service.py",
        target_symbol="authenticate",
        nodes=nodes,
    )
    # Bad diff: altered signature without touching caller (src/api_gateway.py)
    bad_diff = (
        "--- a/src/auth_service.py\n"
        "+++ b/src/auth_service.py\n"
        "@@ -2,2 +2,2 @@\n"
        "-    def authenticate(self, token: str) -> bool:\n"
        "+    def authenticate(self, token: str, context: dict) -> bool:\n"
    )
    verdict = OpenCodeReviewAsymmetricReflector.evaluate_diff(bad_diff, blast, ("C1",))
    assert not verdict.approved
    assert "src/api_gateway.py" in str(verdict.broken_callers)

    # Good diff: touches both target and reverse caller
    good_diff = (
        "--- a/src/auth_service.py\n"
        "+++ b/src/auth_service.py\n"
        "@@ -2,2 +2,2 @@\n"
        "-    def authenticate(self, token: str) -> bool:\n"
        "+    def authenticate(self, token: str, context: dict) -> bool:\n"
        "--- a/src/api_gateway.py\n"
        "+++ b/src/api_gateway.py\n"
        "@@ -6,2 +6,2 @@\n"
        "-        if self.auth.authenticate(req.get('token', '')):\n"
        "+        if self.auth.authenticate(req.get('token', ''), {}):\n"
    )
    verdict_good = OpenCodeReviewAsymmetricReflector.evaluate_diff(good_diff, blast, ("C1",))
    assert verdict_good.approved


def test_closed_loop_verified_cascade_step_and_ed25519_receipt(
    sample_polyglot_repo: dict[str, str],
) -> None:
    """
    Verifies the unified closed loop:
    AST + Blast Radius -> Router -> Asymmetric Diff Review -> AcceptanceOracle (with UTBoost floor)
    -> EscalationPacket on failure -> Ed25519-signed RFC 8785 JCS receipt.
    """
    ledger = RoutingLedger()
    for i in range(40):
        ledger.record(LedgerEntry("auth_refactor", "cheap", True, False, 0.2, 50 + i))
        ledger.record(LedgerEntry("auth_refactor", "strong", True, False, 1.5, 120 + i))
    router = AccuracyCascadeRouter(ledger, "cheap", "strong", 0.80)
    signing_key = Ed25519PrivateKey.from_private_bytes(b"\x22" * 32)
    full_t2_evidence = {c: True for c in BASE_ORACLE_CHECKS + T2_ORACLE_CHECKS}

    # 1. Falsification: signature changed without updating caller -> rejected & escalated with slice only
    bad_diff = (
        "--- a/src/auth_service.py\n"
        "+++ b/src/auth_service.py\n"
        "@@ -2,2 +2,2 @@\n"
        "-    def authenticate(self, token: str) -> bool:\n"
        "+    def authenticate(self, token: str, context: dict) -> bool:\n"
    )
    step_bad = execute_verified_cascade_step(
        repo_files=sample_polyglot_repo,
        target_file="src/auth_service.py",
        target_symbol="authenticate",
        task=CodingTask("t-bad", "auth_refactor", "T2", False, {"cheap": 0.2, "strong": 1.5}),
        router=router,
        candidate_diff=bad_diff,
        oracle_evidence=full_t2_evidence,
        hard_rules=("C1: Update reverse callers",),
        signing_key=signing_key,
        mutation_kill_ratio_bps=9500,
        min_mutation_kill_bps=9000,
    )
    assert step_bad.route_decision.model == "cheap"
    assert not step_bad.diff_review.approved
    assert not step_bad.oracle_verdict.accepted
    assert "blast_radius_updated" in step_bad.oracle_verdict.failed_checks
    assert step_bad.escalation_packet is not None
    assert step_bad.escalation_packet["affected_symbols"] == ["src/auth_service.py::authenticate"]
    assert any("src/api_gateway.py" in c for c in step_bad.escalation_packet["reverse_callers"])
    assert "frontend/src/client.ts" not in str(step_bad.escalation_packet["reverse_callers"])

    # Verify Ed25519 signature over RFC 8785 JCS receipt
    pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(step_bad.public_key_hex))
    pub.verify(bytes.fromhex(step_bad.ed25519_signature_hex), encode_jcs(step_bad.jcs_receipt))

    # 2. Positive acceptance: caller updated + mutation floor satisfied -> accepted, no escalation
    good_diff = (
        "--- a/src/auth_service.py\n"
        "+++ b/src/auth_service.py\n"
        "@@ -2,2 +2,2 @@\n"
        "-    def authenticate(self, token: str) -> bool:\n"
        "+    def authenticate(self, token: str, context: dict) -> bool:\n"
        "--- a/src/api_gateway.py\n"
        "+++ b/src/api_gateway.py\n"
        "@@ -6,2 +6,2 @@\n"
        "-        if self.auth.authenticate(req.get('token', '')):\n"
        "+        if self.auth.authenticate(req.get('token', ''), {}):\n"
    )
    step_good = execute_verified_cascade_step(
        repo_files=sample_polyglot_repo,
        target_file="src/auth_service.py",
        target_symbol="authenticate",
        task=CodingTask("t-good", "auth_refactor", "T2", False, {"cheap": 0.2, "strong": 1.5}),
        router=router,
        candidate_diff=good_diff,
        oracle_evidence=full_t2_evidence,
        hard_rules=("C1: Update reverse callers",),
        signing_key=signing_key,
        mutation_kill_ratio_bps=9667,
        min_mutation_kill_bps=9000,
    )
    assert step_good.oracle_verdict.accepted is True
    assert step_good.escalation_packet is None
    assert step_good.jcs_receipt["oracle_accepted"] is True
    pub.verify(bytes.fromhex(step_good.ed25519_signature_hex), encode_jcs(step_good.jcs_receipt))


def test_real_repository_compression_measurement() -> None:
    """Verifies real repository compression measurement across src/*.py and lexical tokenizer."""
    assert estimate_lexical_tokens("") == 0
    assert estimate_lexical_tokens("def foo(x: int) -> int: return x + 1") >= 10
    metrics = measure_repository_compression(Path("."), max_files=10)
    assert metrics["files_measured"] == 10
    assert metrics["full_repo_bytes"] > metrics["ast_skeleton_bytes"] > 0
    assert metrics["full_repo_char4_tokens"] > metrics["ast_skeleton_char4_tokens"] > 0
    assert metrics["full_repo_lexical_tokens"] > metrics["ast_skeleton_lexical_tokens"] > 0
    assert 0 < metrics["skeleton_char4_reduction_bps"] < 10000
    assert 0 < metrics["skeleton_lexical_reduction_bps"] < 10000


def test_cli_self_test() -> None:
    """Verifies standalone self-test function executes cleanly."""
    run_self_test()


def test_banned_words_audit() -> None:
    """Enforces AGENTS.md epistemic boundary purity across owned files."""
    banned_tokens = [
        "guaran" + "tee",
        "proven" + " universally",
        "bullet" + "proof",
        "enterprise" + "-grade",
        "production" + "-safe",
        "100%" + " secure",
    ]
    files_to_check = [
        Path("tools/finalize_repo_intelligence_packer.py"),
    ]
    violations: list[str] = []
    for fp in files_to_check:
        content = fp.read_text(encoding="utf-8")
        for idx, line in enumerate(content.splitlines(), 1):
            for token in banned_tokens:
                if re.search(r"\b" + re.escape(token) + r"\b", line, re.IGNORECASE):
                    violations.append(f"{fp}:{idx}: {line.strip()}")
    assert not violations, f"Banned words detected: {violations}"
