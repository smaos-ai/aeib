"""
Hierarchical Merkle-Tree Trace Collector
For sovereign AI governance distributed tracing with cryptographic proofs.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any, Callable
import hashlib
import json
import time
import uuid
import asyncio


class SpanStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    FAILED = "failed"
    HALTED = "halted"
    WAITING_HUMAN = "waiting_human"


class SpanType(str, Enum):
    SYSTEM_ORCHESTRATION = "system_orchestration"
    POLICY_CLASSIFICATION = "policy_classification"
    VERIFICATION = "verification"
    IDENTITY_ATTESTATION = "identity_attestation"
    DELEGATION_CHECK = "delegation_check"
    SANDBOX_SIMULATION = "sandbox_simulation"
    VETO_GATE_INTERVENTION = "veto_gate_intervention"
    CRYPTOGRAPHIC_SIGNING = "cryptographic_signing"
    LEDGER_COMMIT = "ledger_commit"


@dataclass
class TraceSpan:
    """A single step in the execution flow."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    sequence: int
    span_type: SpanType
    name: str
    status: SpanStatus
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    payload: dict = field(default_factory=dict)
    merkle_root: Optional[str] = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    child_span_ids: list = field(default_factory=list)

    def complete(self, status: SpanStatus = SpanStatus.COMPLETE):
        """Mark span as complete and compute merkle root."""
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        self.status = status
        self._compute_merkle()

    def fail(self, error: str):
        """Mark span as failed."""
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        self.status = SpanStatus.FAILED
        self.error = error
        self._compute_merkle()

    def _compute_merkle(self):
        """Compute cryptographic hash of this span."""
        content = json.dumps({
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "type": self.span_type.value,
            "status": self.status.value,
            "payload": self.payload,
            "start": self.start_time,
            "end": self.end_time,
        }, sort_keys=True)
        self.merkle_root = hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> dict:
        """Convert to serializable dict."""
        d = asdict(self)
        d["span_type"] = self.span_type.value
        d["status"] = self.status.value
        return d


@dataclass
class FlowTrace:
    """Complete trace for one request through the governance pipeline."""
    trace_id: str
    created_at: float
    spans: dict[str, TraceSpan] = field(default_factory=dict)  # span_id -> TraceSpan
    root_span_id: Optional[str] = None
    status: SpanStatus = SpanStatus.ACTIVE
    total_duration_ms: Optional[float] = None

    def add_span(
        self,
        span_type: SpanType,
        name: str,
        payload: dict = None,
        parent_span_id: Optional[str] = None,
    ) -> TraceSpan:
        """Add a new span to the trace."""
        span = TraceSpan(
            trace_id=self.trace_id,
            span_id=str(uuid.uuid4())[:8],
            parent_span_id=parent_span_id or self.root_span_id,
            sequence=len(self.spans),
            span_type=span_type,
            name=name,
            status=SpanStatus.ACTIVE,
            start_time=time.time(),
            payload=payload or {},
        )
        self.spans[span.span_id] = span

        # Register this span as a child of its parent
        if span.parent_span_id and span.parent_span_id in self.spans:
            self.spans[span.parent_span_id].child_span_ids.append(span.span_id)

        # If this is the first span, mark it as root
        if not self.root_span_id:
            self.root_span_id = span.span_id

        return span

    def complete(self):
        """Mark trace as complete and compute total duration."""
        self.status = SpanStatus.COMPLETE
        if self.spans:
            all_spans = list(self.spans.values())
            start = min(s.start_time for s in all_spans)
            end = max(s.end_time or s.start_time for s in all_spans)
            self.total_duration_ms = round((end - start) * 1000, 2)

    def merkle_root(self) -> str:
        """Compute merkle root of entire trace tree."""
        if not self.root_span_id or self.root_span_id not in self.spans:
            return "no_root"
        root_span = self.spans[self.root_span_id]
        return self._compute_subtree_merkle(root_span)

    def _compute_subtree_merkle(self, span: TraceSpan) -> str:
        """Recursively compute merkle root for a span and its children."""
        # Get this span's merkle
        span_merkle = span.merkle_root or ""

        # Get children's merkles
        child_merkles = []
        for child_id in span.child_span_ids:
            if child_id in self.spans:
                child_merkle = self._compute_subtree_merkle(self.spans[child_id])
                child_merkles.append(child_merkle)

        # Combine: span merkle + all children
        combined = ":".join([span_merkle] + sorted(child_merkles))
        return hashlib.sha256(combined.encode()).hexdigest()

    def to_dict(self) -> dict:
        """Convert to serializable dict."""
        return {
            "trace_id": self.trace_id,
            "status": self.status.value,
            "total_duration_ms": self.total_duration_ms,
            "span_count": len(self.spans),
            "merkle_root": self.merkle_root(),
            "spans": {k: v.to_dict() for k, v in self.spans.items()},
        }


