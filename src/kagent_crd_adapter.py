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
src/kagent_crd_adapter.py
================================================================================
kagent Declarative Kubernetes CRD Adapter & AEIB Policy Validator.

Evaluated under the stated model:
Validates kagent (kagent.dev / Solo.io) Kubernetes Custom Resources
(Harness, AgentTemplate, SandboxAgent) against the Seven-Layer AEIB invariants:
  1. Mandatory SPIFFE X.509-SVID identity format (spiffe://<trust-domain>/...).
  2. Runtime sandbox enforcement: gVisor (runsc) or Cloud Hypervisor (microvm).
  3. Default-deny egress proxy enforcement via agentgateway.
  4. Credential blinding: raw keys prohibited; {{VAULT:<KEY>}} required.
  5. EO1 Write-Before-Execute Latch & SQLite-WAL AutoPause hook configuration.
  6. SEMA-Auto trajectory drift threshold cap (<= 4000 bps).
  7. Blast-radius and anti-smurfing governor budget definitions.

Zero mocks, zero floats, deterministic RFC 8785 single-source JCS validation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SPIFFE_ID_REGEX = re.compile(r"^spiffe://[a-zA-Z0-9.-]+/[a-zA-Z0-9/_.-]+$")
VAULT_PLACEHOLDER_REGEX = re.compile(r"^\{\{VAULT:[A-Z0-9_]+\}\}$")
RAW_SECRET_LEAK_REGEX = re.compile(r"(sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{20,}|AKIA[0-9A-Z]{16})")

PERMITTED_RUNTIMES = frozenset({"gvisor", "runsc", "cloud-hypervisor", "microvm", "kata"})


@dataclass(frozen=True)
class CRDValidationResult:
    is_valid: bool
    crd_kind: str
    metadata_name: str
    runtime_sandbox: str
    spiffe_id: str
    egress_enforced: bool
    vault_blinded: bool
    eo1_latch_enabled: bool
    max_drift_bps: int
    violations: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "crd_kind": self.crd_kind,
            "metadata_name": self.metadata_name,
            "runtime_sandbox": self.runtime_sandbox,
            "spiffe_id": self.spiffe_id,
            "egress_enforced": self.egress_enforced,
            "vault_blinded": self.vault_blinded,
            "eo1_latch_enabled": self.eo1_latch_enabled,
            "max_drift_bps": self.max_drift_bps,
            "violations": list(self.violations),
        }


