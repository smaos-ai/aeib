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

"""Stage 3: Forensic Interrogator (interrogator.py)

Isolated micro-agent execution envelope utilizing 4 scenario-tuned primitives:
  1. GetWireStatus
  2. CompareJCSDigest
  3. CheckRetryPolicy
  4. InspectDisbursementLineage
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ocr_audit.bundler import ActionBundle
from ocr_audit.tools.wire_status import get_wire_status
from ocr_audit.tools.jcs_digest import compare_jcs_digest
from ocr_audit.tools.retry_policy import check_retry_policy
from ocr_audit.tools.disbursement_lineage import inspect_disbursement_lineage


@dataclass
class CandidateFinding:
    finding_id: str
    severity: str
    category: str
    action_id: str
    claimed_verdict: str
    rationale: str
    proposed_remediation: str
    evidence_fields: Dict[str, Any] = field(default_factory=dict)


class ForensicInterrogator:
    def __init__(self):
        self.findings = []

    def evaluate_bundle(self, bundle: ActionBundle) -> List[CandidateFinding]:
        findings: List[CandidateFinding] = []
        facts = bundle.wire_facts

        # 1. Toxic Receipt check
        if facts.get("has_wire_fault"):
            for t in bundle.traces:
                if t.claimed_verdict in ("CONFIRMED", "SUCCESS", "SETTLED"):
                    findings.append(CandidateFinding(
                        finding_id=f"FIND-{bundle.action_id}-TOXIC",
                        severity="CRITICAL",
                        category="UNJUSTIFIED_CONFIRMED_ON_WIRE_FAULT",
                        action_id=t.action_id,
                        claimed_verdict=t.claimed_verdict,
                        rationale=(
                            f"Agent claimed {t.claimed_verdict} despite transport fault "
                            f"({t.wire_fault}, HTTP {t.http_status}). Violates DORA Art. 17 fail-closed requirement."
                        ),
                        proposed_remediation="Hold state as verdict: UNKNOWN; freeze retry cascade until reconciliation.",
                        evidence_fields={
                            "wire_fault": t.wire_fault,
                            "http_status": t.http_status,
                            "claimed_verdict": t.claimed_verdict,
                        },
                    ))

        # 2. Cryptographic Tampering check
        if facts.get("jcs_tampered"):
            findings.append(CandidateFinding(
                finding_id=f"FIND-{bundle.action_id}-JCS-MISMATCH",
                severity="CRITICAL",
                category="CRYPTOGRAPHIC_DIGEST_MISMATCH",
                action_id=bundle.action_id,
                claimed_verdict="CONFIRMED",
                rationale="Payload canonical JCS hash does not match claimed digest. Potential in-transit tampering.",
                proposed_remediation="Immediate HALT; reject receipt under RFC 8785 integrity verification.",
                evidence_fields={"jcs_tampered": True},
            ))

        # 3. Retry Policy check
        retry_check = check_retry_policy(bundle, bundle.action_id)
        if retry_check["unheld_retry_storm"]:
            findings.append(CandidateFinding(
                finding_id=f"FIND-{bundle.action_id}-RETRY-STORM",
                severity="HIGH",
                category="UNCONTROLLED_RETRY_STORM",
                action_id=bundle.action_id,
                claimed_verdict="RETRY",
                rationale="Agent fired mutating retry after transport failure without setting retry_held=True.",
                proposed_remediation="Enforce exponential backoff and circuit breaker pause on 5xx errors.",
                evidence_fields=retry_check,
            ))

        # 4. Disbursement Lineage check
        lineage_check = inspect_disbursement_lineage(bundle, bundle.action_id)
        if lineage_check.get("orphaned_disbursement"):
            findings.append(CandidateFinding(
                finding_id=f"FIND-{bundle.action_id}-ORPHAN",
                severity="CRITICAL",
                category="ORPHANED_DISBURSEMENT_RECORD",
                action_id=bundle.action_id,
                claimed_verdict="CONFIRMED",
                rationale="Disbursement lacks valid parent authorization action_id.",
                proposed_remediation="Revoke transaction; enforce parent intent attachment.",
                evidence_fields=lineage_check,
            ))

        # 5. Jev Intent vs. Wire Settlement Reconciliation Gate
        for t in bundle.traces:
            jev_intent = str(t.record.get("jev_intent", t.record.get("jev_guard", t.record.get("intent_decision", "NONE")))).lower()
            if jev_intent in ("allow", "approved"):
                if t.http_status in (500, 502, 503, 504) or facts.get("has_wire_fault"):
                    findings.append(CandidateFinding(
                        finding_id=f"FIND-{t.action_id}-JEV-COLLISION",
                        severity="CRITICAL",
                        category="JEV_INTENT_WIRE_FAULT_COLLISION",
                        action_id=t.action_id,
                        claimed_verdict=t.claimed_verdict,
                        rationale=(
                            f"Jev pre-execution intent was '{jev_intent.upper()}', but backend network dropped with "
                            f"HTTP {t.http_status} / {t.wire_fault}. Violates Wire Settlement Invariant. State must downgrade to UNKNOWN."
                        ),
                        proposed_remediation="Downgrade state immediately to verdict: UNKNOWN. Freeze retries to prevent double-disbursement.",
                        evidence_fields={
                            "jev_intent": jev_intent,
                            "wire_status": t.http_status,
                            "wire_fault": t.wire_fault,
                            "claimed_verdict": t.claimed_verdict,
                        },
                    ))
            elif jev_intent in ("deny", "blocked", "prohibited"):
                if t.is_mutating():
                    findings.append(CandidateFinding(
                        finding_id=f"FIND-{t.action_id}-JEV-DISPATCH-VIOLATION",
                        severity="CRITICAL",
                        category="JEV_DENIAL_MUTATION_ATTEMPT",
                        action_id=t.action_id,
                        claimed_verdict=t.claimed_verdict,
                        rationale=(
                            f"Jev pre-execution intent was '{jev_intent.upper()}', but agent attempted "
                            f"mutating action '{t.action_type}'. Pre-execution gate bypassed."
                        ),
                        proposed_remediation="Intercept and halt execution at kernel boundary (EPERM / HALT).",
                        evidence_fields={
                            "jev_intent": jev_intent,
                            "action_type": t.action_type,
                        },
                    ))

        return findings
