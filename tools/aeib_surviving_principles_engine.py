#!/usr/bin/env python3
# File: tools/aeib_surviving_principles_engine.py
"""
AEIB 五大核心幸存架构原则（Five Surviving Principles — Structural Scaffold for External Prover Metadata）零 Mock 生产级实现：
1. 确定性先行 + 面向对象多态策略控制架 (Polymorphic OO-Policy Harness)
2. 可采纳性三元组状态机 (Admissibility Triad: Evidence + Authority + Standing -> ALLOW/HOLD/DENY/ESCALATE)
3. 溯源熵标签门控 (Provenance Tagging: AI_GENERATED_UNVERIFIED vs HUMAN_VERIFIED_SIGNED)
4. 纵深冗余与共享依赖单点故障探测 (Shared-Dependency SPoF Detector: HALT_SHARED_DEPENDENCY_RISK)
5. 机器身份图谱与影子智能体熔断 (Machine Identity Graph & Shadow Agent Breaker)
"""
import base64
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# RFC 8785 single source of truth: delegate to src/jcs_canonicalizer.encode_jcs
# (differential-tested in tests/test_jcs_single_source.py).
try:
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs
except ImportError:  # loaded without the repository root on sys.path
    import sys as _jcs_sys
    from pathlib import Path as _JcsPath

    _jcs_sys.path.insert(0, str(_JcsPath(__file__).resolve().parents[1]))
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs


def canonical_json_bytes(obj: Any) -> bytes:
    if isinstance(obj, float):
        raise ValueError("ERR_FLOAT_FORBIDDEN")
    return _reference_encode_jcs(obj)


