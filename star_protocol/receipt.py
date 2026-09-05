#!/usr/bin/env python3
"""
Receipt dataclass for STAR protocol.
Encodes cryptographic proofs, compliance metadata, and execution traces
for immutable audit trails.

Fields (16 total):
  - 10 core execution fields (story, status, merkle proofs, signatures)
  - 5 EU compliance fields (retention, access logs, authorization, environment, replay)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime


@dataclass
class Receipt:
    """Immutable cryptographic receipt for STAR test execution."""

    # Core execution fields
    receipt_id: str
    story_id: str
    status: str
    verdict: str
    steps_total: int
    steps_passed: int
    merkle_root: str
    signature: str
    spans: List[Dict[str, Any]]
    timestamp: str

    # EU compliance fields (Annex IV)
    retention_days: int = 2555  # ~7 years, GDPR retention minimum for financial audit
    access_log: List[Dict[str, Any]] = field(default_factory=list)  # Who accessed this receipt
    human_override: Dict[str, Any] = field(default_factory=dict)  # {invoked: bool, reason: str, approver: str}
    environment_snapshot: Dict[str, Any] = field(default_factory=dict)  # {os, python_version, star_version, model}
    replay_instructions: str = ""  # Instructions to deterministically replay this test
    schema_version: str = "1.0"  # Receipt schema version for forward compatibility

    def __post_init__(self):
        """Validate receipt after initialization."""
        if not self.receipt_id:
            raise ValueError("receipt_id cannot be empty")
        if not self.merkle_root:
            raise ValueError("merkle_root cannot be empty")
        if not self.signature:
            raise ValueError("signature cannot be empty")

    def add_access_log_entry(self, user: str, action: str, timestamp: Optional[str] = None) -> None:
        """Add access log entry for audit trail."""
        if timestamp is None:
            timestamp = datetime.utcnow().isoformat()
        self.access_log.append({
            "user": user,
            "action": action,
            "timestamp": timestamp
        })

    def to_dict(self) -> Dict[str, Any]:
        """Convert receipt to dict for JSON serialization."""
        return {
            "receipt_id": self.receipt_id,
            "story_id": self.story_id,
            "status": self.status,
            "verdict": self.verdict,
            "steps_total": self.steps_total,
            "steps_passed": self.steps_passed,
            "merkle_root": self.merkle_root,
            "signature": self.signature,
            "spans": self.spans,
            "timestamp": self.timestamp,
            "retention_days": self.retention_days,
            "access_log": self.access_log,
            "human_override": self.human_override,
            "environment_snapshot": self.environment_snapshot,
            "replay_instructions": self.replay_instructions,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Receipt":
        """Create receipt from dict."""
        return cls(
            receipt_id=data.get("receipt_id", ""),
            story_id=data.get("story_id", ""),
            status=data.get("status", ""),
            verdict=data.get("verdict", ""),
            steps_total=data.get("steps_total", 0),
            steps_passed=data.get("steps_passed", 0),
            merkle_root=data.get("merkle_root", ""),
            signature=data.get("signature", ""),
            spans=data.get("spans", []),
            timestamp=data.get("timestamp", ""),
            retention_days=data.get("retention_days", 2555),
            access_log=data.get("access_log", []),
            human_override=data.get("human_override", {}),
            environment_snapshot=data.get("environment_snapshot", {}),
            replay_instructions=data.get("replay_instructions", ""),
            schema_version=data.get("schema_version", "1.0"),
        )
