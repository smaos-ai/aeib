#!/usr/bin/env python3
"""
tests/test_substrate_cube_and_blast_radius.py — Zero-Mock Falsification & Adequacy Suite

Falsifies and evaluates:
1. `src/hypergraph_blast_radius.py` (Kiro 1,000 PRs/wk Blast Radius, Anti-Scope-Creep & Anti-Smurfing)
2. `src/substrate_cube_interlock.py` (Agent Substrate + Cube Sandbox Egress & Auto-Pause)
"""

from __future__ import annotations

import pytest

from src.hypergraph_blast_radius import (
    AutonomousPRVerdict,
    BlastRadiusReport,
    DependencyGraph,
    HypergraphBlastRadiusGovernor,
    PRDiffSpec,
    PRScopeProposal,
    ScopeEvaluationReport,
    sha256_jcs_caid,
)
from src.substrate_cube_interlock import (
    ActorSnapshotDescriptor,
    EgressInterlockReceipt,
    SubstrateCubeInterlock,
)


def _sample_repo_graph() -> dict[str, str]:
    """
    5-module repository dependency chain:
    `src/core_auth.py` <- `src/session.py` <- `src/api_router.py` <- `src/cli_app.py`
    `src/leaf_formatter.py` (isolated leaf node, imported by nothing)
    """
    return {
        "src/core_auth.py": "def verify_token(t: str) -> bool:\n    return len(t) > 0\n",
        "src/session.py": "import src.core_auth\ndef open_session(t: str) -> bool:\n    return src.core_auth.verify_token(t)\n",
        "src/api_router.py": "from src import session\ndef route(t: str) -> bool:\n    return session.open_session(t)\n",
        "src/cli_app.py": "import src.api_router\ndef main() -> bool:\n    return src.api_router.route('ok')\n",
        "src/leaf_formatter.py": "def format_banner(msg: str) -> str:\n    return msg.strip()\n",
    }


def test_1_kiro_blast_radius_routing_and_anti_scope_creep() -> None:
    gov = HypergraphBlastRadiusGovernor(
        repo_sources=_sample_repo_graph(),
        max_auto_merge_radius_bps=3000,  # 30.00% threshold
        max_lines_changed=50,
        max_files_touched=3,
    )

    # Case A: Leaf node change (`src/leaf_formatter.py`, 0 dependents -> 0 bps) -> AUTO_MERGE
    v_leaf = gov.evaluate_pr(
        PRDiffSpec(
            pr_id="pr_1001_leaf",
            intent_caid="sha256:1111111111111111111111111111111111111111111111111111111111111111",
            changed_files=("src/leaf_formatter.py",),
            lines_added=8,
            lines_deleted=2,
        )
    )
    assert v_leaf.action == "AUTO_MERGE"
    assert v_leaf.blast_radius_bps == 0
    assert v_leaf.affected_modules == ()
    assert v_leaf.verdict_caid.startswith("sha256:")

    # Case B: Over-eager agent turns a 10-line fix into a 90-line subsystem -> HALT_SCOPE_CREEP
    v_creep = gov.evaluate_pr(
        PRDiffSpec(
            pr_id="pr_1002_over_eager",
            intent_caid="sha256:2222222222222222222222222222222222222222222222222222222222222222",
            changed_files=("src/leaf_formatter.py",),
            lines_added=75,
            lines_deleted=15,
        )
    )
    assert v_creep.action == "HALT_SCOPE_CREEP"
    assert "HALT_OVER_EAGER_AGENT" in v_creep.reason_code

    # Case C: Small 4-line edit to `src/core_auth.py` (transitively impacts 3 of 5 modules = 6000 bps) -> HUMAN_ESCALATE
    v_core = gov.evaluate_pr(
        PRDiffSpec(
            pr_id="pr_1003_core_auth",
            intent_caid="sha256:3333333333333333333333333333333333333333333333333333333333333333",
            changed_files=("src/core_auth.py",),
            lines_added=3,
            lines_deleted=1,
        )
    )
    assert v_core.action == "HUMAN_ESCALATE"
    assert v_core.blast_radius_bps == 6000  # 3 / 5 = 60.00% = 6000 bps
    assert v_core.affected_modules == (
        "src/api_router.py",
        "src/cli_app.py",
        "src/session.py",
    )

    # Case D: Invariant violation trips AUTO_REJECT_INVARIANT
    v_invar = gov.evaluate_pr(
        PRDiffSpec(
            pr_id="pr_1004_violation",
            intent_caid="sha256:4444444444444444444444444444444444444444444444444444444444444444",
            changed_files=("src/leaf_formatter.py",),
            lines_added=5,
            lines_deleted=1,
            constraint_violations=("FORBIDDEN_COLOR_LITERAL_#FF0000",),
        )
    )
    assert v_invar.action == "AUTO_REJECT_INVARIANT"
    assert "FORBIDDEN_COLOR_LITERAL" in v_invar.reason_code


