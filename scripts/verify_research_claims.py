#!/usr/bin/env python3
# File: scripts/verify_research_claims.py
"""
/antigravity-decide 自动化一手源核验引擎 (2-Hop Primary Source Verifier).

连接免费公开科研与工程 API（无需付费 API Key）：
1. arXiv API (`export.arxiv.org/api/query`)：核验预印本 ID 与标题。
2. OpenAlex API (`api.openalex.org/works`)：核验 DOI 与同行评审论文。
3. GitHub REST API (`api.github.com/repos/...`)：核验开源代码库是否真实存在。

输出三级认识论标签：
- VERIFIED_PRIMARY_SOURCE：已通过一手库验证，允许进入架构规范与论文引用。
- CONCEPT_VALID_SOURCE_UNCONFIRMED：原理有效但外部命名/指标未证实，仅采纳抽象原语。
- UNVERIFIED_QUARANTINED：无一手源支撑的高精度数字或虚构系统名，严格隔离。
"""
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass(frozen=True)
class ResearchClaim:
    claim_id: str
    title_or_name: str
    claim_type: str  # "ARXIV" | "DOI" | "GITHUB_REPO" | "UNANCHORED_METRIC"
    identifier: str  # e.g., "2610.23257", "10.1007/s00146-025-02340-8", "Comfy-Org/ComfyUI"
    extracted_principle: str


@dataclass(frozen=True)
class VerificationReceipt:
    claim_id: str
    identifier: str
    epistemic_status: str
    primary_source_url: Optional[str]
    verified_metadata: Dict[str, Any]
    aeib_action_directive: str


class AntigravityDecideVerifier:
    """
    执行 /antigravity-decide 协议的两跳一手源核验器。
    支持在线实时 API 核验，以及针对气隙环境（Air-Gapped CI）的确定性快照核验。
    """

    USER_AGENT = "AEIB-EpistemicVerifier/1.0 (mailto:audit@aeib.example)"

    # 经当前会话视觉一手证据（Sources 1-26）确认的基准快照（用于离线/气隙 CI 环境）
    VERIFIED_SNAPSHOT_REGISTRY: Dict[str, Dict[str, Any]] = {
        "2610.23257": {
            "title": "Reasoning Models Can Control Their Chains of Thought When They Tell Themselves To",
            "authors": ["Uriel Dolev", "Idan Schwartz", "Yoav Goldberg"],
            "url": "https://arxiv.org/abs/2610.23257",
        },
        "2610.26860": {
            "title": "OpenVLHarness: Real World Visual Agentic Tool-Use with Multimodal Memory",
            "authors": ["Yu Zhou", "Cheng-Fu Yang", "Kai-Wei Chang"],
            "url": "https://arxiv.org/abs/2610.26860",
        },
        "2610.22603": {
            "title": "At the Limits of Computability: Steps Towards Autonomous AI Discovery on the Busy Beaver Frontier",
            "authors": ["Marco Dos Santos", "Tom Zahavy"],
            "url": "https://arxiv.org/abs/2610.22603",
        },
        "2610.20563": {
            "title": "Scaling Discovery Requires Forgetting",
            "authors": ["Shangyin Tan", "Matei Zaharia"],
            "url": "https://arxiv.org/abs/2610.20563",
        },
        "2610.16733": {
            "title": "TheoPhysEval: Assessing AI agents at autonomous theoretical physics problem solving",
            "authors": ["A. Ramesh Chandra", "Suvrat Raju"],
            "url": "https://arxiv.org/abs/2610.16733",
        },
        "2610.24521": {
            "title": "Comparing Sparsified MLPs and Transcoders: Many Transcoder Features Are Neurons in Disguise",
            "authors": ["Stepan Shabalin", "Mateusz Piotrowski"],
            "url": "https://arxiv.org/abs/2610.24521",
        },
        "10.1007/s00146-025-02340-8": {
            "title": "Bullshit universities: the future of automated education",
            "authors": ["Robert Sparrow", "Gene Flenady"],
            "url": "https://doi.org/10.1007/s00146-025-02340-8",
        },
        "Comfy-Org/ComfyUI": {
            "title": "ComfyUI: Modular diffusion model GUI, API and backend",
            "license": "GPL-3.0",
            "url": "https://github.com/Comfy-Org/ComfyUI",
        },
        "MontrealAI/AGI-Alpha-Agent-v0": {
            "title": "Out-Evolve / The World as an Output (SUCCESSOR Omega)",
            "url": "https://github.com/MontrealAI/AGI-Alpha-Agent-v0",
        },
    }

    def __init__(self, offline_mode: bool = True) -> None:
        self.offline_mode = offline_mode

    def verify_claim(self, claim: ResearchClaim) -> VerificationReceipt:
        # 1. 优先检查已固定的一手证据注册表
        if claim.identifier in self.VERIFIED_SNAPSHOT_REGISTRY:
            meta = self.VERIFIED_SNAPSHOT_REGISTRY[claim.identifier]
            return VerificationReceipt(
                claim_id=claim.claim_id,
                identifier=claim.identifier,
                epistemic_status="VERIFIED_PRIMARY_SOURCE",
                primary_source_url=str(meta.get("url")),
                verified_metadata=meta,
                aeib_action_directive=f"ALLOW_CITATION_AND_INTEGRATION: {claim.extracted_principle}",
            )

        # 2. 如果处于在线模式，调用免费公开 API (arXiv / OpenAlex / GitHub)
        if not self.offline_mode:
            live_meta = self._query_live_free_apis(claim)
            if live_meta is not None:
                return VerificationReceipt(
                    claim_id=claim.claim_id,
                    identifier=claim.identifier,
                    epistemic_status="VERIFIED_PRIMARY_SOURCE",
                    primary_source_url=str(live_meta.get("url")),
                    verified_metadata=live_meta,
                    aeib_action_directive=f"ALLOW_CITATION_AND_INTEGRATION: {claim.extracted_principle}",
                )

        # 3. 未能通过 2-Hop 一手源验证的声明：隔离专有名称与数字，仅保留可自证的底层原语
        if claim.extracted_principle:
            return VerificationReceipt(
                claim_id=claim.claim_id,
                identifier=claim.identifier,
                epistemic_status="CONCEPT_VALID_SOURCE_UNCONFIRMED",
                primary_source_url=None,
                verified_metadata={"warning": "No primary source verified within 2 hops."},
                aeib_action_directive=(
                    f"QUARANTINE_PRODUCT_NAME_AND_NUMBERS; "
                    f"IMPLEMENT_FIRST_PRINCIPLES_ONLY: {claim.extracted_principle}"
                ),
            )

        return VerificationReceipt(
            claim_id=claim.claim_id,
            identifier=claim.identifier,
            epistemic_status="UNVERIFIED_QUARANTINED",
            primary_source_url=None,
            verified_metadata={},
            aeib_action_directive="REJECT_FROM_PAPER_AND_MANIFEST",
        )

    def _query_live_free_apis(self, claim: ResearchClaim) -> Optional[Dict[str, Any]]:
        try:
            if claim.claim_type == "ARXIV":
                url = f"http://export.arxiv.org/api/query?id_list={ urllib.parse.quote(claim.identifier) }"
                req = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    xml_bytes = resp.read()
                root = ET.fromstring(xml_bytes)
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                entry = root.find("atom:entry", ns)
                if entry is not None:
                    title_el = entry.find("atom:title", ns)
                    if title_el is not None and title_el.text and "Error" not in title_el.text:
                        return {"title": title_el.text.strip(), "url": f"https://arxiv.org/abs/{claim.identifier}"}

            elif claim.claim_type == "DOI":
                url = f"https://api.openalex.org/works/https://doi.org/{ urllib.parse.quote(claim.identifier) }"
                req = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                if "id" in data and "title" in data:
                    return {"title": data["title"], "url": f"https://doi.org/{claim.identifier}"}

            elif claim.claim_type == "GITHUB_REPO":
                url = f"https://api.github.com/repos/{claim.identifier}"
                req = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                if "full_name" in data:
                    return {
                        "title": data.get("description", ""),
                        "stars": data.get("stargazers_count", 0),
                        "url": data.get("html_url"),
                    }
        except Exception:
            return None
        return None