class TraceCollector:
    """Central collector for all execution traces."""

    def __init__(self):
        self.traces: dict[str, FlowTrace] = {}
        self._subscribers: list[Callable] = []
        self._lock = asyncio.Lock()

    def start_trace(self, intent: dict) -> FlowTrace:
        """Start a new trace for a governance request."""
        trace_id = str(uuid.uuid4())[:12]
        trace = FlowTrace(trace_id=trace_id, created_at=time.time())
        self.traces[trace_id] = trace

        # Create root span
        root_span = trace.add_span(
            SpanType.SYSTEM_ORCHESTRATION,
            "Sovereign Execution Pipeline",
            payload={
                "intent_query": str(intent.get("query", ""))[:200],
                "session_id": str(intent.get("session_id", ""))[:12],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        root_span.complete()
        self._emit(trace_id, root_span)
        return trace

    def add_classification_span(
        self, trace: FlowTrace, rules: list, confidence: float
    ) -> TraceSpan:
        """Add policy classification span."""
        span = trace.add_span(
            SpanType.POLICY_CLASSIFICATION,
            "Policy Classification",
            payload={
                "matched_rules": rules[:5],  # First 5 only
                "confidence": round(confidence, 3),
                "primary_category": rules[0] if rules else "unknown",
            },
        )
        span.complete()
        self._emit(trace.trace_id, span)
        return span

    def add_veto_gate_span(
        self,
        trace: FlowTrace,
        blast_radius: float,
        threshold: float,
        decision: str,
    ) -> TraceSpan:
        """Add veto gate (Layer 7) span."""
        span = trace.add_span(
            SpanType.VETO_GATE_INTERVENTION,
            "Layer 7: Veto Gate Check",
            payload={
                "blast_radius": round(blast_radius, 3),
                "threshold": round(threshold, 3),
                "decision": decision,
                "cet1_ratio": "11.2%",
                "projected_ratio": "10.18%",
            },
        )
        if decision == "HALT":
            span.complete(SpanStatus.HALTED)
        elif decision == "HUMAN_GATE":
            span.status = SpanStatus.WAITING_HUMAN
            span.end_time = time.time()
            span.duration_ms = round((span.end_time - span.start_time) * 1000, 2)
            span._compute_merkle()
        else:
            span.complete()
        self._emit(trace.trace_id, span)
        return span

    def add_authorization_span(
        self, trace: FlowTrace, endpoint: str, method: str, signature: str
    ) -> TraceSpan:
        """Add authorization span."""
        span = trace.add_span(
            SpanType.CRYPTOGRAPHIC_SIGNING,
            "Authorization: Ed25519 Signature",
            payload={
                "endpoint": endpoint,
                "method": method,
                "signature_algorithm": "Ed25519",
                "signature_preview": signature[:32] + "...",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        span.complete()
        self._emit(trace.trace_id, span)
        return span

    def add_execution_span(
        self, trace: FlowTrace, layers: list, exit_code: int, output: str
    ) -> TraceSpan:
        """Add execution span (Layers 0-12)."""
        span = trace.add_span(
            SpanType.SANDBOX_SIMULATION,
            "Execution: 12-Layer Verification",
            payload={
                "layers_executed": len(layers),
                "layers": layers,
                "exit_code": exit_code,
                "output_preview": output[:200],
            },
        )
        if exit_code == 0:
            span.complete()
        else:
            span.fail(f"Exit code {exit_code}")
        self._emit(trace.trace_id, span)
        return span

    def add_receipt_span(
        self, trace: FlowTrace, receipt_id: str, merkle_root: str
    ) -> TraceSpan:
        """Add receipt persistence span."""
        span = trace.add_span(
            SpanType.LEDGER_COMMIT,
            "Receipt Persisted to Ledger",
            payload={
                "receipt_id": receipt_id,
                "merkle_root": merkle_root[:32] + "...",
                "ledger_location": "/tmp/agentacct.db",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        span.complete()
        trace.complete()
        self._emit(trace.trace_id, span)
        return span

    def _emit(self, trace_id: str, span: TraceSpan):
        """Emit trace event to all subscribers."""
        event = {
            "trace_id": trace_id,
            "span": span.to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for callback in self._subscribers:
            try:
                callback(event)
            except Exception as e:
                print(f"Subscriber error: {e}")

    def subscribe(self, callback: Callable):
        """Subscribe to trace events."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable):
        """Unsubscribe from trace events."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def get_trace(self, trace_id: str) -> Optional[dict]:
        """Get full trace by ID."""
        trace = self.traces.get(trace_id)
        return trace.to_dict() if trace else None

    def get_recent_traces(self, limit: int = 20) -> list:
        """Get recent traces."""
        sorted_traces = sorted(
            self.traces.values(), key=lambda t: t.created_at, reverse=True
        )[:limit]
        return [
            {
                "trace_id": t.trace_id,
                "status": t.status.value,
                "span_count": len(t.spans),
                "total_duration_ms": t.total_duration_ms,
                "created_at": t.created_at,
                "merkle_root": t.merkle_root()[:16] + "...",
            }
            for t in sorted_traces
        ]


# Global collector instance
collector = TraceCollector()