def test_2_substrate_spiffe_cube_vault_and_autopause_indeterminate_latch() -> None:
    interlock = SubstrateCubeInterlock(
        trusted_spiffe_prefix="spiffe://sovereign.nexus/ns/prod/",
        allowed_egress_hosts=frozenset({"api.stripe.com", "mcp.internal.nexus"}),
        credential_vault={"STRIPE_SECRET_KEY": "sk_live_999888777_real_secret"},
    )
    actor_id = "spiffe://sovereign.nexus/ns/prod/actor/worker_01"

    # 2A: Reject untrusted SPIFFE prefix
    r_untrusted = interlock.intercept_outbound_egress(
        actor_spiffe_id="spiffe://rogue.actor/ns/prod/worker_01",
        target_host="api.stripe.com",
        http_method="POST",
        business_effect_payload={"amount": 100},
        header_templates={},
    )
    assert r_untrusted.allowed is False
    assert r_untrusted.effect_state == "HALT_UNTRUSTED_SPIFFE_ID"

    # 2B: Reject forbidden host
    r_bad_host = interlock.intercept_outbound_egress(
        actor_spiffe_id=actor_id,
        target_host="exfiltrate.evil.io",
        http_method="POST",
        business_effect_payload={"amount": 100},
        header_templates={},
    )
    assert r_bad_host.allowed is False
    assert "HALT_EGRESS_HOST_DENIED" in r_bad_host.effect_state

    # 2C: Reject raw secret leaked inside agent payload (Cube Credential Blindness)
    r_leak = interlock.intercept_outbound_egress(
        actor_spiffe_id=actor_id,
        target_host="api.stripe.com",
        http_method="POST",
        business_effect_payload={"amount_minor": 5000, "leaked": "sk_live_999888777_real_secret"},
        header_templates={},
    )
    assert r_leak.allowed is False
    assert "HALT_RAW_SECRET_IN_SANDBOX_CONTEXT" in r_leak.effect_state

    # 2D: Valid egress with `{{VAULT:STRIPE_SECRET_KEY}}` placeholder latches cleanly
    payload = {"amount_minor": 5000, "currency": "USD", "order_id": "ord_77"}
    r_ok = interlock.intercept_outbound_egress(
        actor_spiffe_id=actor_id,
        target_host="api.stripe.com",
        http_method="POST",
        business_effect_payload=payload,
        header_templates={"Authorization": "Bearer {{VAULT:STRIPE_SECRET_KEY}}"},
    )
    assert r_ok.allowed is True
    assert r_ok.effect_state == "LATCHED_DISPATCHED"
    assert r_ok.resolved_headers_redacted["Authorization"] == "VAULT_INJECTED:STRIPE_SECRET_KEY"

    # 2E: Actor enters Cube/Substrate AutoPause BEFORE HTTP ACK arrives!
    snap = interlock.auto_pause_actor(
        actor_spiffe_id=actor_id,
        sandbox_backend="cube_kvm",
        memory_zstd_bytes=b"ZSTD_COMPRESSED_VM_MEMORY_IMAGE_01",
        pre_suspend_taint_clean=True,
    )
    assert interlock.get_effect_state(r_ok.effect_key_caid) == "EFFECT_INDETERMINATE"

    # 2F: Verify tampered Zstd snapshot is rejected on AutoResume
    tampered_snap = ActorSnapshotDescriptor(
        actor_spiffe_id=snap.actor_spiffe_id,
        sandbox_backend=snap.sandbox_backend,
        memory_zstd_bytes=b"TAMPERED_MEMORY_BYTES",
        pre_suspend_taint_clean=True,
        pending_effect_keys=snap.pending_effect_keys,
        snapshot_caid=snap.snapshot_caid,
    )
    resumed_bad, reason_bad = interlock.auto_resume_actor(tampered_snap)
    assert resumed_bad is False
    assert reason_bad == "HALT_SNAPSHOT_HASH_TAMPER_DETECTED"

    # 2G: Valid snapshot resumes, but blind retry of the indeterminate mutation is BLOCKED
    resumed_ok, _ = interlock.auto_resume_actor(snap)
    assert resumed_ok is True
    r_retry = interlock.intercept_outbound_egress(
        actor_spiffe_id=actor_id,
        target_host="api.stripe.com",
        http_method="POST",
        business_effect_payload=payload,
        header_templates={"Authorization": "Bearer {{VAULT:STRIPE_SECRET_KEY}}"},
    )
    assert r_retry.allowed is False
    assert r_retry.effect_state == "HALT_INDETERMINATE_REQUIRES_RECONCILIATION"

    # 2H: HOLD-and-Reconcile probe confirms provider already executed the charge -> marks COMMITTED
    rec_status = interlock.reconcile_indeterminate_effect(
        r_ok.effect_key_caid, provider_confirmed_executed=True
    )
    assert rec_status == "RECONCILED_ALREADY_COMMITTED"
    assert interlock.get_effect_state(r_ok.effect_key_caid) == "COMMITTED"

    # Duplicate call after commit is permanently blocked
    r_dup = interlock.intercept_outbound_egress(
        actor_spiffe_id=actor_id,
        target_host="api.stripe.com",
        http_method="POST",
        business_effect_payload=payload,
        header_templates={"Authorization": "Bearer {{VAULT:STRIPE_SECRET_KEY}}"},
    )
    assert r_dup.allowed is False
    assert r_dup.effect_state == "HALT_DUPLICATE_COMMITTED_EFFECT_BLOCKED"


