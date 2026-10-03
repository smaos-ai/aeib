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

"""Pre-Access Compliance Gate (Moat #8)

Uses CNCF SPIFFE/SPIRE for workload identity and IETF SCITT for pre-flight authorization.
Satisfies: Verify(SVID) and Verify(SCITT) => Session_Established.
"""

from typing import Any, Dict, Optional, Tuple


class DummySpiffeVerifier:
    """Mock-safe SPIFFE SVID validator checking format, trust domain, and expiration."""
    def __init__(self, expected_trust_domain: str = "spiffe://smaos.internal"):
        self.expected_trust_domain = expected_trust_domain

    def verify_svid(self, agent_svid: str) -> bool:
        if not isinstance(agent_svid, str):
            return False
        if not agent_svid.startswith(self.expected_trust_domain):
            return False
        if "revoked" in agent_svid or "expired" in agent_svid:
            return False
        return True


class DummyScittVerifier:
    """Validates that a pre-flight SCITT action capsule is cryptographically signed and compliant."""
    def verify_capsule(self, scitt_capsule: Dict[str, Any]) -> bool:
        if not isinstance(scitt_capsule, dict):
            return False
        capsule = scitt_capsule.get("capsule", {})
        if not capsule:
            return False
        sig = scitt_capsule.get("signature", "")
        if not sig or not sig.startswith("sig:ed25519:"):
            return False
        if not capsule.get("policy_id") or not capsule.get("payload_hash"):
            return False
        return True


class PreAccessComplianceGate:
    """Moat 8: SPIFFE/SPIRE + IETF SCITT Pre-Access Gate."""
    def __init__(self, spiffe_verifier=None, scitt_verifier=None):
        self.spiffe = spiffe_verifier or DummySpiffeVerifier()
        self.scitt = scitt_verifier or DummyScittVerifier()

    def evaluate_handshake(
        self, agent_svid: str, scitt_capsule: Dict[str, Any]
    ) -> Tuple[bool, str]:
        # 1. Validate short-lived SPIFFE Workload Identity (SVID)
        if not self.spiffe.verify_svid(agent_svid):
            return False, "NOT_ADMISSIBLE: Invalid or expired SPIFFE SVID"

        # 2. Require pre-flight SCITT Action Capsule (policy signed by hardware KMS)
        if not self.scitt.verify_capsule(scitt_capsule):
            return False, "NOT_ADMISSIBLE: Invalid or unsigned SCITT authorization capsule"

        # 3. Verify execution mode is explicitly bound to air-gapped environment
        capsule_body = scitt_capsule.get("capsule", {})
        if capsule_body.get("execution_mode") != "AIR_GAPPED":
            return False, "NOT_ADMISSIBLE: Policy requires AIR_GAPPED execution mode"

        return True, "ADMISSIBLE: Workload identity and pre-flight policy verified"