def sha256_digest(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


# ============================================================================
# 原则 2 & 3 & 5：可采纳性三元组、机器身份凭证与溯源标签数据结构
# ============================================================================
@dataclass(frozen=True)
class AdmissibleEvidence:
    """可采纳证据：包含前置探针回执哈希、上下文摘要与来源溯源标签。"""
    evidence_id: str
    precondition_receipt_hashes: Tuple[str, ...]
    provenance_tag: str  # "HUMAN_VERIFIED_SIGNED" | "DETERMINISTIC_PROBE" | "AI_GENERATED_UNVERIFIED"
    taint_tier: str      # "TIER_0_PINNED" | "TIER_1_INTERNAL" | "TIER_2_UNTRUSTED"


@dataclass(frozen=True)
class ApplicableAuthority:
    """适用权限：绑定机器身份、根发起人签名与作用域。"""
    machine_identity_id: str
    root_sponsor_id: str
    allowed_action_classes: Tuple[str, ...]
    max_amount_minor: int
    sponsor_signature_b64: str


@dataclass(frozen=True)
class EstablishedStanding:
    """既定立场：当前策略纪元、剩余托管预算与系统健康态。"""
    active_policy_epoch: str
    remaining_budget_minor: int
    revoked_identities: Set[str]
    known_pinned_payees: Set[str]


@dataclass(frozen=True)
class CandidateActionProposal:
    operation_id: str
    action_class: str  # "FINANCIAL_TRANSFER" | "CODE_MUTATION" | "KNOWLEDGE_COMMIT"
    amount_minor: int
    target_resource: str
    policy_epoch: str
    touched_symbols: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AdmissibilityVerdict:
    disposition: str  # "ALLOW" | "HOLD" | "DENY" | "ESCALATE"
    reason_code: str
    caid: str
    llm_fallback_invoked: bool = False


# ============================================================================
# 原则 1：面向对象多态策略控制架 (Base Descriptive Harness & Specialized Subclasses)
# ============================================================================
class BaseDescriptivePolicyHarness:
    """
    抽象描述性控制架基类（跨所有底层模型保持 100% 不变）：
    执行确定性先行检查（机器身份、可采纳性三元组、策略纪元与签名）。
    """

    def __init__(self, sponsor_pubkeys: Dict[str, Ed25519PublicKey]) -> None:
        self.sponsor_pubkeys = dict(sponsor_pubkeys)

    def evaluate_admissibility(
        self,
        proposal: CandidateActionProposal,
        evidence: AdmissibleEvidence,
        authority: ApplicableAuthority,
        standing: EstablishedStanding,
    ) -> AdmissibilityVerdict:
        caid = sha256_digest(
            canonical_json_bytes(
                {
                    "action_class": proposal.action_class,
                    "amount_minor": proposal.amount_minor,
                    "evidence_id": evidence.evidence_id,
                    "machine_identity_id": authority.machine_identity_id,
                    "operation_id": proposal.operation_id,
                    "policy_epoch": proposal.policy_epoch,
                    "target_resource": proposal.target_resource,
                }
            )
        )

        # 1. 机器身份与影子智能体检查 (Shadow Agent Breaker)
        if authority.machine_identity_id in standing.revoked_identities:
            return AdmissibilityVerdict("DENY", "ERR_MACHINE_IDENTITY_REVOKED", caid)

        sponsor_pub = self.sponsor_pubkeys.get(authority.root_sponsor_id)
        if sponsor_pub is None:
            return AdmissibilityVerdict(
                "DENY", "ERR_SHADOW_AGENT_UNREGISTERED_SPONSOR", caid
            )

        auth_payload = canonical_json_bytes(
            {
                "allowed_action_classes": list(authority.allowed_action_classes),
                "machine_identity_id": authority.machine_identity_id,
                "max_amount_minor": authority.max_amount_minor,
                "root_sponsor_id": authority.root_sponsor_id,
            }
        )
        try:
            sponsor_pub.verify(
                base64.b64decode(authority.sponsor_signature_b64, validate=True),
                auth_payload,
            )
        except Exception:
            return AdmissibilityVerdict(
                "DENY", "ERR_INVALID_MACHINE_IDENTITY_SIGNATURE", caid
            )

        # 2. 既定立场（Standing）与策略纪元校验
        if proposal.policy_epoch != standing.active_policy_epoch:
            return AdmissibilityVerdict("DENY", "ERR_STALE_POLICY_EPOCH_STANDING", caid)

        if proposal.action_class not in authority.allowed_action_classes:
            return AdmissibilityVerdict("DENY", "ERR_ACTION_OUTSIDE_AUTHORITY_SCOPE", caid)

        # 3. 交由具体业务领域的策略子类执行多态确定性裁决 (0 LLM Token 消耗)
        return self._evaluate_domain_specific(proposal, evidence, authority, standing, caid)

    def _evaluate_domain_specific(
        self,
        proposal: CandidateActionProposal,
        evidence: AdmissibleEvidence,
        authority: ApplicableAuthority,
        standing: EstablishedStanding,
        caid: str,
    ) -> AdmissibilityVerdict:
        raise NotImplementedError


class FinancialTransferHarness(BaseDescriptivePolicyHarness):
    """针对金融结算的多态控制架子类。"""

    def _evaluate_domain_specific(
        self,
        proposal: CandidateActionProposal,
        evidence: AdmissibleEvidence,
        authority: ApplicableAuthority,
        standing: EstablishedStanding,
        caid: str,
    ) -> AdmissibilityVerdict:
        if proposal.amount_minor <= 0 or proposal.amount_minor > authority.max_amount_minor:
            return AdmissibilityVerdict("DENY", "ERR_AMOUNT_EXCEEDS_AUTHORITY_CAP", caid)

        if proposal.amount_minor > standing.remaining_budget_minor:
            return AdmissibilityVerdict("HOLD", "HOLD_INSUFFICIENT_ESCROW_BUDGET", caid)

        # 若上下文含 TIER_2 外部污染且收款方未预固定 -> 升级要求人类步进授权 (ESCALATE)
        if (
            evidence.taint_tier == "TIER_2_UNTRUSTED"
            and proposal.target_resource not in standing.known_pinned_payees
        ):
            return AdmissibilityVerdict(
                "ESCALATE", "ESCALATE_TAINTED_UNPINNED_PAYEE_REQUIRES_HUMAN", caid
            )

        # 强制要求前置余票/余额探针回执证据（无 Admissible Evidence 则挂起或拒绝）
        if not evidence.precondition_receipt_hashes:
            return AdmissibilityVerdict(
                "DENY", "ERR_MISSING_ADMISSIBLE_PRECONDITION_EVIDENCE", caid
            )

        return AdmissibilityVerdict("ALLOW", "OK", caid)


class KnowledgeVaultCommitHarness(BaseDescriptivePolicyHarness):
    """
    针对核心知识库/科学结论入库的多态控制架子类（防御合成超载与未验证 AI 幻觉入库）。
    """

    def _evaluate_domain_specific(
        self,
        proposal: CandidateActionProposal,
        evidence: AdmissibleEvidence,
        authority: ApplicableAuthority,
        standing: EstablishedStanding,
        caid: str,
    ) -> AdmissibilityVerdict:
        if evidence.provenance_tag == "AI_GENERATED_UNVERIFIED":
            return AdmissibilityVerdict(
                "ESCALATE",
                "ESCALATE_UNVERIFIED_SYNTHETIC_OUTPUT_REQUIRES_HUMAN_SIGN",
                caid,
            )
        return AdmissibilityVerdict("ALLOW", "OK", caid)


class PolymorphicHarnessRouter:
    """根据任务类型在 O(1) 时间内路由至对应的面向对象控制架子类。"""

    def __init__(self, sponsor_pubkeys: Dict[str, Ed25519PublicKey]) -> None:
        self._harnesses: Dict[str, BaseDescriptivePolicyHarness] = {
            "FINANCIAL_TRANSFER": FinancialTransferHarness(sponsor_pubkeys),
            "KNOWLEDGE_COMMIT": KnowledgeVaultCommitHarness(sponsor_pubkeys),
        }

    def route_and_evaluate(
        self,
        proposal: CandidateActionProposal,
        evidence: AdmissibleEvidence,
        authority: ApplicableAuthority,
        standing: EstablishedStanding,
    ) -> AdmissibilityVerdict:
        harness = self._harnesses.get(proposal.action_class)
        if harness is None:
            return AdmissibilityVerdict(
                "DENY", "ERR_UNREGISTERED_HARNESS_CLASS", "sha256:none"
            )
        return harness.evaluate_admissibility(proposal, evidence, authority, standing)


# ============================================================================
# 原则 4：多智能体共享依赖与单点故障探测器 (Shared-Dependency SPoF Detector)
# ============================================================================
@dataclass(frozen=True)
class AgentRuntimeTopologyNode:
    agent_id: str
    model_provider: str
    rag_vector_db_uri: str
    Write_db_connection_pool: str
    network_egress_conduit: str


class SharedDependencySpofAuditor:
    """
    探测多智能体系统中的“同沟双光缆”隐藏单点故障（Hidden SPoF）：
    即使两个并行智能体使用了不同的模型提供商（如 Anthropic 与 OpenAI），
    若它们共享同一个未隔离的底层 RAG 存储、数据库连接池或物理网络通道，
    在关键高可靠任务中触发 HALT_SHARED_DEPENDENCY_RISK。
    """

    @staticmethod
    def audit_parallel_topology(
        nodes: List[AgentRuntimeTopologyNode],
    ) -> Dict[str, Any]:
        shared_rag: List[str] = []
        shared_db_pool: List[str] = []
        shared_conduit: List[str] = []

        seen_rag: Dict[str, str] = {}
        seen_db: Dict[str, str] = {}
        seen_conduit: Dict[str, str] = {}

        for n in nodes:
            if n.rag_vector_db_uri in seen_rag:
                shared_rag.append(f"{seen_rag[n.rag_vector_db_uri]}<->{n.agent_id}")
            else:
                seen_rag[n.rag_vector_db_uri] = n.agent_id

            if n.Write_db_connection_pool in seen_db:
                shared_db_pool.append(f"{seen_db[n.Write_db_connection_pool]}<->{n.agent_id}")
            else:
                seen_db[n.Write_db_connection_pool] = n.agent_id

            if n.network_egress_conduit in seen_conduit:
                shared_conduit.append(f"{seen_conduit[n.network_egress_conduit]}<->{n.agent_id}")
            else:
                seen_conduit[n.network_egress_conduit] = n.agent_id

        has_spof = bool(shared_rag or shared_db_pool or shared_conduit)
        return {
            "disposition": "HALT_SHARED_DEPENDENCY_RISK" if has_spof else "TOPOLOGY_ISOLATED_OK",
            "shared_rag_Collisions": shared_rag,
            "shared_db_pool_collisions": shared_db_pool,
            "shared_network_conduit_collisions": shared_conduit,
        }


def test_five_surviving_principles_engine() -> None:
    sponsor_priv = Ed25519PrivateKey.generate()
    sponsor_id = "did:key:enterprise-root-sponsor"
    router = PolymorphicHarnessRouter({sponsor_id: sponsor_priv.public_key()})

    # 签发合法的机器身份凭证
    auth_core = {
        "allowed_action_classes": ["FINANCIAL_TRANSFER", "KNOWLEDGE_COMMIT"],
        "machine_identity_id": "did:machine:agent-treasury-01",
        "max_amount_minor": 1000_00,
        "root_sponsor_id": sponsor_id,
    }
    sig_b64 = base64.b64encode(
        sponsor_priv.sign(canonical_json_bytes(auth_core))
    ).decode("ascii")
    valid_authority = ApplicableAuthority(
        machine_identity_id="did:machine:agent-treasury-01",
        root_sponsor_id=sponsor_id,
        allowed_action_classes=("FINANCIAL_TRANSFER", "KNOWLEDGE_COMMIT"),
        max_amount_minor=1000_00,
        sponsor_signature_b64=sig_b64,
    )
    standing = EstablishedStanding(
        active_policy_epoch="2026-Q4",
        remaining_budget_minor=5000_00,
        revoked_identities=set(),
        known_pinned_payees={"iban:DE89370400440532013000"},
    )

    # 1. 验证影子智能体（未注册 Sponsor）被立即 DENY
    shadow_authority = ApplicableAuthority(
        machine_identity_id="did:machine:shadow-agent-99",
        root_sponsor_id="did:key:unknown-shadow-sponsor",
        allowed_action_classes=("FINANCIAL_TRANSFER",),
        max_amount_minor=100_00,
        sponsor_signature_b64=sig_b64,
    )
    prop_fin = CandidateActionProposal(
        "op-1", "FINANCIAL_TRANSFER", 500_00, "iban:DE89370400440532013000", "2026-Q4"
    )
    ev_valid = AdmissibleEvidence(
        "ev-1", ("sha256:probe-ok",), "DETERMINISTIC_PROBE", "TIER_1_INTERNAL"
    )
    v_shadow = router.route_and_evaluate(prop_fin, ev_valid, shadow_authority, standing)
    assert v_shadow.disposition == "DENY"
    assert v_shadow.reason_code == "ERR_SHADOW_AGENT_UNREGISTERED_SPONSOR"

    # 2. 验证缺失前置可采纳证据（无余票/余额探针回执）被 DENY
    ev_no_probe = AdmissibleEvidence(
        "ev-2", (), "DETERMINISTIC_PROBE", "TIER_1_INTERNAL"
    )
    v_no_ev = router.route_and_evaluate(prop_fin, ev_no_probe, valid_authority, standing)
    assert v_no_ev.disposition == "DENY"
    assert v_no_ev.reason_code == "ERR_MISSING_ADMISSIBLE_PRECONDITION_EVIDENCE"

    # 3. 验证外部污染上下文（TIER_2）向未固定收款方转账触发 ESCALATE
    prop_unpinned = CandidateActionProposal(
        "op-2", "FINANCIAL_TRANSFER", 500_00, "iban:GB00ATTACKER999", "2026-Q4"
    )
    ev_tainted = AdmissibleEvidence(
        "ev-3", ("sha256:probe-ok",), "DETERMINISTIC_PROBE", "TIER_2_UNTRUSTED"
    )
    v_esc = router.route_and_evaluate(prop_unpinned, ev_tainted, valid_authority, standing)
    assert v_esc.disposition == "ESCALATE"
    assert v_esc.reason_code == "ESCALATE_TAINTED_UNPINNED_PAYEE_REQUIRES_HUMAN"

    # 4. 验证三元组齐全时 ALLOW 放行且零 LLM 调用开销
    v_allow = router.route_and_evaluate(prop_fin, ev_valid, valid_authority, standing)
    assert v_allow.disposition == "ALLOW"
    assert v_allow.llm_fallback_invoked is False

    # 5. 验证未经人类验证签名的 AI 合成内容写入核心知识库被 ESCALATE
    prop_know = CandidateActionProposal(
        "op-know-1", "KNOWLEDGE_COMMIT", 0, "vault://math/siegel_proof", "2026-Q4"
    )
    ev_synthetic = AdmissibleEvidence(
        "ev-syn", ("sha256:lean-pending",), "AI_GENERATED_UNVERIFIED", "TIER_1_INTERNAL"
    )
    v_know = router.route_and_evaluate(
        prop_know, ev_synthetic, valid_authority, standing
    )
    assert v_know.disposition == "ESCALATE"
    assert (
        v_know.reason_code
        == "ESCALATE_UNVERIFIED_SYNTHETIC_OUTPUT_REQUIRES_HUMAN_SIGN"
    )

    # 6. 验证隐藏单点故障探测器（发现两个异构模型智能体共享同一个 RAG 向量库）
    spof_report = SharedDependencySpofAuditor.audit_parallel_topology(
        [
            AgentRuntimeTopologyNode(
                "agent-alpha", "anthropic", "redis://rag-shared:6379", "pg://pool-1", "isp-a"
            ),
            AgentRuntimeTopologyNode(
                "agent-beta", "openai", "redis://rag-shared:6379", "pg://pool-2", "isp-b"
            ),
        ]
    )
    assert spof_report["disposition"] == "HALT_SHARED_DEPENDENCY_RISK"
    assert spof_report["shared_rag_Collisions"] == ["agent-alpha<->agent-beta"]


if __name__ == "__main__":
    test_five_surviving_principles_engine()
    print(
        "FIVE SURVIVING PRINCIPLES ENGINE PASSED: "
        "OO-HARNESS ROUTING, ADMISSIBILITY TRIAD, SHADOW AGENT BREAKER, "
        "PROVENANCE TAGGING, AND SHARED-DEPENDENCY SPOF DETECTOR VERIFIED."
    )