def test_3_governor_scope_proposals_and_protected_paths() -> None:
    gov = HypergraphBlastRadiusGovernor(
        repo_sources=_sample_repo_graph(),
        max_blast_radius_bps=4500,
        max_pr_lines=100,
        max_epoch_cumulative_lines=120,
    )

    # 3A: Protected path violation (touching compliance/ or config/agentgateway)
    prop_protected = PRScopeProposal(
        pr_id="pr_prot_01",
        author_agent_id="agent_alpha",
        epoch_id="epoch_01",
        declared_intent="Modify compliance rule",
        modified_files=["compliance/check_zone_boundary.py"],
        added_lines=10,
        deleted_lines=5,
    )
    rep_prot = gov._evaluate_pr_scope_proposal(prop_protected)
    assert rep_prot.verdict == "HALT_PROTECTED_PATH"
    assert rep_prot.blast_radius_bps == 10000

    # 3B: Single PR line cap exceeded
    prop_large = PRScopeProposal(
        pr_id="pr_large_01",
        author_agent_id="agent_alpha",
        epoch_id="epoch_01",
        declared_intent="Refactor leaf formatter",
        modified_files=["src/leaf_formatter.py"],
        added_lines=90,
        deleted_lines=20,  # 110 > 100
    )
    rep_large = gov._evaluate_pr_scope_proposal(prop_large)
    assert rep_large.verdict == "HALT_SCOPE_VIOLATION"

    # 3C: Legitimate proposal passes
    prop_ok = PRScopeProposal(
        pr_id="pr_ok_01",
        author_agent_id="agent_alpha",
        epoch_id="epoch_01",
        declared_intent="Fix banner whitespace",
        modified_files=["src/leaf_formatter.py"],
        added_lines=30,
        deleted_lines=10,  # 40 lines
    )
    rep_ok = gov._evaluate_pr_scope_proposal(prop_ok)
    assert rep_ok.verdict == "PASS"
    assert rep_ok.cumulative_epoch_lines == 40
    assert rep_ok.caid != ""

    # 3D: Split-PR Smurfing: next proposal exceeds remaining cumulative epoch budget (120) while within single-PR limit (100)
    prop_smurf = PRScopeProposal(
        pr_id="pr_smurf_02",
        author_agent_id="agent_alpha",
        epoch_id="epoch_01",
        declared_intent="Add more formatting helpers",
        modified_files=["src/leaf_formatter.py"],
        added_lines=50,
        deleted_lines=40,  # 90 lines <= 100 max_pr_lines; 40 + 90 = 130 > 120 max_epoch
    )
    rep_smurf = gov._evaluate_pr_scope_proposal(prop_smurf)
    assert rep_smurf.verdict == "HALT_SMURFING_EXCEEDED"

    # 3E: Proposal canonical dict serialization
    d = rep_ok.to_canonical_dict()
    assert d["verdict"] == "PASS"
    assert d["cumulative_epoch_lines"] == 40


def test_4_parameter_validation_and_edge_cases() -> None:
    # Governor parameter bounds
    with pytest.raises(ValueError, match="ERR_EMPTY_REPO_SOURCES"):
        HypergraphBlastRadiusGovernor(repo_sources={})

    with pytest.raises(ValueError, match="ERR_INVALID_RADIUS_BPS"):
        HypergraphBlastRadiusGovernor(repo_sources=_sample_repo_graph(), max_auto_merge_radius_bps=10001)

    with pytest.raises(ValueError, match="ERR_INVALID_MAX_LINES"):
        HypergraphBlastRadiusGovernor(repo_sources=_sample_repo_graph(), max_lines_changed=0)

    with pytest.raises(ValueError, match="ERR_INVALID_MAX_FILES"):
        HypergraphBlastRadiusGovernor(repo_sources=_sample_repo_graph(), max_files_touched=0)

    # PRDiffSpec validations
    with pytest.raises(ValueError, match="ERR_EMPTY_PR_ID"):
        PRDiffSpec("", "sha256:123", ("a.py",), 1, 1)

    with pytest.raises(ValueError, match="ERR_INVALID_INTENT_CAID"):
        PRDiffSpec("pr_1", "bad_caid", ("a.py",), 1, 1)

    with pytest.raises(ValueError, match="ERR_NEGATIVE_LINE_COUNTS"):
        PRDiffSpec("pr_1", "sha256:123", ("a.py",), -1, 1)

    # PRScopeProposal validations
    with pytest.raises(ValueError, match="ERR_EMPTY_PR_ID"):
        PRScopeProposal("", "author", "ep", "intent", ["a.py"], 1, 1).validate()

    with pytest.raises(ValueError, match="ERR_EMPTY_AUTHOR_AGENT_ID"):
        PRScopeProposal("pr_1", "", "ep", "intent", ["a.py"], 1, 1).validate()

    with pytest.raises(ValueError, match="ERR_EMPTY_EPOCH_ID"):
        PRScopeProposal("pr_1", "author", "", "intent", ["a.py"], 1, 1).validate()

    with pytest.raises(ValueError, match="ERR_EMPTY_DECLARED_INTENT"):
        PRScopeProposal("pr_1", "author", "ep", "", ["a.py"], 1, 1).validate()

    with pytest.raises(ValueError, match="ERR_NEGATIVE_LINE_COUNT"):
        PRScopeProposal("pr_1", "author", "ep", "intent", ["a.py"], -1, 1).validate()

    with pytest.raises(ValueError, match="ERR_EMPTY_MODIFIED_FILES"):
        PRScopeProposal("pr_1", "author", "ep", "intent", [], 1, 1).validate()

    # Substrate validations
    with pytest.raises(ValueError, match="ERR_INVALID_SPIFFE_TRUST_DOMAIN"):
        SubstrateCubeInterlock("bad_prefix", frozenset(), {})

    interlock = SubstrateCubeInterlock(
        "spiffe://sovereign.nexus/", frozenset({"api.com"}), {}
    )

    with pytest.raises(ValueError, match="ERR_UNSUPPORTED_SANDBOX_BACKEND"):
        interlock.auto_pause_actor("spiffe://sovereign.nexus/1", "unsupported_backend", b"", True)

    with pytest.raises(KeyError, match="ERR_UNKNOWN_EFFECT_KEY"):
        interlock.acknowledge_egress_completion("spiffe://sovereign.nexus/1", "sha256:ghost", True)

    with pytest.raises(ValueError, match="ERR_EFFECT_NOT_INDETERMINATE"):
        interlock.reconcile_indeterminate_effect("sha256:ghost", True)

    # sha256_jcs_caid bytes and str paths
    caid_bytes = sha256_jcs_caid(b"hello")
    caid_str = sha256_jcs_caid("hello")
    assert caid_bytes == caid_str


