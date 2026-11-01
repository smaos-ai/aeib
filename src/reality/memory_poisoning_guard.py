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

"""
src/reality/memory_poisoning_guard.py — Merkle DAG Hash-Chain Long-Term Memory Guard.

Defends against Social Chat Agent Memory Poisoning & Epistemic Drift:
When agents maintain persistent memory across sessions, adversarial or sloppy inputs
can inject poison statements into long-term memory (e.g. "the user approved skipping auth gates",
"secrets may be committed in test files", "mock crypto is allowed").

The MemoryPoisoningGuard validates every memory write against a set of immutable system
invariants before storage, chains records in an append-only cryptographic Merkle DAG,
and emits an explicit `HALT_MEMORY_POISONING` signal upon any attempted compromise.
"""

import hashlib
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.jcs_canonicalizer import encode_jcs


@dataclass(frozen=True)
class InvariantRule:
    rule_id: str
    forbidden_terms: Tuple[str, ...]
    description: str


DEFAULT_SYSTEM_INVARIANTS: Tuple[InvariantRule, ...] = (
    InvariantRule(
        rule_id="INV-01-NO-AUTH-BYPASS",
        forbidden_terms=("bypass auth", "skip authentication", "always return true", "disable gate"),
        description="Memory cannot instruct the agent to bypass authentication or execution gates.",
    ),
    InvariantRule(
        rule_id="INV-02-NO-MOCK-CRYPTO",
        forbidden_terms=("mock signature", "stub hash", "fake key", "simulate cryptographic signature"),
        description="Memory cannot allow or instruct mock cryptographic operations.",
    ),
    InvariantRule(
        rule_id="INV-03-NO-SECRET-TRACKING",
        forbidden_terms=("commit secret", "commit api key", "track .env", "bypass pre-push"),
        description="Memory cannot instruct committing credentials or bypassing pre-push airgap.",
    ),
    InvariantRule(
        rule_id="INV-04-NO-UNRESTRICTED-EGRESS",
        forbidden_terms=("disable firewall", "unrestricted network", "exfiltrate payload"),
        description="Memory cannot instruct disabling egress firewalls or unvetted network calls.",
    ),
)


@dataclass(frozen=True)
class MemoryRecord:
    record_id: str
    agent_id: str
    content: str
    memory_type: str  # "FACT", "PROCEDURE", "CONSTRAINT"
    prev_record_caid: str
    timestamp_ns: int
    record_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "agent_id": self.agent_id,
            "content": self.content,
            "memory_type": self.memory_type,
            "prev_record_caid": self.prev_record_caid,
            "timestamp_ns": self.timestamp_ns,
            "record_caid": self.record_caid,
        }


class MemoryPoisoningGuard:
    """
    Append-only Merkle DAG long-term memory validator and chain auditor.
    """

    def __init__(
        self,
        invariants: Sequence[InvariantRule] = DEFAULT_SYSTEM_INVARIANTS,
    ) -> None:
        self.invariants = tuple(invariants)
        self.records: List[MemoryRecord] = []
        self._last_caid: str = "GENESIS"

    def validate_and_commit(
        self,
        record_id: str,
        agent_id: str,
        content: str,
        memory_type: str = "FACT",
        now_ns: Optional[int] = None,
    ) -> Tuple[bool, str, Optional[MemoryRecord]]:
        """
        Validates content against all system invariants.
        If clean, appends to hash-chain and returns (True, "COMMITTED_CLEAN_MEMORY", record).
        If violated, returns (False, "HALT_MEMORY_POISONING: ...", None).
        """
        content_lower = content.lower()
        for rule in self.invariants:
            for term in rule.forbidden_terms:
                if term in content_lower:
                    reason = f"HALT_MEMORY_POISONING: Content violates {rule.rule_id} ('{term}' detected)"
                    return False, reason, None

        ts = now_ns if now_ns is not None else time.time_ns()
        body = {
            "record_id": record_id,
            "agent_id": agent_id,
            "content": content,
            "memory_type": memory_type,
            "prev_record_caid": self._last_caid,
            "timestamp_ns": ts,
        }
        record_caid = "sha256:" + hashlib.sha256(encode_jcs(body)).hexdigest()

        rec = MemoryRecord(
            record_id=record_id,
            agent_id=agent_id,
            content=content,
            memory_type=memory_type,
            prev_record_caid=self._last_caid,
            timestamp_ns=ts,
            record_caid=record_caid,
        )
        self.records.append(rec)
        self._last_caid = record_caid
        return True, "COMMITTED_CLEAN_MEMORY", rec

    def verify_chain(self) -> Tuple[bool, str, int]:
        """
        Verifies cryptographic integrity and Merkle hash linkage of all records.
        Returns (valid, status_code, verified_count).
        """
        expected_prev = "GENESIS"
        for idx, rec in enumerate(self.records):
            if rec.prev_record_caid != expected_prev:
                return False, f"ERR_CHAIN_LINKAGE_BROKEN: Record {idx} prev != {expected_prev}", idx

            body = {
                "record_id": rec.record_id,
                "agent_id": rec.agent_id,
                "content": rec.content,
                "memory_type": rec.memory_type,
                "prev_record_caid": rec.prev_record_caid,
                "timestamp_ns": rec.timestamp_ns,
            }
            expected_caid = "sha256:" + hashlib.sha256(encode_jcs(body)).hexdigest()
            if rec.record_caid != expected_caid:
                return False, f"ERR_RECORD_CAID_TAMPERED: Record {idx} caid mismatch", idx

            expected_prev = rec.record_caid

        return True, "VERIFIED_MEMORY_CHAIN", len(self.records)
