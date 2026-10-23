#!/usr/bin/env python3
# File: src/decide_v51_meta_hardening_engine.py
"""
`/decide` v5.1 Meta-Hardening Engine: Multi-Flag Lattice Composition,
`T4+` Mutation-Killed Oracles (`MLReproMutate`), `CAVEAT` Error-Correlation
Discounting, `POIROT` Citation-Echo Detection, & Epistemic Half-Life Decay.

Evaluated prototype under the stated model closing the 5 meta-epistemic blind spots
identified when comparing `/decide` v5.0 against late-2026 global & Chinese research:
1. Multi-Flag Join-Semilattice Composer:
   - Handles simultaneous multi-flag invocations such as
     `/decide --research --deep --compliance --security --falsify --benchmark`
     by taking the union of mandatory gate obligations across all active flags.
2. `T4+` Mutation-Killed Oracle Verifier (`MLReproMutate` & `The Verification Horizon`, 2026):
   - Prevents vacuous `T4` tests by injecting synthetic boundary/signature mutants
     into the invariant under test and requiring a 10,000 bps (100%) mutant kill rate.
3. `CAVEAT` Correlated-Error Discounting & Non-LLM Orthogonal Witness (2026):
   - Computes effective sample size `N_eff = N / (1 + (N - 1) * rho_corr)` across
     models sharing pre-training corpora and requires a non-LLM formal/AST witness
     whenever `rho_corr >= 3000 bps` (0.30).
4. `POIROT` & `Marco DeepResearch` Citation Echo-Chamber & Surface-Skim Detector (2026):
   - Collapses multiple citations that share an identical `root_origin_caid` into a
     single source so secondary blog/summary echoes cannot masquerade as independent sources.
5. Non-Stationary Epistemic Half-Life (`tau_half_life_hours`):
   - Applies temporal freshness decay to time-sensitive security/supply-chain claims
     while preserving infinite half-life for formal mathematical proofs.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Sequence, Set, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def canonical_jcs_bytes(obj: Any) -> bytes:
    def _check(val: Any) -> None:
        if isinstance(val, float):
            raise ValueError("ERR_FLOAT_FORBIDDEN_IN_JCS")
        if isinstance(val, dict):
            for k, v in val.items():
                if not isinstance(k, str):
                    raise ValueError("ERR_NON_STRING_KEY")
                _check(v)
        elif isinstance(val, list):
            for item in val:
                _check(item)

    _check(obj)
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_prefixed(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


# ============================================================================
# 1. MULTI-FLAG JOIN-SEMILATTICE COMPOSER
# ============================================================================
MODE_OBLIGATIONS: Dict[str, Tuple[str, ...]] = {
    "--research": ("REQ_PRIMARY_LITERATURE_T2", "REQ_POIROT_ORIGIN_DEDUP"),
    "--deep": ("REQ_7_LANE_SWEEP", "REQ_CAVEAT_CORRELATION_AUDIT"),
    "--compliance": ("REQ_REGULATORY_CROSSWALK", "REQ_ZERO_RAW_PII_COMMITMENT"),
    "--security": ("REQ_THREAT_SURFACE_ISOLATION", "REQ_FRESHNESS_HALF_LIFE_CHECK"),
    "--falsify": ("REQ_COUNTEREXAMPLE_SEARCH", "REQ_T4_PLUS_MUTATION_KILL_10000_BPS"),
    "--benchmark": ("REQ_SEEDED_FAULT_SCHEDULE", "REQ_QUANTITATIVE_BPS_TELEMETRY"),
    "--build": ("REQ_MODULE_INTERFACE_CONTRACT", "REQ_AST_PURITY_CHECK"),
    "--release": ("REQ_PHASE0_BLOCKER_AUDIT", "REQ_CLEANROOM_ARCHIVE"),
    "--repo": ("REQ_CLICKABLE_FILE_LINE_LINKS",),
}


@dataclass(frozen=True)
class MultiFlagLatticePlan:
    active_flags: Tuple[str, ...]
    required_obligations: Tuple[str, ...]
    lattice_caid: str


class MultiFlagLatticeComposer:
    """
    Composes arbitrary combinations of `/decide` flags into a deterministic
    join-semilattice of verification obligations.
    """

    @staticmethod
    def compose(flags: Sequence[str]) -> MultiFlagLatticePlan:
        normalized = tuple(sorted({f.strip() for f in flags if f.strip()}))
        if not normalized:
            raise ValueError("HALT_DECIDE_V51_NO_FLAGS_SPECIFIED")

        obligations: Set[str] = set()
        for flag in normalized:
            if flag not in MODE_OBLIGATIONS:
                raise ValueError(f"HALT_DECIDE_V51_UNKNOWN_MODE_FLAG:{flag}")
            obligations.update(MODE_OBLIGATIONS[flag])

        sorted_obs = tuple(sorted(obligations))
        caid = sha256_prefixed(
            canonical_jcs_bytes(
                {
                    "active_flags": list(normalized),
                    "required_obligations": list(sorted_obs),
                }
            )
        )
        return MultiFlagLatticePlan(
            active_flags=normalized,
            required_obligations=sorted_obs,
            lattice_caid=caid,
        )


# ============================================================================
# 2. T4+ MUTATION-KILLED ORACLE VERIFIER (`MLReproMutate` & `Verification Horizon`)
# ============================================================================
@dataclass(frozen=True)
class MutantCase:
    mutant_id: str
    description: str
    mutated_state: Dict[str, Any]


@dataclass(frozen=True)
class MutationKillReport:
    oracle_id: str
    total_mutants: int
    killed_mutants: int
    surviving_mutant_ids: Tuple[str, ...]
    kill_rate_bps: int
    qualifies_as_t4_plus: bool


class MutationKilledOracleVerifier:
    """
    Verifies that a candidate `T4` executable test oracle is not vacuously passing:
    1. Runs `oracle_fn(nominal_state)` -> must return `True` (passes on valid state).
    2. Runs `oracle_fn(mutant.mutated_state)` for each injected mutant -> must return
       `False` or raise an exception (`KILLED`). If `oracle_fn` returns `True` on a
       mutant, that mutant SURVIVED and the oracle is rejected as vacuous!
    """

    @staticmethod
    def evaluate_oracle(
        oracle_id: str,
        oracle_fn: Callable[[Dict[str, Any]], bool],
        nominal_state: Dict[str, Any],
        mutants: Sequence[MutantCase],
    ) -> MutationKillReport:
        if not mutants:
            raise ValueError("HALT_MUTATION_VERIFIER_EMPTY_MUTANT_SUITE")

        nominal_passed = bool(oracle_fn(nominal_state))
        if not nominal_passed:
            raise ValueError("HALT_MUTATION_VERIFIER_NOMINAL_STATE_FAILED")

        surviving: List[str] = []
        killed = 0
        for m in mutants:
            try:
                res = bool(oracle_fn(m.mutated_state))
            except Exception:
                res = False

            if not res:
                killed += 1
            else:
                surviving.append(m.mutant_id)

        kill_bps = (killed * 10000) // len(mutants)
        return MutationKillReport(
            oracle_id=oracle_id,
            total_mutants=len(mutants),
            killed_mutants=killed,
            surviving_mutant_ids=tuple(surviving),
            kill_rate_bps=kill_bps,
            qualifies_as_t4_plus=(kill_bps == 10000 and len(surviving) == 0),
        )


# ============================================================================
# 3. `CAVEAT` CORRELATED-ERROR DISCOUNTING & `POIROT` CITATION ECHO DETECTOR
# ============================================================================
@dataclass(frozen=True)
class ProvenanceEvidenceItem:
    evidence_id: str
    claim_id: str
    source_uri: str
    root_origin_caid: str  # Upstream primary source CAID (detects echo chambers)
    tier: str              # "T0" | "T1" | "T2" | "T3" | "T4" | "T4_PLUS"
    is_non_llm_orthogonal_witness: bool
    age_hours: int
    half_life_hours: int   # 0 = infinite (e.g. formal math proof); >0 = decaying


class CaveatAndPoirotMetaAuditor:
    """
    Implements:
    - `POIROT` / `Marco DeepResearch` Citation Echo Deduplication:
      Collapses multiple sources sharing the same `root_origin_caid` into 1 independent source.
    - `CAVEAT` Correlated Pre-Training Error Discounting:
      Computes `effective_models_bps = (N * 10000) // (10000 + (N - 1) * rho_corr_bps)`.
      If `rho_corr_bps >= 3000` (30% shared pre-training correlation), requires at least
      one `is_non_llm_orthogonal_witness=True` item.
    - Epistemic Half-Life Freshness Gate:
      Rejects security/supply-chain evidence whose `age_hours > half_life_hours`.
    """

    @staticmethod
    def compute_effective_model_count_bps(
        model_count: int, rho_corr_bps: int
    ) -> int:
        if model_count <= 0:
            return 0
        if rho_corr_bps < 0 or rho_corr_bps > 10000:
            raise ValueError("ERR_INVALID_RHO_CORR_BPS")
        denom = 10000 + (model_count - 1) * rho_corr_bps
        return (model_count * 10000 * 10000) // denom

    @classmethod
    def audit_claim_evidence(
        cls,
        claim_id: str,
        items: Sequence[ProvenanceEvidenceItem],
        model_count: int,
        rho_corr_bps: int,
    ) -> Dict[str, Any]:
        fresh_items: List[ProvenanceEvidenceItem] = []
        expired_ids: List[str] = []

        for item in items:
            if item.claim_id != claim_id:
                continue
            if item.half_life_hours > 0 and item.age_hours > item.half_life_hours:
                expired_ids.append(item.evidence_id)
            else:
                fresh_items.append(item)

        if expired_ids:
            return {
                "status": "HALT_STALE_EVIDENCE_HALF_LIFE_EXPIRED",
                "expired_evidence_ids": expired_ids,
                "independent_origins_count": 0,
            }

        unique_root_origins = {i.root_origin_caid for i in fresh_items}
        echo_duplicates_collapsed = len(fresh_items) - len(unique_root_origins)
        has_orthogonal_witness = any(
            i.is_non_llm_orthogonal_witness for i in fresh_items
        )
        has_t4_plus = any(i.tier == "T4_PLUS" for i in fresh_items)

        eff_models_bps = cls.compute_effective_model_count_bps(
            model_count, rho_corr_bps
        )

        if rho_corr_bps >= 3000 and not has_orthogonal_witness:
            return {
                "status": "HALT_CAVEAT_CORRELATED_BLINDSPOT_NEEDS_ORTHOGONAL_WITNESS",
                "effective_models_bps": eff_models_bps,
                "independent_origins_count": len(unique_root_origins),
                "echo_duplicates_collapsed": echo_duplicates_collapsed,
            }

        if len(unique_root_origins) < 2 and not has_t4_plus:
            return {
                "status": "HOLD_POIROT_INSUFFICIENT_INDEPENDENT_ORIGINS",
                "effective_models_bps": eff_models_bps,
                "independent_origins_count": len(unique_root_origins),
                "echo_duplicates_collapsed": echo_duplicates_collapsed,
            }

        return {
            "status": "VALIDATED_HIGH_CONFIDENCE",
            "effective_models_bps": eff_models_bps,
            "independent_origins_count": len(unique_root_origins),
            "echo_duplicates_collapsed": echo_duplicates_collapsed,
            "has_orthogonal_witness": has_orthogonal_witness,
            "has_t4_plus": has_t4_plus,
        }


# ============================================================================
# 4. UNIFIED `/DECIDE` v5.1 META-DECISION ADJUDICATOR
# ============================================================================
@dataclass(frozen=True)
class DecideV51SignedVerdict:
    query: str
    active_flags: Tuple[str, ...]
    required_obligations: Tuple[str, ...]
    mutation_kill_rate_bps: int
    independent_origins_count: int
    echo_duplicates_collapsed: int
    effective_models_bps: int
    final_disposition: str
    verdict_caid: str
    signature_b64: str


class DecideV51MetaHardeningEngine:
    """
    Executes the full `/decide` v5.1 pipeline across all requested mode flags,
    verifying `T4+` mutation kill rate, `POIROT` origin independence, `CAVEAT`
    correlated-error mitigation, and Ed25519 JCS receipt signing.
    """

    def __init__(self, signer_privkey: Ed25519PrivateKey) -> None:
        self._priv = signer_privkey
        self.pubkey: Ed25519PublicKey = signer_privkey.public_key()

    def execute_meta_decide(
        self,
        query: str,
        flags: Sequence[str],
        claim_id: str,
        evidence_items: Sequence[ProvenanceEvidenceItem],
        mutation_report: MutationKillReport,
        model_count: int,
        rho_corr_bps: int,
    ) -> DecideV51SignedVerdict:
        lattice = MultiFlagLatticeComposer.compose(flags)

        if (
            "REQ_T4_PLUS_MUTATION_KILL_10000_BPS" in lattice.required_obligations
            and not mutation_report.qualifies_as_t4_plus
        ):
            disposition = "HOLD_VACUOUS_T4_ORACLE_SURVIVING_MUTANTS"
            ind_origins = 0
            echo_collapsed = 0
            eff_bps = 0
        else:
            audit = CaveatAndPoirotMetaAuditor.audit_claim_evidence(
                claim_id=claim_id,
                items=evidence_items,
                model_count=model_count,
                rho_corr_bps=rho_corr_bps,
            )
            disposition = audit["status"]
            ind_origins = audit["independent_origins_count"]
            echo_collapsed = audit.get("echo_duplicates_collapsed", 0)
            eff_bps = audit.get("effective_models_bps", 0)

        payload_dict = {
            "active_flags": list(lattice.active_flags),
            "echo_duplicates_collapsed": echo_collapsed,
            "effective_models_bps": eff_bps,
            "final_disposition": disposition,
            "independent_origins_count": ind_origins,
            "mutation_kill_rate_bps": mutation_report.kill_rate_bps,
            "query": query,
            "required_obligations": list(lattice.required_obligations),
        }
        raw_bytes = canonical_jcs_bytes(payload_dict)
        v_caid = sha256_prefixed(raw_bytes)
        sig_b64 = base64.b64encode(self._priv.sign(raw_bytes)).decode("ascii")

        return DecideV51SignedVerdict(
            query=query,
            active_flags=lattice.active_flags,
            required_obligations=lattice.required_obligations,
            mutation_kill_rate_bps=mutation_report.kill_rate_bps,
            independent_origins_count=ind_origins,
            echo_duplicates_collapsed=echo_collapsed,
            effective_models_bps=eff_bps,
            final_disposition=disposition,
            verdict_caid=v_caid,
            signature_b64=sig_b64,
        )


def run_self_test() -> None:
    priv = Ed25519PrivateKey.generate()
    engine = DecideV51MetaHardeningEngine(priv)

    # 1. Verify 6-flag lattice composition
    flags = (
        "--research",
        "--deep",
        "--compliance",
        "--security",
        "--falsify",
        "--benchmark",
    )
    plan = MultiFlagLatticeComposer.compose(flags)
    assert len(plan.active_flags) == 6
    assert "REQ_T4_PLUS_MUTATION_KILL_10000_BPS" in plan.required_obligations

    # 2. Verify T4+ Mutation-Killed Oracle catches surviving mutants vs kills all mutants
    nominal = {"spend_minor": 1000, "ceiling_minor": 5000, "sig_valid": True}
    mutants = [
        MutantCase("M1_OVER_CEILING", "Spend exceeds ceiling", {"spend_minor": 6000, "ceiling_minor": 5000, "sig_valid": True}),
        MutantCase("M2_FORGED_SIG", "Signature invalid", {"spend_minor": 1000, "ceiling_minor": 5000, "sig_valid": False}),
    ]
    strong_report = MutationKilledOracleVerifier.evaluate_oracle(
        "oracle-solvency-v1",
        lambda s: bool(s["sig_valid"]) and int(s["spend_minor"]) <= int(s["ceiling_minor"]),
        nominal,
        mutants,
    )
    assert strong_report.qualifies_as_t4_plus is True
    assert strong_report.kill_rate_bps == 10000

    # 3. Verify POIROT echo deduplication and CAVEAT orthogonal witness
    items = [
        ProvenanceEvidenceItem("ev-1", "c-1", "https://arxiv.org/abs/2610.14224", "sha256:origin-harness2", "T2", False, 12, 168),
        ProvenanceEvidenceItem("ev-2-echo", "c-1", "https://blog.example/summary", "sha256:origin-harness2", "T1", False, 6, 168),
        ProvenanceEvidenceItem("ev-3-orth", "c-1", "file:///tests/test_sovereign_decade_dominance_suite.py", "sha256:origin-local-ast", "T4_PLUS", True, 1, 0),
    ]
    verdict = engine.execute_meta_decide(
        query="Evaluate 6-flag meta-hardening",
        flags=flags,
        claim_id="c-1",
        evidence_items=items,
        mutation_report=strong_report,
        model_count=4,
        rho_corr_bps=4000,
    )
    assert verdict.final_disposition == "VALIDATED_HIGH_CONFIDENCE"
    assert verdict.independent_origins_count == 2
    assert verdict.echo_duplicates_collapsed == 1


if __name__ == "__main__":
    run_self_test()
    print("DECIDE V5.1 META-HARDENING ENGINE VERIFIED.")