def test_5_spiffe_spire_authority_and_blind_credential_vault() -> None:
    from src.substrate_cube_interlock import (
        BlindCredentialVault,
        SpiffeSpireAuthority,
        SpiffeSvid,
    )

    auth = SpiffeSpireAuthority("sovereign.nexus")
    assert "BEGIN PUBLIC KEY" in auth.get_ca_public_pem()

    # Issue and verify valid SVID
    svid = auth.issue_svid("worker_01", validity_seconds=3600)
    valid, reason = auth.verify_svid(svid)
    assert valid is True
    assert reason == "SVID_SIGNATURE_VALID"

    # Expired SVID
    expired_svid = auth.issue_svid("worker_01", validity_seconds=-10)
    exp_valid, exp_reason = auth.verify_svid(expired_svid)
    assert exp_valid is False
    assert exp_reason == "ERR_SVID_EXPIRED"

    # Tampered signature
    tampered_svid = SpiffeSvid(
        spiffe_id=svid.spiffe_id,
        issued_at_epoch_s=svid.issued_at_epoch_s,
        expires_at_epoch_s=svid.expires_at_epoch_s,
        public_key_pem=svid.public_key_pem,
        signature_b64=svid.signature_b64[:-4] + "AAAA",
    )
    tamp_valid, tamp_reason = auth.verify_svid(tampered_svid)
    assert tamp_valid is False
    assert tamp_reason == "ERR_INVALID_SVID_SIGNATURE"

    # Malformed spiffe_id
    bad_uri_svid = SpiffeSvid(
        spiffe_id="invalid://uri",
        issued_at_epoch_s=svid.issued_at_epoch_s,
        expires_at_epoch_s=svid.expires_at_epoch_s,
        public_key_pem=svid.public_key_pem,
        signature_b64=svid.signature_b64,
    )
    bad_valid, bad_reason = auth.verify_svid(bad_uri_svid)
    assert bad_valid is False
    assert bad_reason == "ERR_INVALID_SPIFFE_URI_FORMAT"

    # Blind Credential Vault
    vault = BlindCredentialVault()
    vault.register_secret("STRIPE_KEY", "sk_live_secret_123", ["spiffe://sovereign.nexus/agent/worker_01"])

    # Successful injection
    res, injected = vault.inject_credentials(
        "spiffe://sovereign.nexus/agent/worker_01",
        '{"headers": {"Authorization": "Bearer {{VAULT:STRIPE_KEY}}"}}',
    )
    assert injected == ["STRIPE_KEY"]
    assert "sk_live_secret_123" in res

    # Access denied
    with pytest.raises(PermissionError, match="ERR_VAULT_ACCESS_DENIED"):
        vault.inject_credentials(
            "spiffe://sovereign.nexus/agent/unauthorized_agent",
            '{"headers": {"Authorization": "Bearer {{VAULT:STRIPE_KEY}}"}}',
        )

    # Unknown key
    with pytest.raises(KeyError, match="ERR_VAULT_KEY_NOT_FOUND"):
        vault.inject_credentials(
            "spiffe://sovereign.nexus/agent/worker_01",
            '{"headers": {"Authorization": "Bearer {{VAULT:UNKNOWN_KEY}}"}}',
        )


def test_6_substrate_cube_interlock_manager_lifecycle() -> None:
    from src.substrate_cube_interlock import SubstrateCubeInterlockManager

    mgr = SubstrateCubeInterlockManager(":memory:")
    actor_id = "actor_finance_01"
    spiffe_id = "spiffe://sovereign.nexus/agent/actor_finance_01"

    mgr.register_actor(actor_id, spiffe_id)

    # Submit mutating request (IN_FLIGHT)
    status_post = mgr.submit_request(
        request_id="req_001",
        actor_id=actor_id,
        method="POST",
        endpoint="/v1/transfers",
        payload='{"amount": 1000}',
        idempotency_token="idem_001",
    )
    assert status_post == "REQUEST_DISPATCHED_IN_FLIGHT"

    # Trigger AutoPause: KVM memory frozen
    pause_receipt = mgr.trigger_autopause(actor_id, memory_bytes=b"VM_MEM_SNAPSHOT_BYTES")
    assert pause_receipt["event"] == "AUTO_PAUSE_COMPLETED"
    assert "req_001" in pause_receipt["frozen_indeterminate_requests"]

    # Trigger AutoResume: state becomes RESUMED_PROBE_REQUIRED
    resume_receipt = mgr.trigger_autoresume(actor_id)
    assert resume_receipt["new_state"] == "RESUMED_PROBE_REQUIRED"
    assert resume_receipt["pending_indeterminate_count"] == 1

    # Blind retry while probe required is strictly rejected
    with pytest.raises(RuntimeError, match="ERR_HALT_BLIND_RETRY_FORBIDDEN"):
        mgr.submit_request(
            request_id="req_002",
            actor_id=actor_id,
            method="POST",
            endpoint="/v1/transfers",
            payload='{"amount": 1000}',
            idempotency_token="idem_001",
        )

    # Authoritative probe resolves indeterminacy to COMMITTED
    probe_receipt = mgr.resolve_indeterminate_probe(
        actor_id=actor_id,
        request_id="req_001",
        probe_outcome="SUCCESS_CONFIRMED",
    )
    assert probe_receipt["resolved_status"] == "COMMITTED"

    # Now actor is ACTOR_ACTIVE again and can submit new requests
    status_next = mgr.submit_request(
        request_id="req_003",
        actor_id=actor_id,
        method="GET",
        endpoint="/v1/balances",
        payload="{}",
        idempotency_token="idem_002",
    )
    assert status_next == "REQUEST_DISPATCHED_IN_FLIGHT"
    mgr.close()


