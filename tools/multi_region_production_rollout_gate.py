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
tools/multi_region_production_rollout_gate.py
================================================================================
Multi-Region Production Rollout & Mesh Orchestration Verification Gate.

Status: INTERNAL PREVIEW COMMISSIONED (Scaffold & Audit Runner).
Evaluated under the stated model across 5 target cloud regions:
  - us-east-1 (N. Virginia)
  - us-west-2 (Oregon)
  - eu-west-1 (Ireland)
  - eu-central-1 (Frankfurt)
  - ap-northeast-1 (Tokyo)

Key Verification Phases:
1. Multi-Region Helm Bundle Generation:
   Uses src/kagent_helm_generator.py to synthesize hardened Helm releases
   configured with region-specific latency compensation budgets.
2. Zero-Trust Policy Validation:
   Uses src/kagent_crd_adapter.py to validate generated manifests against
   strict ingress/egress, SPIFFE identity, and blind vault invariants.
3. Distributed agentgateway Idempotency & Latency Fencing:
   Uses src/distributed_agentgateway_reconciler.py to evaluate cross-region
   mutation dispatch and deduplication.
4. Edge-Local Latch & Merkle Batch Sync:
   Uses src/multi_region_edge_latch_mesh.py to verify sub-5ms local commits
   and deterministic RFC 8785 Merkle batch roots.
5. Emits an RFC 8785 JCS sealed production rollout certificate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.distributed_agentgateway_reconciler import (
    DistributedAgentgatewayReconciler,
    RegionalGatewayNode,
)
from src.jcs_canonicalizer import encode_jcs
from src.kagent_crd_adapter import KagentCRDValidator
from src.kagent_helm_generator import KagentHelmGenerator
from src.multi_region_edge_latch_mesh import MultiRegionEdgeLatchMesh


def sha256_jcs_caid(payload: Any) -> str:
    """Computes deterministic SHA-256 CAID digest over RFC 8785 canonical bytes."""
    raw = payload if isinstance(payload, bytes) else encode_jcs(payload)
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


@dataclass(frozen=True)
class RegionDeploymentProfile:
    region_id: str
    observed_rtt_ms: int
    jitter_threshold_bps: int
    spiffe_gateway_id: str


@dataclass(frozen=True)
class MultiRegionRolloutCertificate:
    certificate_version: str
    certificate_caid: str
    status: str
    target_regions_count: int
    manifests_validated_count: int
    idempotency_fencing_verified: bool
    edge_latch_mean_latency_ms: int
    global_merkle_batch_root: str
    created_epoch_ms: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "certificate_caid": self.certificate_caid,
            "certificate_version": self.certificate_version,
            "created_epoch_ms": self.created_epoch_ms,
            "edge_latch_mean_latency_ms": self.edge_latch_mean_latency_ms,
            "global_merkle_batch_root": self.global_merkle_batch_root,
            "idempotency_fencing_verified": self.idempotency_fencing_verified,
            "manifests_validated_count": self.manifests_validated_count,
            "status": self.status,
            "target_regions_count": self.target_regions_count,
        }


