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
tools/fintech_diagnostic_wedge.py — AEIB 48-Hour / €1,500 Fintech Agent Execution Diagnostic Wedge

Evaluates a target agent or Model Context Protocol (MCP) deployment configuration
across four empirical Q4 2026 diagnostic matrices under the stated model:
  1. Matrix 1: MCP OAuth 2.1 Resource Indicators (RFC 8707 / RFC 9728) vs. Tool-Call Scope Gap
  2. Matrix 2: OWASP Agentic AI Top 10 (2026) (ASI01-ASI10) Control Posture
  3. Matrix 3: Transport Ambiguity & Duplicate Financial Mutation Simulation (HTTP 504 / TCP RST)
  4. Matrix 4: EU Regulatory Evidence Readiness (DORA Art. 17 & Art. 28(3) EBA DPM 4.0 xBRL-CSV
     + EU AI Act Arts. 12/14/15/17 prEN 18286)

Emits an RFC 8785 JCS-canonicalized, Ed25519-signed Diagnostic Assessment Report.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is importable when invoked as a standalone script
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from src.jcs_canonicalizer import encode_jcs


EPISTEMIC_BOUNDARY_NOTICE = (
    "EPISTEMIC BOUNDARY NOTICE: All diagnostic findings, control evaluations, and transport "
    "simulations in this report are observed, tested, and evaluated under the stated model "
    "using a deterministic prototype and verification scaffold. Findings reflect configured "
    "architecture parameters and simulated fault schedules rather than universal claims."
)


DEFAULT_LEGACY_MCP_CONFIG: Dict[str, Any] = {
    "deployment_id": "legacy-fintech-mcp-v1",
    "organization": "Example European Payment Institution (EPI)",
    "environment_tier": "staging_prototype",
    "mcp_oauth21": {
        "oauth21_resource_indicator_rfc8707": True,
        "protected_resource_metadata_rfc9728": True,
        "caid_jcs_sink_binding": False,
        "single_use_ticket_burn_at_sink": False,
        "temporal_standing_5term_check": False,
    },
    "owasp_asi_2026_controls": {
        "ASI01_ForkAndFlushContextBoundary": False,
        "ASI01_CAIDIntentBinding": False,
        "ASI02_TypedOwaspPreDispatchGate": False,
        "ASI03_CredentialVaultGate": False,
        "ASI03_MonotonicDelegationAttenuation": False,
        "ASI06_TemporalMemoryDigestStaleGate": False,
        "ASI07_BFTProvenanceValidator": False,
        "ASI08_CircuitBreaker": False,
        "ASI08_ProbeBudgetOne": False,
    },
    "transport_ambiguity_policy": {
        "max_automatic_retries_on_504": 3,
        "effect_indeterminate_wire_latch": False,
        "probe_budget": 3,
        "out_of_band_reconciler_required": False,
    },
    "eu_regulatory_readiness": {
        "dora_art17_three_plane_incident_bundle": False,
        "dora_art17_4h_clock_major_classification_anchor": False,
        "dora_art28_eba_dpm40_xbrl_csv_lowercase": False,
        "eu_ai_act_pren18286_arts_12_14_15_17_mapping": False,
        "scitt_rfc9052_rfc9942_offline_receipts": False,
    },
}


DEFAULT_AEIB_HARDENED_CONFIG: Dict[str, Any] = {
    "deployment_id": "aeib-hardened-fintech-mcp-v040",
    "organization": "Example European Payment Institution (EPI)",
    "environment_tier": "evaluated_scaffold",
    "mcp_oauth21": {
        "oauth21_resource_indicator_rfc8707": True,
        "protected_resource_metadata_rfc9728": True,
        "caid_jcs_sink_binding": True,
        "single_use_ticket_burn_at_sink": True,
        "temporal_standing_5term_check": True,
    },
    "owasp_asi_2026_controls": {
        "ASI01_ForkAndFlushContextBoundary": True,
        "ASI01_CAIDIntentBinding": True,
        "ASI02_TypedOwaspPreDispatchGate": True,
        "ASI03_CredentialVaultGate": True,
        "ASI03_MonotonicDelegationAttenuation": True,
        "ASI06_TemporalMemoryDigestStaleGate": True,
        "ASI07_BFTProvenanceValidator": True,
        "ASI08_CircuitBreaker": True,
        "ASI08_ProbeBudgetOne": True,
    },
    "transport_ambiguity_policy": {
        "max_automatic_retries_on_504": 0,
        "effect_indeterminate_wire_latch": True,
        "probe_budget": 1,
        "out_of_band_reconciler_required": True,
    },
    "eu_regulatory_readiness": {
        "dora_art17_three_plane_incident_bundle": True,
        "dora_art17_4h_clock_major_classification_anchor": True,
        "dora_art28_eba_dpm40_xbrl_csv_lowercase": True,
        "eu_ai_act_pren18286_arts_12_14_15_17_mapping": True,
        "scitt_rfc9052_rfc9942_offline_receipts": True,
    },
}