def test_7_hypergraph_coverage_and_oracle_hardening(tmp_path: Path) -> None:
    from src.hypergraph_blast_radius import (
        DependencyGraph,
        HypergraphBlastRadiusGovernor,
        PRDiffSpec,
        PRScopeProposal,
        extract_ast_imports,
        sha256_jcs_caid,
    )

    # 7A: Deterministic CAID generation for dict, bytes, and str
    caid1 = sha256_jcs_caid({"temperature": 0})
    caid2 = sha256_jcs_caid({"temperature": 0})
    assert caid1 == caid2
    assert caid1.startswith("sha256:")
    caid_bytes = sha256_jcs_caid(b"hello bytes")
    caid_str = sha256_jcs_caid("hello string")
    assert caid_bytes.startswith("sha256:")
    assert caid_str.startswith("sha256:")

    # 7B: Default governor parameters
    gov_def = HypergraphBlastRadiusGovernor(repo_sources={"root.py": ""})
    assert gov_def.max_blast_radius_bps == 4500
    assert gov_def.max_pr_lines == 300
    assert gov_def.max_epoch_cumulative_lines == 1200
    assert gov_def.max_auto_merge_radius_bps == 3000

    # 7C: Exact line addition and deletion arithmetic check
    repo = {
        "src/a.py": "import src.b\n",
        "src/b.py": "def b(): pass\n",
    }
    gov = HypergraphBlastRadiusGovernor(repo_sources=repo)
    pr = PRDiffSpec(
        pr_id="pr_arith_1",
        intent_caid="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        changed_files=("src/b.py",),
        lines_added=15,
        lines_deleted=10,
    )
    verdict = gov.evaluate_pr(pr)
    assert verdict.total_lines_changed == 25
    assert verdict.blast_radius_bps == 5000
    assert verdict.action == "HUMAN_ESCALATE"

    # 7D: Cyclic dependency in graph and compute_reverse_dependents_bfs
    graph = DependencyGraph()
    graph.add_dependency("modA", "modB")
    graph.add_dependency("modB", "modA")
    deps = graph.compute_reverse_dependents_bfs({"modA"}, max_depth=5)
    assert "modB" in deps

    # 7E: AST import extractor on real files
    p1 = tmp_path / "mod_x.py"
    p1.write_text("import json\nfrom math import sqrt\ndef calc(): return sqrt(4)\n", encoding="utf-8")
    imps = extract_ast_imports(p1)
    assert "json" in imps
    assert "math" in imps
    assert extract_ast_imports(tmp_path / "non_existent.py") == set()

    # 7F: calculate_blast_radius with empty changed files
    blast_empty = gov_def.calculate_blast_radius(())
    assert blast_empty.blast_radius_bps == 0
    assert blast_empty.changed_files == ()

    # 7G: PRScopeProposal validation error paths
    with pytest.raises(ValueError, match="ERR_EMPTY_PR_ID"):
        PRScopeProposal("", "author", "epoch", "intent", ["file.py"], 1, 1).validate()
    with pytest.raises(ValueError, match="ERR_EMPTY_AUTHOR_AGENT_ID"):
        PRScopeProposal("pr1", "", "epoch", "intent", ["file.py"], 1, 1).validate()
    with pytest.raises(ValueError, match="ERR_EMPTY_EPOCH_ID"):
        PRScopeProposal("pr1", "author", "", "intent", ["file.py"], 1, 1).validate()
    with pytest.raises(ValueError, match="ERR_EMPTY_DECLARED_INTENT"):
        PRScopeProposal("pr1", "author", "epoch", "", ["file.py"], 1, 1).validate()
    with pytest.raises(ValueError, match="ERR_NEGATIVE_LINE_COUNT"):
        PRScopeProposal("pr1", "author", "epoch", "intent", ["file.py"], -1, 1).validate()
    with pytest.raises(ValueError, match="ERR_NEGATIVE_LINE_COUNT"):
        PRScopeProposal("pr1", "author", "epoch", "intent", ["file.py"], 1, -1).validate()
    with pytest.raises(ValueError, match="ERR_EMPTY_MODIFIED_FILES"):
        PRScopeProposal("pr1", "author", "epoch", "intent", [], 1, 1).validate()

    # 7H: Polymorphic evaluate_pr with PRScopeProposal and unsupported type
    prop = PRScopeProposal("pr_poly_1", "author", "epoch_poly", "intent", ["src/a.py"], 5, 2)
    rep_poly = gov.evaluate_pr(prop)
    assert rep_poly.verdict == "PASS"

    with pytest.raises(TypeError, match="ERR_UNSUPPORTED_PR_SPEC_TYPE"):
        gov.evaluate_pr(12345)  # type: ignore

    # 7I: build_graph_from_directory
    cnt_empty = gov_def.build_graph_from_directory(tmp_path / "does_not_exist")
    assert cnt_empty == 0
    cnt_real = gov_def.build_graph_from_directory(tmp_path)
    assert cnt_real == 1

    # 7J: reset_epoch_accumulator
    gov.reset_epoch_accumulator()
    assert len(gov._epoch_line_accumulator) == 0