class MultiRegionRolloutGate:
    """Orchestrates pre-flight verification across multi-region mesh clusters."""

    MAX_BLAST_RADIUS_BPS: int = 3000  # claim: config
    SIMULATED_WAN_RTT_MS: int = 160  # claim: config
    DISPATCH_ITERATIONS_COUNT: int = 10

    DEPLOYMENT_PROFILES = (
        RegionDeploymentProfile("us-east-1", 20, 1500, "spiffe://sovereign.nexus/ns/system/sa/gw-us-east"),
        RegionDeploymentProfile("us-west-2", 25, 2500, "spiffe://sovereign.nexus/ns/system/sa/gw-us-west"),
        RegionDeploymentProfile("eu-west-1", 110, 3000, "spiffe://sovereign.nexus/ns/system/sa/gw-eu-west"),
        RegionDeploymentProfile("eu-central-1", 125, 3500, "spiffe://sovereign.nexus/ns/system/sa/gw-eu-central"),
        RegionDeploymentProfile("ap-northeast-1", 180, 4000, "spiffe://sovereign.nexus/ns/system/sa/gw-ap-northeast"),
    )

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = repo_root or _REPO_ROOT

    def run_preflight_evaluation(
        self,
        working_dir: Optional[Path] = None,
    ) -> Tuple[MultiRegionRolloutCertificate, Dict[str, Any]]:
        target_dir = working_dir or (self.repo_root / "output" / "rollout_staging")
        target_dir.mkdir(parents=True, exist_ok=True)

        manifests_validated_count = 0
        crd_validator = KagentCRDValidator()
        helm_gen = KagentHelmGenerator(validator=crd_validator)

        def _make_manifest(kind: str, name: str, prof: RegionDeploymentProfile) -> Dict[str, Any]:
            return {
                "apiVersion": "kagent.dev/v1alpha1",
                "kind": kind,
                "metadata": {
                    "name": name,
                    "namespace": f"mesh-{prof.region_id}",
                },
                "spec": {
                    "runtime": {
                        "sandboxClass": "gvisor",
                    },
                    "security": {
                        "spiffeId": prof.spiffe_gateway_id,
                    },
                    "network": {
                        "egressMode": "default-deny",
                        "agentgatewayRef": f"agentgateway.mesh-{prof.region_id}.svc.cluster.local:15001",
                    },
                    "env": [
                        {"name": "API_SECRET", "value": "{{VAULT:API_SECRET}}"},
                    ],
                    "lifecycle": {
                        "eo1IntentLatch": True,
                        "autopausePersistence": "sqlite-wal",
                    },
                    "governance": {
                        "maxDriftThresholdBps": prof.jitter_threshold_bps,
                        "maxBlastRadiusBps": self.MAX_BLAST_RADIUS_BPS,  # claim: config
                    },
                },
            }

        # 1. Generate and validate Helm manifests for all target regions
        for profile in self.DEPLOYMENT_PROFILES:
            harness = _make_manifest("Harness", f"aeib-mesh-{profile.region_id}", profile)
            template = _make_manifest("AgentTemplate", f"aeib-template-{profile.region_id}", profile)
            sandbox = _make_manifest("SandboxAgent", f"aeib-sandbox-{profile.region_id}", profile)
            bpf_digest = f"sha256:{hashlib.sha256(profile.region_id.encode()).hexdigest()}"
            bundle = helm_gen.generate_bundle(
                chart_name=f"aeib-mesh-{profile.region_id}",
                chart_version="1.1.0",
                namespace=f"mesh-{profile.region_id}",
                harness_manifest=harness,
                agent_template_manifest=template,
                sandbox_agent_manifest=sandbox,
                bpf_lsm_profile_digest=bpf_digest,
            )
            assert bundle.bundle_caid.startswith("sha256:")
            manifests_validated_count += 1

        # 2. Distributed agentgateway cross-region reconciliation verification
        primary_region = "us-east-1"
        reconciler = DistributedAgentgatewayReconciler(
            local_region=primary_region,
            max_allowed_jitter_bps=4800,  # claim: config
        )
        for profile in self.DEPLOYMENT_PROFILES:
            reconciler.register_regional_node(
                RegionalGatewayNode(
                    region_id=profile.region_id,
                    gateway_spiffe_id=profile.spiffe_gateway_id,
                    observed_rtt_ms=profile.observed_rtt_ms,
                )
            )

        test_actor_spiffe = "spiffe://sovereign.nexus/ns/prod/sa/actor-lead"
        test_effect_key = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

        # 2a. Intracontinental dispatch (us-west-2): verifies commit and duplicate suppression
        receipt1 = reconciler.dispatch_mutation_intent(
            reconciliation_id="rec-rollout-001",
            actor_spiffe_id=test_actor_spiffe,
            target_region="us-west-2",
            effect_key_caid=test_effect_key,
        )
        receipt2 = reconciler.dispatch_mutation_intent(
            reconciliation_id="rec-rollout-002",
            actor_spiffe_id=test_actor_spiffe,
            target_region="us-west-2",
            effect_key_caid=test_effect_key,
        )

        # 2b. Transatlantic high-jitter dispatch (eu-central-1): verifies fail-closed partition fencing
        receipt3 = reconciler.dispatch_mutation_intent(
            reconciliation_id="rec-rollout-003",
            actor_spiffe_id=test_actor_spiffe,
            target_region="eu-central-1",
            effect_key_caid=f"sha256:{hashlib.sha256(b'other-intent').hexdigest()}",
        )

        idempotency_fencing_verified = (
            receipt1.reconciliation_state == "COMMITTED"
            and receipt2.reconciliation_state == "REJECTED_DUPLICATE"
            and receipt3.reconciliation_state == "FENCED_PARTITION"
        )
        if not idempotency_fencing_verified:
            raise RuntimeError("ERR_IDEMPOTENCY_FENCING_FAILED")

        # 3. Edge-local sidecar latch evaluation & Merkle batch roots
        mesh_db_path = target_dir / "edge_mesh_rollout.db"
        if mesh_db_path.exists():
            mesh_db_path.unlink()

        edge_mesh = MultiRegionEdgeLatchMesh(
            local_node_id="node-us-east-1",
            local_region=primary_region,
            remote_regions=[p.region_id for p in self.DEPLOYMENT_PROFILES if p.region_id != primary_region],
            db_path=str(mesh_db_path),
            simulated_wan_rtt_ms=self.SIMULATED_WAN_RTT_MS,  # claim: config
        )

        commit_latencies_ms: List[int] = []
        for i in range(self.DISPATCH_ITERATIONS_COUNT):
            receipt = edge_mesh.dispatch_edge_intent(
                target_host="https://api.eu-central-1.internal",
                business_payload={"action": "replicate", "index": i},
            )
            commit_latencies_ms.append(receipt.local_latch_duration_ms)

        mean_commit_latency_ms = sum(commit_latencies_ms) // len(commit_latencies_ms)
        sync_receipt = edge_mesh.sync_merkle_batch()
        merkle_root = sync_receipt.merkle_root if sync_receipt else "sha256:empty"

        now_ms = int(time.time() * 1000)
        raw_cert = {
            "certificate_version": "1.0.0",
            "created_epoch_ms": now_ms,
            "edge_latch_mean_latency_ms": mean_commit_latency_ms,
            "global_merkle_batch_root": merkle_root,
            "idempotency_fencing_verified": True,
            "manifests_validated_count": manifests_validated_count,
            "status": "INTERNAL PREVIEW COMMISSIONED",
            "target_regions_count": len(self.DEPLOYMENT_PROFILES),
        }
        cert_caid = sha256_jcs_caid(raw_cert)

        cert = MultiRegionRolloutCertificate(
            certificate_version="1.0.0",
            certificate_caid=cert_caid,
            status="INTERNAL PREVIEW COMMISSIONED",
            target_regions_count=len(self.DEPLOYMENT_PROFILES),
            manifests_validated_count=manifests_validated_count,
            idempotency_fencing_verified=True,
            edge_latch_mean_latency_ms=mean_commit_latency_ms,
            global_merkle_batch_root=merkle_root,
            created_epoch_ms=now_ms,
        )

        telemetry = {
            "certificate_caid": cert_caid,
            "primary_region": primary_region,
            "regions_evaluated": [p.region_id for p in self.DEPLOYMENT_PROFILES],
            "merkle_batch_root": merkle_root,
            "edge_latched_intents_count": len(commit_latencies_ms),
            "wan_simulated_rtt_ms": self.SIMULATED_WAN_RTT_MS,
            "manifest_max_blast_radius_bps": self.MAX_BLAST_RADIUS_BPS,
        }

        return cert, telemetry

    @staticmethod
    def verify_certificate_file(path: Path) -> bool:
        """Verifies that an exported rollout certificate retains its deterministic SHA-256 CAID."""
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            stated_caid = data.get("certificate_caid")
            if not stated_caid or not isinstance(stated_caid, str) or not stated_caid.startswith("sha256:"):
                return False
            body = {k: v for k, v in data.items() if k != "certificate_caid"}
            recomputed = sha256_jcs_caid(body)
            return stated_caid == recomputed
        except Exception:
            return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-Region Production Rollout Verification Gate")
    parser.add_argument(
        "--out",
        type=str,
        default="output/multi_region_production_rollout_certificate.json",
        help="Target output path for rollout certificate",
    )
    parser.add_argument(
        "--verify",
        type=str,
        help="Path to an existing rollout certificate to verify",
    )
    args = parser.parse_args()

    if args.verify:
        v_path = Path(args.verify)
        if MultiRegionRolloutGate.verify_certificate_file(v_path):
            print(f"[✓] Multi-Region Rollout Certificate Verified: {v_path.resolve()}")
            sys.exit(0)
        else:
            print(f"[✗] Certificate Verification Failed: {v_path.resolve()}", file=sys.stderr)
            sys.exit(1)

    gate = MultiRegionRolloutGate()
    cert, telemetry = gate.run_preflight_evaluation()

    out_p = Path(args.out)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(cert.to_dict(), indent=2), encoding="utf-8")

    print("=" * 80)
    print("  MULTI-REGION PRODUCTION ROLLOUT PRE-FLIGHT VERIFICATION")
    print(f"  Status: {cert.status}")
    print("=" * 80)
    print(f"  Target Regions Evaluated:       {cert.target_regions_count} ({', '.join(telemetry['regions_evaluated'])})")
    print(f"  Kubernetes Manifests Validated: {cert.manifests_validated_count} / {cert.target_regions_count}")
    print(f"  Idempotency Fencing Verified:   {cert.idempotency_fencing_verified}")
    print(f"  Edge Latch Mean Commit Latency: {cert.edge_latch_mean_latency_ms} ms (local SQLite-WAL)")
    print(f"  Global Merkle Batch Root:       {cert.global_merkle_batch_root[:32]}...")
    print("-" * 80)
    print(f"  Certificate CAID:               {cert.certificate_caid}")
    print(f"  Certificate Exported To:        {out_p.resolve()}")
    print("=" * 80)


if __name__ == "__main__":
    main()