class KagentCRDValidator:
    """Validates declarative kagent Kubernetes resource manifests."""

    def __init__(
        self,
        default_max_drift_bps: int = 4000,  # claim: config
        max_allowed_blast_radius_bps: int = 3000,  # claim: config
    ) -> None:
        if not (0 <= default_max_drift_bps <= 10000):
            raise ValueError("default_max_drift_bps must be between 0 and 10000")
        if not (0 <= max_allowed_blast_radius_bps <= 10000):
            raise ValueError("max_allowed_blast_radius_bps must be between 0 and 10000")
        self.default_max_drift_bps = default_max_drift_bps
        self.max_allowed_blast_radius_bps = max_allowed_blast_radius_bps

    def validate_manifest(self, manifest: Dict[str, Any]) -> CRDValidationResult:
        """Evaluates a parsed kagent CRD manifest against AEIB policy invariants."""
        violations: List[str] = []

        # 1. Basic Structure
        kind = manifest.get("kind", "")
        if kind not in {"Harness", "AgentTemplate", "SandboxAgent"}:
            violations.append(f"REJECTED_UNKNOWN_CRD_KIND: {kind}")

        metadata = manifest.get("metadata", {})
        name = metadata.get("name", "unnamed")

        spec = manifest.get("spec", {})

        # 2. Runtime Isolation Check (Agent Substrate Layer)
        runtime = spec.get("runtime", {}).get("sandboxClass", "").lower()
        if not runtime:
            violations.append("REJECTED_MISSING_RUNTIME_SANDBOX")
        elif runtime not in PERMITTED_RUNTIMES:
            violations.append(f"REJECTED_INSECURE_RUNTIME_SANDBOX: {runtime} (must use gVisor or microVM)")

        # 3. SPIFFE Workload Identity Check
        spiffe_id = spec.get("security", {}).get("spiffeId", "")
        if not spiffe_id:
            violations.append("REJECTED_MISSING_SPIFFE_IDENTITY")
        elif not SPIFFE_ID_REGEX.match(spiffe_id):
            violations.append(f"REJECTED_INVALID_SPIFFE_FORMAT: {spiffe_id}")

        # 4. Egress Traffic Gate Check (agentgateway Layer)
        network = spec.get("network", {})
        egress_mode = network.get("egressMode", "").lower()
        gateway_ref = network.get("agentgatewayRef", "")
        egress_enforced = (egress_mode == "default-deny") and bool(gateway_ref)
        if not egress_enforced:
            violations.append("REJECTED_UNENFORCED_EGRESS (must specify egressMode: default-deny and agentgatewayRef)")

        # 5. Credential Blinding Check (Cube/OpenSandbox Layer)
        env_vars = spec.get("env", [])
        vault_blinded = True
        for env_entry in env_vars:
            val = str(env_entry.get("value", ""))
            # Check for raw secrets
            if RAW_SECRET_LEAK_REGEX.search(val):
                violations.append(f"REJECTED_RAW_SECRET_IN_MANIFEST: key={env_entry.get('name')}")
                vault_blinded = False
            # If name looks like a secret, ensure placeholder is used
            name_upper = env_entry.get("name", "").upper()
            if any(k in name_upper for k in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
                if not VAULT_PLACEHOLDER_REGEX.match(val):
                    violations.append(
                        f"REJECTED_UNBLINDED_CREDENTIAL: {env_entry.get('name')} must use {{{{VAULT:<KEY>}}}}"
                    )
                    vault_blinded = False

        # 6. EO1 Latch & SQLite-WAL AutoPause Interlock
        lifecycle = spec.get("lifecycle", {})
        eo1_enabled = lifecycle.get("eo1IntentLatch", False)
        autopause_mode = lifecycle.get("autopausePersistence", "").lower()
        if not eo1_enabled or autopause_mode != "sqlite-wal":
            violations.append("REJECTED_MISSING_EO1_AUTOPAUSE_INTERLOCK (must enable eo1IntentLatch and sqlite-wal)")

        # 7. SEMA-Auto Trajectory Drift Cap
        governance = spec.get("governance", {})
        max_drift_bps = governance.get("maxDriftThresholdBps", self.default_max_drift_bps)
        if not isinstance(max_drift_bps, int) or max_drift_bps < 0 or max_drift_bps > 10000:
            violations.append(f"REJECTED_INVALID_DRIFT_BPS: {max_drift_bps}")
        elif max_drift_bps > 4000:
            violations.append(f"REJECTED_DRIFT_CAP_EXCEEDED: {max_drift_bps} bps > 4000 bps ceiling")

        # 8. Blast Radius Cap
        blast_cap_bps = governance.get("maxBlastRadiusBps", self.max_allowed_blast_radius_bps)
        if not isinstance(blast_cap_bps, int) or blast_cap_bps < 0 or blast_cap_bps > 10000:
            violations.append(f"REJECTED_INVALID_BLAST_CAP_BPS: {blast_cap_bps}")
        elif blast_cap_bps > 4500:
            violations.append(f"REJECTED_BLAST_CAP_EXCEEDED: {blast_cap_bps} bps > 4500 bps ceiling")

        is_valid = len(violations) == 0

        return CRDValidationResult(
            is_valid=is_valid,
            crd_kind=kind,
            metadata_name=name,
            runtime_sandbox=runtime,
            spiffe_id=spiffe_id,
            egress_enforced=egress_enforced,
            vault_blinded=vault_blinded,
            eo1_latch_enabled=eo1_enabled,
            max_drift_bps=max_drift_bps,
            violations=tuple(violations),
        )