def test_8_substrate_cube_coverage_hardening() -> None:
    from src.substrate_cube_interlock import (
        BlindCredentialVault,
        SubstrateCubeInterlock,
        SubstrateCubeInterlockManager,
    )

    # 8A: Missing secret key raises KeyError in BlindCredentialVault
    vault = BlindCredentialVault()
    with pytest.raises(KeyError, match="ERR_VAULT_KEY_NOT_FOUND"):
        vault.inject_credentials("spiffe://sovereign.nexus/agent/bot", "token: {{VAULT:MISSING_KEY}}")

    with pytest.raises(ValueError, match="ERR_INVALID_SECRET_DATA"):
        vault.register_secret("", "val", ["*"])

    # 8B: Unknown effect key state in SubstrateCubeInterlock
    interlock = SubstrateCubeInterlock(
        trusted_spiffe_prefix="spiffe://sovereign.nexus/ns/prod/",
        allowed_egress_hosts=frozenset({"api.test.com"}),
        credential_vault={"TEST_KEY": "secret_val"},
    )
    assert interlock.get_effect_state("sha256:unknown_effect_never_registered") == "UNSEEN"

    # Missing vault secret in egress templates
    r_missing = interlock.intercept_outbound_egress(
        actor_spiffe_id="spiffe://sovereign.nexus/ns/prod/actor/test",
        target_host="api.test.com",
        http_method="POST",
        business_effect_payload={"act": "test"},
        header_templates={"Auth": "Bearer {{VAULT:UNREGISTERED_KEY}}"},
    )
    assert r_missing.allowed is False
    assert r_missing.effect_state == "HALT_UNKNOWN_VAULT_PLACEHOLDER:UNREGISTERED_KEY"

    # 8C: Pre-suspend taint flag preservation
    snap_tainted = interlock.auto_pause_actor(
        actor_spiffe_id="spiffe://sovereign.nexus/ns/prod/actor/test",
        sandbox_backend="cube_kvm",
        memory_zstd_bytes=b"MEM_BYTES_TAINTED",
        pre_suspend_taint_clean=False,
    )
    assert snap_tainted.pre_suspend_taint_clean is False

    # 8D: Multiple indeterminate requests: verify state only returns to ACTOR_ACTIVE when 0 remain
    mgr = SubstrateCubeInterlockManager(":memory:")
    actor_id = "act_multi_test"
    mgr.register_actor(actor_id, "spiffe://sovereign.nexus/agent/act_multi_test")

    # Submit 2 POST requests and 1 GET request
    mgr.submit_request("r1", actor_id, "POST", "/p1", "{}", "idem1")
    mgr.submit_request("r2", actor_id, "POST", "/p2", "{}", "idem2")
    mgr.submit_request("r3_get", actor_id, "GET", "/g1", "{}", "idem3")

    pause_rep = mgr.trigger_autopause(actor_id, b"SNAP_MEM")
    assert sorted(pause_rep["frozen_indeterminate_requests"]) == ["r1", "r2"]

    # Resume: state is RESUMED_PROBE_REQUIRED
    res_rep = mgr.trigger_autoresume(actor_id)
    assert res_rep["new_state"] == "RESUMED_PROBE_REQUIRED"
    assert res_rep["pending_indeterminate_count"] == 2

    # Resolve only r1: state remains RESUMED_PROBE_REQUIRED
    mgr.resolve_indeterminate_probe(actor_id, "r1", "SUCCESS_CONFIRMED")
    cursor = mgr.conn.cursor()
    cursor.execute("SELECT state FROM actor_state WHERE actor_id = ?", (actor_id,))
    assert cursor.fetchone()["state"] == "RESUMED_PROBE_REQUIRED"

    # Resolve r2: now all 0 indeterminate remain, state transitions to ACTOR_ACTIVE
    mgr.resolve_indeterminate_probe(actor_id, "r2", "FAILURE_CONFIRMED")
    cursor.execute("SELECT state FROM actor_state WHERE actor_id = ?", (actor_id,))
    assert cursor.fetchone()["state"] == "ACTOR_ACTIVE"
    mgr.close()

    # 8E: acknowledge_egress_completion transport failure and success
    interlock._effect_ledger["sha256:some_failed_key"] = "IN_FLIGHT"
    eff_res = interlock.acknowledge_egress_completion(
        actor_spiffe_id="spiffe://sovereign.nexus/ns/prod/actor/test",
        effect_key_caid="sha256:some_failed_key",
        transport_succeeded=False,
    )
    assert eff_res == "EFFECT_INDETERMINATE"
    assert interlock.get_effect_state("sha256:some_failed_key") == "EFFECT_INDETERMINATE"

    interlock._effect_ledger["sha256:some_success_key"] = "IN_FLIGHT"
    eff_succ = interlock.acknowledge_egress_completion(
        actor_spiffe_id="spiffe://sovereign.nexus/ns/prod/actor/test",
        effect_key_caid="sha256:some_success_key",
        transport_succeeded=True,
    )
    assert eff_succ == "COMMITTED"
    assert interlock.get_effect_state("sha256:some_success_key") == "COMMITTED"

    # 8F: submit_request with unregistered actor raises ValueError, and suspended actor raises RuntimeError
    mgr_fresh = SubstrateCubeInterlockManager(":memory:")
    with pytest.raises(ValueError, match="ERR_ACTOR_NOT_FOUND"):
        mgr_fresh.submit_request("r_fail", "unregistered_actor_id", "POST", "/url", "{}", "idem_f")

    mgr_fresh.register_actor("act_susp_test", "spiffe://sovereign.nexus/agent/act_susp_test")
    mgr_fresh.trigger_autopause("act_susp_test", b"SNAP")
    with pytest.raises(RuntimeError, match="ERR_ACTOR_SUSPENDED"):
        mgr_fresh.submit_request("r_susp", "act_susp_test", "POST", "/url", "{}", "idem_s")
    mgr_fresh.close()


