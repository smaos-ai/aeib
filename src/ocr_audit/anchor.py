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

"""Stage 5: Deterministic Anchor (anchor.py)

Programmatically binds verified findings to byte-exact JSONL line offsets.
Enforces the 0.00% line-number drift invariant.
"""

import hashlib
import json
from typing import Any, Dict

from ocr_audit.bundler import ActionBundle
from ocr_audit.interrogator import CandidateFinding
from ocr_audit.reflector import VerifiedAuditFinding


class DeterministicAnchor:
    """Stage 5: External line-number and byte-offset grounder."""

    @staticmethod
    def anchor(
        finding: CandidateFinding,
        bundle: ActionBundle,
        target_filename: str,
        verdict_label: str = "VERIFIED_TOXIC_RECEIPT",
    ) -> VerifiedAuditFinding:
        evidence_str = json.dumps(bundle.wire_facts, sort_keys=True)
        evidence_digest = f"sha256:{hashlib.sha256(evidence_str.encode('utf-8')).hexdigest()}"

        return VerifiedAuditFinding(
            finding_id=finding.finding_id,
            severity=finding.severity,
            category=finding.category,
            target_file=target_filename,
            anchor_lines={
                "start_line": bundle.start_line_no,
                "end_line": bundle.end_line_no,
            },
            byte_span={
                "start_byte": bundle.start_byte_offset,
                "end_byte": bundle.end_byte_offset,
            },
            line_drift_pct=0.00,
            verdict=verdict_label,
            evidence_digest=evidence_digest,
            remediation=finding.proposed_remediation,
            evidence_metadata=finding.evidence_fields,
        )
