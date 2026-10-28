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

r"""
tests/test_aeib_bench_k8s_sre_504.py — AEIB-Bench Scenario: Infrastructure Autonomy & K8s SRE Remediation
==========================================================================================================
Simulates an autonomous SRE agent (emergent machine play / unprompted remediation cycle)
formulating a Kubernetes pod mutation targeting a degraded service, encountering an HTTP 504
Gateway Timeout post-commit, and comparing:

  Arm 1 (Legacy Agent SDK): Blind speculative retry -> duplicate pod deletion / cluster outage.
  Arm 2 (AEIB v0.4.0 Wire Interlock): Uncertainty latching (retry_safe: false) -> 0 duplicate retries
                                      -> out-of-band target probe -> target ground-truth reconciliation.

Standards Reference:
  - arXiv:2610.07130 (Emergent Machine Play & Spontaneous Exploration)
  - LIMBO (arXiv:2609.29095, Li 2026 - Duplicate Side Effects in LLM Agents)
  - ISO/IEC 42001:2023 Clause 9.1 / Annex A.9.2 (Operational Anomaly Intervention)
  - EU AI Act Article 14 / 15 (Human Oversight, Robustness & Cybersecurity)
"""

import json
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import pytest
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs, generate_jcs_payload_hash
from src.governance_boundary import (
    GovernanceDecisionBoundary,
    AgentIdentityContext,
    CandidateAction,
    DelegationGrant,
)


class KubernetesClusterLedger:
    """
    Simulates the target-side Kubernetes API server and etcd datastore.
    Tracks state of pods, resource versions, and commit counts independently of client claims.
    """

    def __init__(self):
        self.pods: Dict[str, Dict[str, Any]] = {}
        self.commit_history: Dict[str, int] = {}
        self.audit_log: list = []

    def seed_pod(self, namespace: str, pod_name: str, pod_uid: str, status: str = "Running"):
        key = f"{namespace}/{pod_name}"
        self.pods[key] = {
            "uid": pod_uid,
            "namespace": namespace,
            "name": pod_name,
            "status": status,
            "deletion_timestamp": None,
            "generation": 1,
            "mutations_applied": 0
        }

    def delete_pod_mutation(self, namespace: str, pod_name: str, business_key: str, grace_period: int = 0) -> Dict[str, Any]:
        """
        Executes a pod deletion mutation in etcd.
        Returns committed mutation metadata.
        """
        key = f"{namespace}/{pod_name}"
        current = self.pods.get(key)
        
        self.commit_history[business_key] = self.commit_history.get(business_key, 0) + 1
        commit_idx = self.commit_history[business_key]

        if current is None:
            record = {
                "business_key": business_key,
                "commit_index": commit_idx,
                "status": "NOT_FOUND",
                "timestamp_utc": datetime.now(timezone.utc).isoformat()
            }
            self.audit_log.append(record)
            return record

        current["mutations_applied"] += 1
        current["status"] = "Terminating"
        current["deletion_timestamp"] = datetime.now(timezone.utc).isoformat()

        record = {
            "business_key": business_key,
            "pod_uid": current["uid"],
            "pod_name": pod_name,
            "namespace": namespace,
            "commit_index": commit_idx,
            "status": "TERMINATION_COMMITTED",
            "mutations_applied": current["mutations_applied"],
            "timestamp_utc": datetime.now(timezone.utc).isoformat()
        }
        self.audit_log.append(record)
        return record

    def probe_state(self, business_key: str) -> Dict[str, Any]:
        """
        Target-side oracle probe. Must strictly accept only the business key query string,
        with zero access to agent hypotheses or transport fault labels.
        """
        if not isinstance(business_key, str):
            raise TypeError("Oracle probe requires a string business key")

        count = self.commit_history.get(business_key, 0)
        matching_audits = [a for a in self.audit_log if a["business_key"] == business_key]
        if count == 0 or not matching_audits:
            return {"status": "NOT_FOUND", "commit_count": 0}

        latest = matching_audits[-1]
        return {
            "status": "COMMITTED",
            "commit_count": count,
            "pod_uid": latest.get("pod_uid"),
            "pod_status": latest.get("status"),
            "mutations_applied": latest.get("mutations_applied", 1)
        }


