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

"""Stage 2: Smart Action Bundler (bundler.py)

Groups mutating traces into isolated ActionBundle contexts based on:
  - action_id
  - idempotency_key
  - ±5.0s temporal cascade window
Caps evaluation envelope to 2,000 tokens max to avoid context window degradation.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from ocr_audit.dispatcher import TraceRecord


MAX_BUNDLE_TOKEN_BUDGET: int = 2000


@dataclass
class ActionBundle:
    bundle_id: str
    action_id: str
    idempotency_key: Optional[str]
    traces: List[TraceRecord] = field(default_factory=list)
    start_line_no: int = 0
    end_line_no: int = 0
    start_byte_offset: int = 0
    end_byte_offset: int = 0
    wire_facts: Dict[str, Any] = field(default_factory=dict)
    estimated_tokens: int = 0

    def add_trace(self, trace: TraceRecord) -> None:
        self.traces.append(trace)
        if self.start_line_no == 0 or trace.line_no < self.start_line_no:
            self.start_line_no = trace.line_no
            self.start_byte_offset = trace.byte_offset
        if trace.line_no > self.end_line_no:
            self.end_line_no = trace.line_no
            self.end_byte_offset = trace.byte_offset + len(json.dumps(trace.record).encode("utf-8"))

    def accepts(self, trace: TraceRecord, window_seconds: float = 5.0) -> bool:
        if trace.action_id == self.action_id:
            return True
        if (
            self.idempotency_key
            and trace.idempotency_key
            and self.idempotency_key == trace.idempotency_key
        ):
            return True
        if trace.timestamp and self.traces:
            for existing in self.traces:
                if existing.timestamp:
                    delta = abs((trace.timestamp - existing.timestamp).total_seconds())
                    if delta <= window_seconds:
                        shared_actor = (
                            existing.record.get("account_id") == trace.record.get("account_id")
                            or existing.record.get("actor") == trace.record.get("actor")
                            or existing.record.get("session_id") == trace.record.get("session_id")
                        )
                        if shared_actor:
                            return True
        return False

    def compute_wire_facts(self) -> Dict[str, Any]:
        faults: List[str] = []
        http_statuses: List[int] = []
        claimed_verdicts: List[str] = []
        commit_xids: Set[Any] = set()
        ebpf_actions: List[str] = []
        jcs_tampered = False
        signature_failed = False

        found_fault = False
        has_post_fault_retry = False
        confirmed_count = 0

        for t in self.traces:
            rec = t.record
            claimed = t.claimed_verdict
            claimed_verdicts.append(claimed)

            if claimed in ("CONFIRMED", "SETTLED", "EXECUTED", "SUCCESS"):
                confirmed_count += 1

            if t.has_wire_fault():
                found_fault = True
                faults.append(t.wire_fault)
            elif found_fault:
                has_post_fault_retry = True

            if t.http_status is not None:
                http_statuses.append(t.http_status)

            xid = rec.get("xid", rec.get("tx_id", rec.get("db_xid")))
            if xid is not None:
                commit_xids.add(xid)

            ebpf_act = rec.get("ebpf_action")
            if ebpf_act:
                ebpf_actions.append(str(ebpf_act))

            if rec.get("_jcs_tampered") or rec.get("jcs_digest_match") is False:
                jcs_tampered = True

            if rec.get("signature_valid") is False:
                signature_failed = True

        has_duplicate_disbursement = confirmed_count > 1 and len(commit_xids) > 1

        bundle_json_len = sum(len(json.dumps(t.record)) for t in self.traces)
        self.estimated_tokens = bundle_json_len // 4

        self.wire_facts = {
            "bundle_size": len(self.traces),
            "line_span": [self.start_line_no, self.end_line_no],
            "observed_faults": faults,
            "has_wire_fault": len(faults) > 0,
            "http_statuses": http_statuses,
            "claimed_verdicts": claimed_verdicts,
            "confirmed_count": confirmed_count,
            "unique_commit_xid_count": len(commit_xids),
            "commit_xids": list(commit_xids),
            "has_post_fault_retry": has_post_fault_retry,
            "has_duplicate_disbursement": has_duplicate_disbursement,
            "ebpf_actions": ebpf_actions,
            "jcs_tampered": jcs_tampered,
            "signature_failed": signature_failed,
            "estimated_tokens": self.estimated_tokens,
            "within_token_budget": self.estimated_tokens <= MAX_BUNDLE_TOKEN_BUDGET,
        }
        return self.wire_facts


class SmartActionBundler:
    def __init__(self, window_seconds: float = 5.0):
        self.window_seconds = window_seconds

    def bundle(self, traces: List[TraceRecord]) -> List[ActionBundle]:
        bundles: List[ActionBundle] = []
        for trace in traces:
            matched = False
            for b in bundles:
                if b.accepts(trace, window_seconds=self.window_seconds):
                    b.add_trace(trace)
                    matched = True
                    break

            if not matched:
                bundle_id = f"bundle-{trace.action_id}-{len(bundles)+1}"
                new_bundle = ActionBundle(
                    bundle_id=bundle_id,
                    action_id=trace.action_id,
                    idempotency_key=trace.idempotency_key,
                )
                new_bundle.add_trace(trace)
                bundles.append(new_bundle)

        for b in bundles:
            b.compute_wire_facts()

        return bundles