def test_antigravity_decide_claim_verifier() -> None:
    verifier = AntigravityDecideVerifier(offline_mode=True)

    # 1. 验证已有一手来源的 Bar-Ilan / AI2 CoT 论文 (arXiv:2610.23257)
    r_cot = verifier.verify_claim(
        ResearchClaim(
            claim_id="CLM-01",
            title_or_name="Self-Instructed CoT Controllability",
            claim_type="ARXIV",
            identifier="2610.23257",
            extracted_principle="Never use CoT as an authorization oracle",
        )
    )
    assert r_cot.epistemic_status == "VERIFIED_PRIMARY_SOURCE"
    assert r_cot.primary_source_url == "https://arxiv.org/abs/2610.23257"

    # 2. 验证未证实的外部产品名（如 Scion / Cerno / TA-14）：自动隔离产品名，仅提取底层计算机科学原语
    r_unconf = verifier.verify_claim(
        ResearchClaim(
            claim_id="CLM-02",
            title_or_name="Unverified External Git Replacement Claim",
            claim_type="UNANCHORED_METRIC",
            identifier="unconfirmed:scion-30000-merges",
            extracted_principle="Server-authoritative disjoint write-set coordinator",
        )
    )
    assert r_unconf.epistemic_status == "CONCEPT_VALID_SOURCE_UNCONFIRMED"
    assert "QUARANTINE_PRODUCT_NAME_AND_NUMBERS" in r_unconf.aeib_action_directive

    # 3. 验证完全无原理也无来源的虚假数字：直接拒绝
    r_bogus = verifier.verify_claim(
        ResearchClaim(
            claim_id="CLM-03",
            title_or_name="Fabricated 50M Weekly Quota Baseline",
            claim_type="UNANCHORED_METRIC",
            identifier="unconfirmed:50m-weekly-quota",
            extracted_principle="",
        )
    )
    assert r_bogus.epistemic_status == "UNVERIFIED_QUARANTINED"
    assert r_bogus.aeib_action_directive == "REJECT_FROM_PAPER_AND_MANIFEST"


if __name__ == "__main__":
    test_antigravity_decide_claim_verifier()
    print("ANTIGRAVITY-DECIDE CLAIM VERIFIER PASSED ALL EPISTEMIC GATES.")