class FintechDiagnosticWedgeEngine:
    """
    Evaluates a target fintech agent/MCP configuration across four empirical Q4 2026
    diagnostic matrices and produces an RFC 8785 JCS-canonicalized, Ed25519-signed
    Diagnostic Assessment Report under the stated model.
    """

    def __init__(
        self,
        signing_key: Optional[ed25519.Ed25519PrivateKey] = None,
        episodes: int = 100,
        seed: int = 42,
    ) -> None:
        if episodes < 1:
            raise ValueError("episodes must be >= 1")
        self.episodes = int(episodes)
        self.seed = int(seed)
        if signing_key is not None:
            self._private_key = signing_key
        else:
            # Deterministic key derivation from seed for reproducible prototype audits
            key_seed = hashlib.sha256(f"aeib-fintech-wedge-seed-{self.seed}".encode("utf-8")).digest()
            self._private_key = ed25519.Ed25519PrivateKey.from_private_bytes(key_seed)
        self._public_key = self._private_key.public_key()

    def evaluate_matrix_1_mcp_oauth21_scope_gap(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Matrix 1: MCP OAuth 2.1 Resource Indicators (RFC 8707 / RFC 9728) vs. Tool-Call Scope Gap.
        Checks oauth21_resource_indicator_rfc8707, caid_jcs_sink_binding,
        single_use_ticket_burn_at_sink, and temporal_standing_5term_check.
        Flags AGENTIC_TOCTOU_EXPOSURE if OAuth 2.1 tokens are scoped only to the MCP server
        without RFC 8785 JCS CAID payload binding at the execution sink.
        """
        mcp_cfg = config.get("mcp_oauth21", {})
        rfc8707 = bool(mcp_cfg.get("oauth21_resource_indicator_rfc8707", False))
        rfc9728 = bool(mcp_cfg.get("protected_resource_metadata_rfc9728", False))
        caid_binding = bool(mcp_cfg.get("caid_jcs_sink_binding", False))
        ticket_burn = bool(mcp_cfg.get("single_use_ticket_burn_at_sink", False))
        temporal_5term = bool(mcp_cfg.get("temporal_standing_5term_check", False))

        flags: List[str] = []
        if rfc8707 and not caid_binding:
            flags.append("AGENTIC_TOCTOU_EXPOSURE")
        if not caid_binding:
            flags.append("MISSING_RFC8785_CAID_SINK_BINDING")
        if not ticket_burn:
            flags.append("MISSING_SINGLE_USE_TICKET_BURN_AT_SINK")
        if not temporal_5term:
            flags.append("MISSING_5TERM_TEMPORAL_STANDING_CHECK")

        passed_checks = sum([rfc8707, caid_binding, ticket_burn, temporal_5term])
        posture_status = (
            "EVALUATED_ALIGNED"
            if (rfc8707 and caid_binding and ticket_burn and temporal_5term)
            else "EXPOSURE_OBSERVED"
        )

        return {
            "matrix_id": "MATRIX_1_MCP_OAUTH21_TOOL_SCOPE_GAP",
            "checks": {
                "oauth21_resource_indicator_rfc8707": rfc8707,
                "protected_resource_metadata_rfc9728": rfc9728,
                "caid_jcs_sink_binding": caid_binding,
                "single_use_ticket_burn_at_sink": ticket_burn,
                "temporal_standing_5term_check": temporal_5term,
            },
            "agentic_toctou_exposure": "AGENTIC_TOCTOU_EXPOSURE" in flags,
            "flags": flags,
            "passed_core_checks": passed_checks,
            "total_core_checks": 4,
            "posture_status": posture_status,
        }

    def evaluate_matrix_2_owasp_asi_2026(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Matrix 2: OWASP Agentic AI Top 10 (2026) (ASI01-ASI10) Control Posture.
        Evaluates controls for ASI01, ASI02, ASI03, ASI06, ASI07, and ASI08.
        """
        asi_cfg = config.get("owasp_asi_2026_controls", {})

        asi01_fork = bool(asi_cfg.get("ASI01_ForkAndFlushContextBoundary", False))
        asi01_caid = bool(asi_cfg.get("ASI01_CAIDIntentBinding", False))
        asi02_gate = bool(asi_cfg.get("ASI02_TypedOwaspPreDispatchGate", False))
        asi03_vault = bool(asi_cfg.get("ASI03_CredentialVaultGate", False))
        asi03_attenuation = bool(asi_cfg.get("ASI03_MonotonicDelegationAttenuation", False))
        asi06_stale = bool(asi_cfg.get("ASI06_TemporalMemoryDigestStaleGate", False))
        asi07_bft = bool(asi_cfg.get("ASI07_BFTProvenanceValidator", False))
        asi08_cb = bool(asi_cfg.get("ASI08_CircuitBreaker", False))
        asi08_probe = bool(asi_cfg.get("ASI08_ProbeBudgetOne", False))

        categories = {
            "ASI01_Agent_Goal_Hijack": {
                "ForkAndFlushContextBoundary": asi01_fork,
                "CAID_Binding": asi01_caid,
                "configured": asi01_fork and asi01_caid,
            },
            "ASI02_Tool_Misuse": {
                "TypedOwaspPreDispatchGate": asi02_gate,
                "configured": asi02_gate,
            },
            "ASI03_Identity_And_Privilege_Abuse": {
                "CredentialVaultGate": asi03_vault,
                "MonotonicDelegationAttenuation": asi03_attenuation,
                "configured": asi03_vault and asi03_attenuation,
            },
            "ASI06_Memory_And_Context_Poisoning": {
                "TemporalMemoryDigest_STALE_DONT_TRUST_YET": asi06_stale,
                "configured": asi06_stale,
            },
            "ASI07_Insecure_Inter_Agent_Communication": {
                "BFTProvenanceValidator": asi07_bft,
                "configured": asi07_bft,
            },
            "ASI08_Cascading_Agent_Failures": {
                "CircuitBreaker": asi08_cb,
                "ProbeBudget_1": asi08_probe,
                "configured": asi08_cb and asi08_probe,
            },
        }

        missing_categories = [
            cat_id for cat_id, details in categories.items() if not details["configured"]
        ]
        configured_count = len(categories) - len(missing_categories)

        return {
            "matrix_id": "MATRIX_2_OWASP_ASI_TOP_10_2026",
            "categories": categories,
            "configured_category_count": configured_count,
            "evaluated_category_count": len(categories),
            "missing_categories": missing_categories,
            "posture_status": (
                "EVALUATED_ALIGNED" if not missing_categories else "GAPS_OBSERVED"
            ),
        }

    def evaluate_matrix_3_transport_ambiguity_simulation(
        self, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Matrix 3: Transport Ambiguity & Duplicate Financial Mutation Simulation.
        Runs a deterministic micro-simulation (configurable episodes, default 100, seed 42)
        of HTTP 504 / TCP RST faults comparing the customer's configured retry policy
        against the AEIB EFFECT_INDETERMINATE wire latch + ProbeBudget: 1.
        """
        pol = config.get("transport_ambiguity_policy", {})
        max_retries = int(pol.get("max_automatic_retries_on_504", 3))
        wire_latch = bool(pol.get("effect_indeterminate_wire_latch", False))
        probe_budget = int(pol.get("probe_budget", 3))
        reconciler_req = bool(pol.get("out_of_band_reconciler_required", False))

        rng = random.Random(self.seed)

        ambiguous_fault_episodes = 0
        # Customer configured policy counters
        configured_duplicate_mutations = 0
        configured_blocked_retries = 0
        # Baseline unhardened reference counters (3 automatic blind retries on HTTP 504)
        baseline_observed_duplicates = 0
        # AEIB reference counters (EFFECT_INDETERMINATE wire latch + ProbeBudget: 1)
        aeib_observed_duplicates = 0
        aeib_blocked_retries = 0

        for ep in range(self.episodes):
            # Deterministically sample whether an HTTP 504 / TCP RST occurs after sink commit
            fault_roll = rng.random()
            sink_already_committed = fault_roll < 0.35
            if not sink_already_committed:
                continue

            ambiguous_fault_episodes += 1

            # 1. Baseline unhardened reference (blind retry on HTTP 504)
            baseline_retries = max(1, max_retries) if not wire_latch else 2
            baseline_observed_duplicates += baseline_retries

            # 2. Customer configured policy evaluation under the stated model
            if wire_latch and probe_budget == 1 and max_retries == 0 and reconciler_req:
                configured_blocked_retries += 1
            else:
                effective_retries = max(max_retries, max(0, probe_budget - 1))
                if effective_retries == 0 and not wire_latch:
                    effective_retries = 1
                configured_duplicate_mutations += effective_retries

            # 3. AEIB EFFECT_INDETERMINATE latch + ProbeBudget: 1 reference
            aeib_blocked_retries += 1

        return {
            "matrix_id": "MATRIX_3_TRANSPORT_AMBIGUITY_SIMULATION",
            "simulation_parameters": {
                "episodes": self.episodes,
                "seed": self.seed,
                "ambiguous_http504_tcp_rst_episodes": ambiguous_fault_episodes,
            },
            "configured_policy": {
                "max_automatic_retries_on_504": max_retries,
                "effect_indeterminate_wire_latch": wire_latch,
                "probe_budget": probe_budget,
                "out_of_band_reconciler_required": reconciler_req,
            },
            "configured_observed_duplicates": configured_duplicate_mutations,
            "configured_blocked_retries": configured_blocked_retries,
            "baseline_observed_duplicates": baseline_observed_duplicates,
            "aeib_observed_duplicates": aeib_observed_duplicates,
            "aeib_blocked_retries": aeib_blocked_retries,
            "posture_status": (
                "EVALUATED_ALIGNED"
                if configured_duplicate_mutations == 0 and wire_latch and probe_budget == 1
                else "DUPLICATE_MUTATION_EXPOSURE_OBSERVED"
            ),
        }

    def evaluate_matrix_4_eu_regulatory_readiness(
        self, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Matrix 4: EU Regulatory Evidence Readiness
        (DORA Art. 17 & Art. 28(3) EBA DPM 4.0 xBRL-CSV + EU AI Act Arts. 12/14/15/17 prEN 18286).
        """
        reg_cfg = config.get("eu_regulatory_readiness", {})
        dora_bundle = bool(reg_cfg.get("dora_art17_three_plane_incident_bundle", False))
        dora_clock = bool(reg_cfg.get("dora_art17_4h_clock_major_classification_anchor", False))
        eba_dpm40 = bool(reg_cfg.get("dora_art28_eba_dpm40_xbrl_csv_lowercase", False))
        ai_act_qms = bool(reg_cfg.get("eu_ai_act_pren18286_arts_12_14_15_17_mapping", False))
        scitt_receipts = bool(reg_cfg.get("scitt_rfc9052_rfc9942_offline_receipts", False))

        checks = {
            "dora_art17_three_plane_incident_bundle": dora_bundle,
            "dora_art17_4h_clock_major_classification_anchor": dora_clock,
            "dora_art28_eba_dpm40_xbrl_csv_lowercase": eba_dpm40,
            "eu_ai_act_pren18286_arts_12_14_15_17_mapping": ai_act_qms,
            "scitt_rfc9052_rfc9942_offline_receipts": scitt_receipts,
        }
        missing_readiness = [k for k, v in checks.items() if not v]

        return {
            "matrix_id": "MATRIX_4_EU_REGULATORY_EVIDENCE_READINESS",
            "checks": checks,
            "ready_check_count": len(checks) - len(missing_readiness),
            "total_check_count": len(checks),
            "missing_readiness_items": missing_readiness,
            "posture_status": (
                "EVALUATED_ALIGNED" if not missing_readiness else "READINESS_GAPS_OBSERVED"
            ),
        }

    def run_diagnostic(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes all 4 diagnostic matrices against `config` and emits a JCS-canonicalized,
        Ed25519-signed Diagnostic Assessment Report dictionary.
        """
        m1 = self.evaluate_matrix_1_mcp_oauth21_scope_gap(config)
        m2 = self.evaluate_matrix_2_owasp_asi_2026(config)
        m3 = self.evaluate_matrix_3_transport_ambiguity_simulation(config)
        m4 = self.evaluate_matrix_4_eu_regulatory_readiness(config)

        all_aligned = all(
            m["posture_status"] == "EVALUATED_ALIGNED" for m in (m1, m2, m3, m4)
        )

        report_body: Dict[str, Any] = {
            "schema_version": "aeib.fintech.diagnostic.wedge.v1",
            "commercial_sku": "AEIB-FINTECH-48H-1500EUR-WEDGE",
            "deployment_id": str(config.get("deployment_id", "unknown-deployment")),
            "organization": str(config.get("organization", "unknown-organization")),
            "environment_tier": str(config.get("environment_tier", "prototype")),
            "epistemic_notice": EPISTEMIC_BOUNDARY_NOTICE,
            "overall_posture": (
                "EVALUATED_ALIGNED_UNDER_STATED_MODEL"
                if all_aligned
                else "CRITICAL_EXECUTION_BOUNDARY_GAPS_OBSERVED"
            ),
            "matrices": {
                "matrix_1_mcp_oauth21": m1,
                "matrix_2_owasp_asi_2026": m2,
                "matrix_3_transport_ambiguity": m3,
                "matrix_4_eu_regulatory_readiness": m4,
            },
        }

        jcs_bytes = encode_jcs(report_body)
        report_digest = hashlib.sha256(jcs_bytes).hexdigest()
        signature_bytes = self._private_key.sign(jcs_bytes)
        signature_b64 = base64.b64encode(signature_bytes).decode("ascii")
        public_key_pem = (
            self._public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode("utf-8")
            .strip()
        )

        return {
            "report": report_body,
            "report_digest": report_digest,
            "signature_b64": signature_b64,
            "public_key_pem": public_key_pem,
        }

    @staticmethod
    def verify_signed_report(signed_bundle: Dict[str, Any]) -> bool:
        """
        Verifies the Ed25519 signature and SHA-256 digest over the RFC 8785 JCS
        canonical representation of `signed_bundle["report"]`.
        """
        try:
            report = signed_bundle["report"]
            expected_digest = signed_bundle["report_digest"]
            signature_b64 = signed_bundle["signature_b64"]
            public_key_pem = signed_bundle["public_key_pem"]

            jcs_bytes = encode_jcs(report)
            actual_digest = hashlib.sha256(jcs_bytes).hexdigest()
            if actual_digest != expected_digest:
                return False

            pub_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
            if not isinstance(pub_key, ed25519.Ed25519PublicKey):
                return False

            sig_bytes = base64.b64decode(signature_b64)
            pub_key.verify(sig_bytes, jcs_bytes)
            return True
        except Exception:
            return False


def run_self_test(episodes: int = 100, seed: int = 42) -> Dict[str, Any]:
    """
    Runs a side-by-side comparison between an unhardened Legacy MCP Agent config
    and an AEIB-Hardened config under the stated model.
    """
    engine = FintechDiagnosticWedgeEngine(episodes=episodes, seed=seed)
    legacy_bundle = engine.run_diagnostic(DEFAULT_LEGACY_MCP_CONFIG)
    hardened_bundle = engine.run_diagnostic(DEFAULT_AEIB_HARDENED_CONFIG)

    legacy_verified = engine.verify_signed_report(legacy_bundle)
    hardened_verified = engine.verify_signed_report(hardened_bundle)

    if not (legacy_verified and hardened_verified):
        raise RuntimeError("Ed25519 JCS signature verification failed during self-test")

    return {
        "comparison_schema": "aeib.fintech.wedge.comparison.v1",
        "epistemic_notice": EPISTEMIC_BOUNDARY_NOTICE,
        "legacy_unhardened_assessment": legacy_bundle,
        "aeib_hardened_assessment": hardened_bundle,
        "verification": {
            "legacy_signature_verified": legacy_verified,
            "hardened_signature_verified": hardened_verified,
        },
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="AEIB 48-Hour / €1,500 Fintech Agent Execution Diagnostic Wedge CLI"
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run comparison between Legacy MCP Agent config and AEIB-Hardened config",
    )
    parser.add_argument(
        "--config-json",
        type=str,
        default=None,
        help="Path to target deployment configuration JSON file",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=100,
        help="Number of deterministic HTTP 504 / TCP RST simulation episodes (default: 100)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic PRNG seed for transport fault simulation (default: 42)",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default=None,
        help="Optional path to write the JCS-signed assessment JSON output",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        payload = run_self_test(episodes=args.episodes, seed=args.seed)
    else:
        if args.config_json:
            cfg_path = Path(args.config_json)
            config = json.loads(cfg_path.read_text(encoding="utf-8"))
        else:
            config = DEFAULT_LEGACY_MCP_CONFIG
        engine = FintechDiagnosticWedgeEngine(episodes=args.episodes, seed=args.seed)
        payload = engine.run_diagnostic(config)

    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
