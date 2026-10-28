#!/usr/bin/env python3
# File: tests/test_sovereign_independent_state_hub_and_chain_proxy.py
"""
Verification Suite for Section 22:
Sovereign Independent Project State Hub (`MemOS MemCube` + `Letta .af` + `Graphiti` Bi-Temporal),
Aider-Style AST Personalized PageRank `RepoMap`, & `AFlow` Zero-Memory `/decide` Chain Proxy.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.sovereign_independent_state_hub_and_chain_proxy import (
    AFlowZeroMemoryChainSelector,
    AstPersonalizedPageRankRepoMapper,
    SovereignIndependentStateHubManager,
    ZeroRepetitionPromptAndMcpProxy,
)


def test_ast_personalized_pagerank_repomap_surfaces_existing_modules() -> None:
    mapper = AstPersonalizedPageRankRepoMapper()
    results = mapper.build_personalized_pagerank_repomap(
        query="toyota 5why root cause hybrid rrf token analytics",
        top_k=5,
    )
    assert len(results) == 5
    top_paths = [r.rel_path for r in results]
    assert "src/toyota_5why_semantic_rca_and_token_analytics.py" in top_paths
    assert results[0].pagerank_score_bps == 10000
    assert results[0].sha256_digest.startswith("sha256:")


def test_aflow_zero_memory_chain_selector_and_no_wheel_matrix() -> None:
    selector = AFlowZeroMemoryChainSelector()

    # 1. Research / no-wheel intent routes to C3
    chain_c3, probs_c3, mods_c3, no_wheel = selector.select_chain(
        "research china and global github scientists what already exists without reinventing wheel"
    )
    assert chain_c3.chain_id == "C3"
    assert "--research" in chain_c3.decide_flags
    assert sum(p for _, p in probs_c3) >= 9995
    assert len(mods_c3) > 0
    assert len(no_wheel) == 5
    refs = " ".join(item.external_sota_reference for item in no_wheel)
    assert "MemOS" in refs
    assert "AFlow" in refs

    # 2. Root-cause debugging intent routes to C2
    chain_c2, _, _, _ = selector.select_chain("why did this bug fail find root cause with 5why toyota")
    assert chain_c2.chain_id == "C2"

    # 3. Explicit chain override routes to C6
    chain_c6, _, _, _ = selector.select_chain("short query", explicit_chain_id="C6")
    assert chain_c6.chain_id == "C6"
    assert len(chain_c6.decide_flags) == 6


def test_independent_state_hub_build_sync_and_tamper_falsification(tmp_path: Path) -> None:
    local_dir = tmp_path / "local_state_hub"
    ext_ssd_dir = tmp_path / "ext_ssd_state_hub"
    ext_ssd_dir.parent.mkdir(parents=True, exist_ok=True)

    mgr = SovereignIndependentStateHubManager(
        local_hub_dir=local_dir,
        ext_ssd_hub_dir=ext_ssd_dir,
    )
    capsule, paths = mgr.build_and_sync_state_hub(
        seed_query="decide deep research benchmark falsify state hub",
        valid_at_unix=1792740000,
    )

    assert "local_hub" in paths
    assert "ext_ssd_hub" in paths
    assert (local_dir / "sovereign_memcube_state.af.json").exists()
    assert (ext_ssd_dir / "sovereign_memcube_state.af.json").exists()
    assert (ext_ssd_dir / "bitemporal_state_history.jsonl").exists()
    assert (ext_ssd_dir / "live_context_brief.md").exists()

    ok, code = mgr.verify_capsule_signature(capsule)
    assert ok is True
    assert code == "VERIFIED_MEMCUBE_CAPSULE"

    # Falsification: tamper with git_branch without re-signing
    tampered = dataclasses.replace(capsule, git_branch="tampered-branch")
    ok_bad, code_bad = mgr.verify_capsule_signature(tampered)
    assert ok_bad is False
    assert code_bad == "HALT_MEMCUBE_CAID_TAMPERED"


def test_zero_repetition_prompt_and_mcp_proxy(tmp_path: Path) -> None:
    mgr = SovereignIndependentStateHubManager(
        local_hub_dir=tmp_path / "local_hub",
        ext_ssd_hub_dir=tmp_path / "ext_hub",
    )
    capsule, _ = mgr.build_and_sync_state_hub()
    proxy = ZeroRepetitionPromptAndMcpProxy(mgr)

    wrapped = proxy.wrap_short_query(
        "check token cost on argon 4 and benchmark chaos",
        channel="telegram",
        capsule=capsule,
    )
    assert wrapped.selected_chain_id == "C5"
    assert wrapped.channel == "telegram"
    assert "[AUTO-ATTACHED SOVEREIGN STATE CAPSULE (TELEGRAM)]" in wrapped.wrapped_prompt_text
    assert int(wrapped.manual_context_tokens_saved_est) == 1800

    # Test MCP 2025-11-25 resources/list, resources/read, prompts/list, prompts/get
    res_list = proxy.handle_mcp_state_and_prompt_rpc({"id": 1, "method": "resources/list"}, capsule=capsule)
    assert len(res_list["result"]["resources"]) == 2

    res_read = proxy.handle_mcp_state_and_prompt_rpc(
        {"id": 2, "method": "resources/read", "params": {"uri": "sovereign://state/brief"}},
        capsule=capsule,
    )
    assert "SovereignNexus Auto-Injected State Capsule" in res_read["result"]["contents"][0]["text"]

    prompts_list = proxy.handle_mcp_state_and_prompt_rpc({"id": 3, "method": "prompts/list"}, capsule=capsule)
    assert len(prompts_list["result"]["prompts"]) == 6

    prompt_get = proxy.handle_mcp_state_and_prompt_rpc(
        {
            "id": 4,
            "method": "prompts/get",
            "params": {"name": "decide-c4", "arguments": {"intent": "verify kernel ebpf containment"}},
        },
        capsule=capsule,
    )
    msg_text = prompt_get["result"]["messages"][0]["content"]["text"]
    assert "/decide --security --falsify --compliance" in msg_text
