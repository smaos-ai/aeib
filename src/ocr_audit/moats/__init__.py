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

"""The 8 Moats Architecture (ocr_audit.moats)

Academic & Standard-Aligned Moats for Agentic Governance:
  • Moat 1: Decision Reproducibility (IETF AAT draft-03 §13.6) -> attestation_closure
  • Moat 2: Evidence Sufficiency (IETF EP-AEG draft-00 §4.2) -> sufficiency
  • Moat 3: Evidence-Path Correctness (GroundEval arXiv:2606.22737) -> ground_eval
  • Moat 4: Runtime Data-Quality Gating (SARC-DQ arXiv:2607.26313) -> sarc_gate
  • Moat 5: Sub-Millisecond Verification (draft-wang-ccs) -> benchmark_latency
  • Moat 6: Hardware-Rooted Attestation (IETF RATS / TPM 2.0) -> hardware_attestation
  • Moat 7: Economic Incentive Alignment (AIGA draft-00) -> continuous_verifier
  • Moat 8: Pre-Access Compliance Handshake (ACD draft-03) -> compliance_handshake
"""

from ocr_audit.moats.attestation_closure import (
    AttestationClosure,
    AttestationClosureSealer,
)
from ocr_audit.moats.sufficiency import (
    RelyingPartySufficiencyEvaluator,
    RelyingPartyVerdict,
    SufficiencyEvaluation,
)
from ocr_audit.moats.ground_eval import (
    GroundEvalFuzzer,
    GroundEvalResult,
    GroundEvalScenarioType,
)
from ocr_audit.moats.sarc_gate import (
    SARCDataQualityGate,
    SARCQualityStatus,
    SARCQualityVerdict,
)
from ocr_audit.moats.benchmark_latency import (
    SubMillisecondVerifierBenchmark,
)
from ocr_audit.moats.hardware_attestation import (
    EnclaveType,
    HardwareAttestationReport,
    HardwareAttestationVerifier,
)
from ocr_audit.moats.continuous_verifier import (
    ContinuousVerificationEngine,
    ContinuousVerificationMetrics,
)
from ocr_audit.moats.compliance_handshake import (
    HandshakeDecision,
    HandshakeDisposition,
    PreToolUseComplianceGate,
)

__all__ = [
    "AttestationClosure",
    "AttestationClosureSealer",
    "RelyingPartySufficiencyEvaluator",
    "RelyingPartyVerdict",
    "SufficiencyEvaluation",
    "GroundEvalFuzzer",
    "GroundEvalResult",
    "GroundEvalScenarioType",
    "SARCDataQualityGate",
    "SARCQualityStatus",
    "SARCQualityVerdict",
    "SubMillisecondVerifierBenchmark",
    "EnclaveType",
    "HardwareAttestationReport",
    "HardwareAttestationVerifier",
    "ContinuousVerificationEngine",
    "ContinuousVerificationMetrics",
    "HandshakeDecision",
    "HandshakeDisposition",
    "PreToolUseComplianceGate",
]