class LegacyAutonomousSREClient:
    """
    Simulates a legacy autonomous agent client (LangChain / AutoGen / standard Kube client)
    lacking wire-level uncertainty latching.
    Upon receiving an HTTP 504 timeout, it assumes transient network loss and automatically retries.
    """

    def __init__(self, cluster: KubernetesClusterLedger):
        self.cluster = cluster
        self.total_dispatches = 0

    def execute_with_blind_retry(self, namespace: str, pod_name: str, business_key: str, max_retries: int = 1) -> Dict[str, Any]:
        self.total_dispatches += 1
        # Target server commits the mutation
        _ = self.cluster.delete_pod_mutation(namespace, pod_name, business_key)
        
        # Simulated wire event: HTTP 504 Gateway Timeout (response lost in-flight)
        wire_status = 504
        
        # Legacy SDK logic: 504 triggers speculative retry
        if wire_status == 504 and max_retries > 0:
            for _ in range(max_retries):
                self.total_dispatches += 1
                # Blind retry re-dispatches exact mutation against the cluster
                _ = self.cluster.delete_pod_mutation(namespace, pod_name, business_key)

        return {
            "total_dispatches": self.total_dispatches,
            "final_commit_count": self.cluster.commit_history.get(business_key, 0)
        }


class AEIBAutonomousSREGateway:
    """
    AEIB v0.4.0 Wire-Level Execution Interlock for Infrastructure Autonomy.
    Enforces candidate binding (RFC 8785 JCS), uncertainty latching on 504 timeouts,
    zero duplicate retries, and out-of-band target-side reconciliation.
    """

    def __init__(self, cluster: KubernetesClusterLedger):
        self.cluster = cluster
        self.boundary = GovernanceDecisionBoundary()
        self.signing_key = ed25519.Ed25519PrivateKey.generate()
        self.latched_caids: Dict[str, bool] = {}
        self.execution_ledger: Dict[str, Dict[str, Any]] = {}
        self.total_gateway_dispatches = 0

    def execute_sre_mutation(
        self,
        agent_id: str,
        principal_id: str,
        namespace: str,
        pod_name: str,
        business_key: str,
        payload: Dict[str, Any],
        simulate_504: bool = False
    ) -> Dict[str, Any]:
        """
        Executes a Kubernetes cluster mutation through the AEIB decision boundary.
        """
        # 1. Candidate Action Binding via RFC 8785 JCS
        canonical_bytes = encode_jcs(payload)
        payload_hash = f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"
        candidate_caid = f"caid:{payload_hash[:32]}"

        # 2. Check for active Uncertainty Latch (Duplicate Retry Suppression)
        if self.latched_caids.get(candidate_caid, False):
            return {
                "permitted": False,
                "disposition": "DISPATCH_REJECTED (UNCERTAINTY_LATCHED_RETRY_BLOCKED)",
                "caid": candidate_caid,
                "retry_safe": False,
                "commit_count": self.cluster.commit_history.get(business_key, 0),
                "wire_event": "UNCERTAINTY_LATCHED_RETRY_BLOCKED"
            }

        # 3. Pre-dispatch wire transmission
        self.total_gateway_dispatches += 1

        # Simulate Target Execution
        self.cluster.delete_pod_mutation(namespace, pod_name, business_key)

        # 4. Handle Transport Fault (HTTP 504 Timeout)
        if simulate_504:
            # Uncertainty Latching: Freeze state at EFFECT_INDETERMINATE, lock retry_safe: False
            self.latched_caids[candidate_caid] = True
            indeterminate_receipt = {
                "caid": candidate_caid,
                "business_key": business_key,
                "disposition": "EFFECT_INDETERMINATE",
                "retry_safe": False,
                "wire_status": 504,
                "timestamp_utc": datetime.now(timezone.utc).isoformat()
            }
            self.execution_ledger[candidate_caid] = indeterminate_receipt

            return {
                "permitted": True,
                "disposition": "EFFECT_INDETERMINATE",
                "caid": candidate_caid,
                "retry_safe": False,
                "wire_status": 504,
                "latch_engaged": True,
                "receipt": indeterminate_receipt
            }

        return {
            "permitted": True,
            "disposition": "OUTCOME_CONFIRMED",
            "caid": candidate_caid,
            "retry_safe": False,
            "wire_status": 200,
            "latch_engaged": False
        }

    def reconcile_out_of_band(self, business_key: str, candidate_caid: str) -> Dict[str, Any]:
        """
        Executes single-flight out-of-band probe against target Kubernetes ledger.
        """
        probe_result = self.cluster.probe_state(business_key)
        
        if probe_result["status"] == "COMMITTED":
            final_disposition = "OUTCOME_CONFIRMED"
        else:
            final_disposition = "EFFECT_INDETERMINATE"

        # Generate Ed25519-signed bitemporal reconciliation receipt
        receipt_data = {
            "caid": candidate_caid,
            "business_key": business_key,
            "disposition": final_disposition,
            "target_commit_count": probe_result["commit_count"],
            "pod_uid": probe_result.get("pod_uid"),
            "probe_authority": "k8s_etcd_ledger_oracle",
            "timestamp_utc": datetime.now(timezone.utc).isoformat()
        }
        canonical_receipt = encode_jcs(receipt_data)
        signature = self.signing_key.sign(canonical_receipt).hex()

        return {
            "reconciliation_disposition": final_disposition,
            "target_ground_truth": probe_result,
            "signed_receipt": {
                "payload": receipt_data,
                "signature": signature,
                "algorithm": "Ed25519"
            }
        }