def test_9_mutation_killer_suite(tmp_path: Path) -> None:
    from dataclasses import FrozenInstanceError
    from src.hypergraph_blast_radius import (
        AutonomousPRVerdict,
        BlastRadiusReport,
        DependencyGraph,
        HypergraphBlastRadiusGovernor,
        PRDiffSpec,
        PRScopeProposal,
        extract_ast_imports,
    )

    # 1. Test FrozenInstanceError on dataclasses
    verdict = AutonomousPRVerdict(
        pr_id="p1", action="AUTO_MERGE", reason_code="OK", blast_radius_bps=0,
        affected_modules=(), total_lines_changed=10, files_touched_count=1, verdict_caid="sha256:00"
    )
    with pytest.raises(FrozenInstanceError):
        verdict.action = "HALT"  # type: ignore

    proposal = PRScopeProposal(
        pr_id="p1", author_agent_id="ag1", epoch_id="ep1", declared_intent="fix",
        modified_files=["a.py"], added_lines=10, deleted_lines=0
    )
    with pytest.raises(FrozenInstanceError):
        proposal.added_lines = 20  # type: ignore

    report = BlastRadiusReport(changed_files=("a.py",), transitive_dependents=(), total_repo_modules=1, blast_radius_bps=0)
    with pytest.raises(FrozenInstanceError):
        report.blast_radius_bps = 100  # type: ignore

    diff = PRDiffSpec(pr_id="p1", intent_caid="sha256:00", changed_files=("a.py",), lines_added=5, lines_deleted=2)
    with pytest.raises(FrozenInstanceError):
        diff.lines_added = 10  # type: ignore

    from src.hypergraph_blast_radius import ScopeEvaluationReport
    scope_rep = ScopeEvaluationReport(
        pr_id="p1", author_agent_id="ag1", epoch_id="ep1", verdict="PASS",
        blast_radius_bps=0, total_lines_changed=5, cumulative_epoch_lines=5,
        affected_dependents_count=0, affected_dependents=[], reasons=["OK"], caid="sha256:00"
    )
    with pytest.raises(FrozenInstanceError):
        scope_rep.verdict = "FAIL"  # type: ignore

    # 2. Test negative line boundaries in PRDiffSpec and PRScopeProposal
    with pytest.raises(ValueError, match="ERR_NEGATIVE_LINE_COUNTS"):
        PRDiffSpec(pr_id="p1", intent_caid="sha256:00", changed_files=("a.py",), lines_added=-1, lines_deleted=0)
    with pytest.raises(ValueError, match="ERR_NEGATIVE_LINE_COUNTS"):
        PRDiffSpec(pr_id="p1", intent_caid="sha256:00", changed_files=("a.py",), lines_added=0, lines_deleted=-1)
    # Zero lines is valid
    p_zero = PRDiffSpec(pr_id="p1", intent_caid="sha256:00", changed_files=("a.py",), lines_added=0, lines_deleted=0)
    assert p_zero.lines_added == 0 and p_zero.lines_deleted == 0

    with pytest.raises(ValueError, match="ERR_NEGATIVE_LINE_COUNT"):
        PRScopeProposal("p1", "ag1", "ep1", "intent", ["a.py"], -1, 0).validate()
    with pytest.raises(ValueError, match="ERR_NEGATIVE_LINE_COUNT"):
        PRScopeProposal("p1", "ag1", "ep1", "intent", ["a.py"], 0, -1).validate()
    p_prop_zero = PRScopeProposal("p1", "ag1", "ep1", "intent", ["a.py"], 0, 0)
    p_prop_zero.validate()
    assert p_prop_zero.added_lines == 0 and p_prop_zero.deleted_lines == 0

    # 3. Test negative parameter limits in Governor
    with pytest.raises(ValueError, match="ERR_INVALID_MAX_LINES"):
        HypergraphBlastRadiusGovernor(max_lines_changed=-1)
    with pytest.raises(ValueError, match="ERR_INVALID_MAX_FILES"):
        HypergraphBlastRadiusGovernor(max_files_touched=-1)

    # 4. Scope-creep independent branches (lines vs files) to kill BOOL_SWAP
    repo_multi = {
        "f1.py": "", "f2.py": "", "f3.py": "", "f4.py": "", "f5.py": ""
    }
    gov_multi = HypergraphBlastRadiusGovernor(repo_sources=repo_multi, max_lines_changed=50, max_files_touched=3)
    # 4A: Lines <= 50, but files > 3 (4 files touched) -> HALT_SCOPE_CREEP
    pr_files_creep = PRDiffSpec(
        pr_id="p_files", intent_caid="sha256:00",
        changed_files=("f1.py", "f2.py", "f3.py", "f4.py"),
        lines_added=4, lines_deleted=0,
    )
    v_files = gov_multi.evaluate_pr(pr_files_creep)
    assert v_files.action == "HALT_SCOPE_CREEP"
    assert v_files.files_touched_count == 4

    # 4B: Files <= 3 (1 file), but lines > 50 (55 lines) -> HALT_SCOPE_CREEP
    pr_lines_creep = PRDiffSpec(
        pr_id="p_lines", intent_caid="sha256:00",
        changed_files=("f1.py",),
        lines_added=55, lines_deleted=0,
    )
    v_lines = gov_multi.evaluate_pr(pr_lines_creep)
    assert v_lines.action == "HALT_SCOPE_CREEP"
    assert v_lines.total_lines_changed == 55

    # 4C: Test single-module repo blast radius is 0
    gov_single = HypergraphBlastRadiusGovernor(repo_sources={"only.py": ""})
    rep_single = gov_single.calculate_blast_radius(("only.py",))
    assert rep_single.blast_radius_bps == 0
    assert rep_single.total_repo_modules == 1

    # 4D: Test that changed_files are excluded from transitive_dependents
    repo_cycle = {
        "a.py": "import b\n",
        "b.py": "import a\n",
    }
    gov_cycle = HypergraphBlastRadiusGovernor(repo_sources=repo_cycle)
    rep_both = gov_cycle.calculate_blast_radius(("a.py", "b.py"))
    assert rep_both.transitive_dependents == ()
    assert rep_both.blast_radius_bps == 0

    # 4E: Test 3-part dotted submodule resolution
    repo_dotted = {
        "pkg/core.py": "def f(): pass\n",
        "user.py": "import pkg.core.sub\n",
    }
    gov_dotted = HypergraphBlastRadiusGovernor(repo_sources=repo_dotted)
    res_dotted = gov_dotted._resolve_import("pkg.core.sub")
    assert res_dotted == "pkg/core.py"

    # 4F: Test exact basis points calculation and zero-bps on scope halt
    prop_halt = PRScopeProposal("p_h", "ag1", "ep1", "intent", ["f1.py"], 350, 50)
    rep_halt = gov_multi.evaluate_pr(prop_halt)
    assert rep_halt.verdict == "HALT_SCOPE_VIOLATION"
    assert rep_halt.blast_radius_bps == 0

    prop_pass_scaled = PRScopeProposal("p_sc", "ag1", "ep1", "intent", ["f1.py"], 10, 0)
    rep_pass_scaled = gov_multi.evaluate_pr(prop_pass_scaled)
    assert rep_pass_scaled.verdict == "PASS"

    # 4. Test build_graph_from_directory on a real file with non-syntax and submodules
    p_bad = tmp_path / "syntax_error.py"
    p_bad.write_text("def def def invalid syntax [[[", encoding="utf-8")
    assert extract_ast_imports(p_bad) == set()

    p_sub = tmp_path / "subpkg" / "nested.py"
    p_sub.parent.mkdir(parents=True, exist_ok=True)
    p_sub.write_text("from pkg.submod import helper\nimport math\n", encoding="utf-8")
    imps = extract_ast_imports(p_sub)
    assert "pkg" in imps
    assert "math" in imps

    gov = HypergraphBlastRadiusGovernor()
    assert gov.build_graph_from_directory(tmp_path / "does_not_exist") == 0
    assert gov.build_graph_from_directory(p_sub) == 0
    total_found = gov.build_graph_from_directory(tmp_path)
    assert total_found == 2

    # 5. DependencyGraph compute_reverse_dependents_bfs depth cutoff and visited checks
    dg = DependencyGraph()
    # 3-hop chain: D -> C -> B -> A (D imports C, C imports B, B imports A)
    dg.add_dependency("B", "A")  # B imports A
    dg.add_dependency("C", "B")  # C imports B
    dg.add_dependency("D", "C")  # D imports C
    # At max_depth=3, all 3 downstream dependents (B, C, D) must be reached
    d3 = dg.compute_reverse_dependents_bfs({"A"}, max_depth=3)
    assert d3 == {"B", "C", "D"}
    # Depth 1 should only reach B
    d1 = dg.compute_reverse_dependents_bfs({"A"}, max_depth=1)
    assert d1 == {"B"}
    # Depth 2 reaches B and C
    d2 = dg.compute_reverse_dependents_bfs({"A"}, max_depth=2)
    assert d2 == {"B", "C"}
    assert "A" not in d2

    # 6. Test short_name duplicate preservation (kills CMP_FLIP on line 295)
    repo_dups = {
        "pkg1/common.py": "",
        "pkg2/common.py": "",
    }
    gov_dups = HypergraphBlastRadiusGovernor(repo_sources=repo_dups)
    assert gov_dups._module_to_file["common"] in ("pkg1/common.py", "pkg2/common.py")

    # 7. Test 1-part prefix matching in _resolve_import (kills CONST_PERTURB on line 326)
    repo_prefix = {
        "top_mod.py": "def f(): pass\n",
    }
    gov_prefix = HypergraphBlastRadiusGovernor(repo_sources=repo_prefix)
    assert gov_prefix._resolve_import("top_mod.sub_member") == "top_mod.py"

    # 8. Test build_graph_from_directory on a file (kills BOOL_SWAP on line 360)
    p_dummy_file = tmp_path / "regular_file.txt"
    p_dummy_file.write_text("not a directory", encoding="utf-8")
    assert gov_prefix.build_graph_from_directory(p_dummy_file) == 0

    # 9. Test affected_dependents_count == 0 on HALT_SCOPE_VIOLATION (kills CONST_PERTURB on line 512)
    p_scope_err = PRScopeProposal("p_err", "ag1", "ep1", "intent", ["f1.py"], 500, 0)
    rep_scope_err = gov_multi.evaluate_pr(p_scope_err)
    assert rep_scope_err.verdict == "HALT_SCOPE_VIOLATION"
    assert rep_scope_err.affected_dependents_count == 0

    # 10. Test exact rational basis points in evaluate_pr for proposal (kills line 566)
    # 2 modules: root.py and leaf.py. leaf imports root. Modifying root impacts leaf (1 / 2 = 5000 bps)
    repo_two = {
        "root.py": "",
        "leaf.py": "import root\n",
    }
    gov_two = HypergraphBlastRadiusGovernor(repo_sources=repo_two, max_blast_radius_bps=6000)
    p_two = PRScopeProposal("p_two", "ag1", "ep_two", "intent", ["root.py"], 10, 0)
    rep_two = gov_two.evaluate_pr(p_two)
    assert rep_two.verdict == "PASS"
    assert rep_two.blast_radius_bps == 5000

    # 6. Test submodule import resolution: from pkg import submodule
    repo = {
        "pkg/__init__.py": "",
        "pkg/submodule.py": "def foo(): pass\n",
        "user.py": "from pkg import submodule\ndef call(): submodule.foo()\n",
    }
    gov_sub = HypergraphBlastRadiusGovernor(repo_sources=repo)
    blast_sub = gov_sub.calculate_blast_radius(("pkg/submodule.py",))
    assert "user.py" in blast_sub.transitive_dependents