class TestAEIBBenchK8sSREScenario:
    """Acceptance test suite for K8s SRE Autonomous Remediation under 504 timeout."""

    def setup_method(self):
        self.namespace = "production-payment"
        self.pod_name = "payment-gateway-6d8b94f-px2w9"
        self.pod_uid = "uid_k8s_pay_9981240"
        self.business_key = "k8s_mutation_tx_prod_099182"
        self.payload = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "namespace": self.namespace,
                "name": self.pod_name,
                "uid": self.pod_uid
            },
            "spec": {
                "gracePeriodSeconds": 0
            }
        }

    def test_branch_a_legacy_sre_sdk_causes_duplicate_retry_storm(self):
        """
        Arm 1 (Legacy Agent SDK):
        Autonomous SRE experiences HTTP 504 -> triggers speculative retry -> DUPLICATE CLUSTER MUTATION.
        """
        cluster = KubernetesClusterLedger()
        cluster.seed_pod(self.namespace, self.pod_name, self.pod_uid)

        legacy_client = LegacyAutonomousSREClient(cluster)
        result = legacy_client.execute_with_blind_retry(
            namespace=self.namespace,
            pod_name=self.pod_name,
            business_key=self.business_key,
            max_retries=1
        )

        # Legacy behavior: 2 dispatches sent, 2 duplicate commits recorded in etcd
        assert result["total_dispatches"] == 2, "Legacy SDK issued blind speculative retry"
        assert result["final_commit_count"] == 2, "Legacy SDK caused duplicate mutation in target cluster"

    def test_branch_b_aeib_latches_504_and_blocks_duplicate_retry(self):
        """
        Arm 2 (AEIB v0.4.0 Wire Interlock):
        Autonomous SRE experiences HTTP 504 -> EFFECT_INDETERMINATE latched -> retry_safe: False.
        Speculative retry rejected fail-closed -> commit_count remains exactly 1.
        """
        cluster = KubernetesClusterLedger()
        cluster.seed_pod(self.namespace, self.pod_name, self.pod_uid)
        gateway = AEIBAutonomousSREGateway(cluster)

        # Step 1: Initial autonomous remediation dispatch encounters HTTP 504
        dispatch_res = gateway.execute_sre_mutation(
            agent_id="agent:infra:k8s-sre-remediator",
            principal_id="principal:sre:platform_admin",
            namespace=self.namespace,
            pod_name=self.pod_name,
            business_key=self.business_key,
            payload=self.payload,
            simulate_504=True
        )

        assert dispatch_res["disposition"] == "EFFECT_INDETERMINATE"
        assert dispatch_res["retry_safe"] is False
        assert dispatch_res["latch_engaged"] is True
        assert cluster.commit_history[self.business_key] == 1, "Target committed initial mutation"

        # Step 2: Autonomous SRE agent attempts speculative retry with same candidate
        retry_res = gateway.execute_sre_mutation(
            agent_id="agent:infra:k8s-sre-remediator",
            principal_id="principal:sre:platform_admin",
            namespace=self.namespace,
            pod_name=self.pod_name,
            business_key=self.business_key,
            payload=self.payload,
            simulate_504=False
        )

        # AEIB halts retry fail-closed: 0 duplicate retries permitted
        assert retry_res["permitted"] is False
        assert "UNCERTAINTY_LATCHED_RETRY_BLOCKED" in retry_res["disposition"]
        assert retry_res["retry_safe"] is False
        assert cluster.commit_history[self.business_key] == 1, "Target commit count must remain exactly 1"

        # Step 3: Out-of-band target reconciliation confirms ground truth
        recon_res = gateway.reconcile_out_of_band(self.business_key, dispatch_res["caid"])
        assert recon_res["reconciliation_disposition"] == "OUTCOME_CONFIRMED"
        assert recon_res["target_ground_truth"]["commit_count"] == 1
        assert recon_res["target_ground_truth"]["pod_status"] == "TERMINATION_COMMITTED"
        assert recon_res["signed_receipt"]["signature"] is not None

    def test_stale_standing_on_exploratory_context_drift(self):
        """
        Verifies that if autonomous machine play / unprompted exploration causes
        context drift or memory alteration between approval and dispatch instant,
        execution halts fail-closed with STALE_STANDING (AT29 pattern).
        """
        boundary = GovernanceDecisionBoundary(
            active_policy_epoch="policy:epoch_k8s_2026_10",
            active_standing_version="standing:v2026.10-current"
        )
        agent_id = "agent:infra:k8s-sre-remediator"
        boundary.register_agent(agent_id)

        boundary.add_grant(DelegationGrant(
            grant_id="grant_k8s_sre_valid",
            principal_id="principal:sre:platform_admin",
            authorized_agent_id=agent_id,
            allowed_verbs={"Pods:Delete", "Pods:Evict"},
            policy_epoch="policy:epoch_k8s_2026_10",
            expires_at_epoch_ms=2000000000000,
        ))

        identity = AgentIdentityContext(
            agent_id=agent_id,
            principal_id="principal:sre:platform_admin",
            tenant_id="tenant:prod-cloud-infra",
            delegation_chain=["principal:sre:platform_admin", agent_id],
            standing_version="standing:v2026.10-current",
            policy_epoch="policy:epoch_k8s_2026_10",
        )

        # Candidate approved with specific memory context digest
        approved_digest = "sha256:ctx_approved_pod_health_baseline_01"
        # Spontaneous machine play / context expansion drifted the memory digest at T_dispatch
        drifted_digest = "sha256:ctx_drifted_unprompted_cluster_exploration_02"

        candidate = CandidateAction(
            noun="Pods",
            verb="Delete",
            payload=self.payload,
            operation_id="op:k8s_sre_drift_01",
            business_idempotency_key=self.business_key,
            grant_id="grant_k8s_sre_valid",
            approved_memory_digest=approved_digest,
            memory_digest=drifted_digest
        )

        # Pre-dispatch check fails closed on memory context drift
        decision = boundary.evaluate_pre_dispatch(candidate, identity, current_time_ms=1000)
        assert decision.permitted is False
        assert decision.disposition == "STALE_STANDING"
        assert decision.retry_safe is False
        assert decision.containment_level == "C2"
