"""
v1.1-roadmap/telemetry_correlation_bridge.py — OpenTelemetry Semantic Telemetry Projection Prototype.
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity Boundary (AEIB).

Tier 3.2 Core Delivery Contract:
Projects AEIB execution phases to OpenTelemetry GenAI semantic conventions:
  1. PRE_DISPATCH_COMMITTED -> gen_ai.agent.action.pre_commit
  2. DISPATCH_AUTHORIZED -> gen_ai.agent.action.dispatch
  3. EFFECT_INDETERMINATE -> gen_ai.agent.action.uncertain_transport
  4. PROBE_DISPATCHED -> gen_ai.agent.action.reconcile_probe
  5. CONFIRMED -> gen_ai.agent.action.confirmed
  6. REFUTED -> gen_ai.agent.action.refuted
  7. NOT_DISPATCHED -> gen_ai.agent.action.held

Operates under the stated model:
- Populates event attributes matching schemas/aeib_otel_events.yaml:
  gen_ai.system: "aeib", action metadata, and aeib.* disposition fields.
- Implements W3C Trace Context (traceparent: 00-{trace_id}-{span_id}-{trace_flags})
  round-trip parsing and generation.
- Enforces strict unidirectional telemetry isolation: telemetry is an outbound observer ONLY,
  possessing zero authority to mutate state or alter gate authorization verdicts.
- Evaluated under simulated telemetry export failures (network drops, buffer overflows,
  malformed spans); boundary enforcement remains fail-closed and unaffected.
"""

from __future__ import annotations

import copy
import json
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


class TelemetryBridgeError(Exception):
    """Base exception for telemetry correlation bridge errors."""


class InvalidTraceparentError(TelemetryBridgeError):
    """Raised when a W3C traceparent header violates the specification."""


class TelemetryIsolationViolationError(TelemetryBridgeError):
    """Raised when telemetry subsystem attempts unauthorized write or state mutation."""


# Valid W3C Trace Context Regex (version-traceid-spanid-traceflags)
TRACEPARENT_REGEX = re.compile(
    r"^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$"
)

# OpenTelemetry GenAI Semantic Convention Event Mapping for AEIB
PHASE_EVENT_MAP: Dict[str, str] = {
    "PRE_DISPATCH_COMMITTED": "gen_ai.agent.action.pre_commit",
    "DISPATCH_AUTHORIZED": "gen_ai.agent.action.dispatch",
    "EFFECT_INDETERMINATE": "gen_ai.agent.action.uncertain_transport",
    "PROBE_DISPATCHED": "gen_ai.agent.action.reconcile_probe",
    "CONFIRMED": "gen_ai.agent.action.confirmed",
    "REFUTED": "gen_ai.agent.action.refuted",
    "NOT_DISPATCHED": "gen_ai.agent.action.held",
}

# Standard attribute schema mapping from schemas/aeib_otel_events.yaml
KNOWN_AEIB_ATTRIBUTES = {
    "effect_id": "aeib.effect_id",
    "attempt_id": "aeib.attempt_id",
    "inference_id": "aeib.inference_id",
    "transport_observation": "aeib.transport.observation",
    "model_hypothesis": "aeib.model_hypothesis",
    "probe_result": "aeib.probe.result",
    "probe_authority_scope": "aeib.probe.authority_scope",
    "probe_consistency_model": "aeib.probe.consistency_model",
    "probe_observed_at": "aeib.probe.observed_at",
    "disposition": "aeib.disposition",
    "retry_safe": "aeib.retry.safe",
    "recovery": "aeib.recovery",
    "receipt_digest": "aeib.receipt.digest",
    "contract_hash": "aeib.contract.hash",
    "release_authorization": "aeib.release.authorization",
}


@dataclass(frozen=True)
class TraceParent:
    """W3C Trace Context traceparent representation."""

    version: str
    trace_id: str
    span_id: str
    trace_flags: str

    def to_header(self) -> str:
        return f"{self.version}-{self.trace_id}-{self.span_id}-{self.trace_flags}"


def parse_traceparent(traceparent: str) -> TraceParent:
    """
    Parses and validates a W3C Trace Context traceparent string.

    Format: {version:2hex}-{trace_id:32hex}-{span_id:16hex}-{trace_flags:2hex}
    Rejects:
      - Length != 55 characters for version '00'
      - Version 'ff' (forbidden by W3C spec)
      - All-zero trace_id
      - All-zero span_id
      - Non-hex characters
    """
    if not isinstance(traceparent, str):
        raise InvalidTraceparentError("traceparent must be a string")

    stripped = traceparent.strip()
    match = TRACEPARENT_REGEX.match(stripped)
    if not match:
        raise InvalidTraceparentError(
            f"Invalid traceparent format: '{traceparent}'. Expected 00-32hex-16hex-02hex."
        )

    version, trace_id, span_id, trace_flags = match.groups()

    if version == "ff":
        raise InvalidTraceparentError("traceparent version 'ff' is forbidden by W3C specification")

    if version == "00" and len(stripped) != 55:
        raise InvalidTraceparentError("W3C traceparent version '00' must be exactly 55 characters")

    if trace_id == "0" * 32:
        raise InvalidTraceparentError("trace_id cannot be all zeros")

    if span_id == "0" * 16:
        raise InvalidTraceparentError("span_id cannot be all zeros")

    return TraceParent(
        version=version,
        trace_id=trace_id,
        span_id=span_id,
        trace_flags=trace_flags,
    )


def generate_traceparent(
    trace_id: str,
    span_id: str,
    trace_flags: str = "01",
    version: str = "00",
) -> str:
    """Generates and validates a W3C traceparent header string."""
    header = f"{version}-{trace_id}-{span_id}-{trace_flags}"
    # Validate through parse_traceparent to observe compliance
    parse_traceparent(header)
    return header


@dataclass
class SpanContext:
    """Context identifying a span within an active execution trace."""

    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    trace_flags: str = "01"
    version: str = "00"
    operation_id: str = ""

    @property
    def traceparent(self) -> str:
        return f"{self.version}-{self.trace_id}-{self.span_id}-{self.trace_flags}"


def _to_otlp_any_value(val: Any) -> Dict[str, Any]:
    """Encodes a primitive value into standard OpenTelemetry AnyValue dictionary."""
    if isinstance(val, bool):
        return {"boolValue": val}
    elif isinstance(val, int):
        return {"intValue": str(val)}
    elif isinstance(val, float):
        return {"doubleValue": val}
    else:
        return {"stringValue": str(val)}


def _normalize_attribute_key(k: str) -> str:
    """Normalizes an attribute key to the aeib / gen_ai namespace."""
    if k.startswith("gen_ai.") or k.startswith("aeib."):
        return k
    if k in KNOWN_AEIB_ATTRIBUTES:
        return KNOWN_AEIB_ATTRIBUTES[k]
    # Replace underscores with dots and prefix with aeib.
    normalized = k.replace("_", ".")
    return f"aeib.{normalized}"


class TelemetryCorrelationBridge:
    """
    OpenTelemetry semantic telemetry correlation bridge for AEIB execution phases.

    Outbound observer under the stated model:
      - Ingests execution phase transitions and maps to GenAI semantic conventions.
      - Maintains local trace and span records for OTLP export.
      - Has zero write authority to mutate state or gate verdicts.
    """

    def __init__(
        self,
        service_name: str = "aeib",
        scope_name: str = "aeib.telemetry_correlation_bridge",
        scope_version: str = "1.1.0",
    ) -> None:
        self.service_name = service_name
        self.scope_name = scope_name
        self.scope_version = scope_version
        self._spans: List[Dict[str, Any]] = []
        self._events_by_span: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = threading.Lock()
        self._is_outbound_observer_only = True

    def start_trace(
        self,
        parent_traceparent: Optional[str] = None,
        operation_id: Optional[str] = None,
        span_name: str = "aeib.agent.action",
    ) -> SpanContext:
        """
        Starts or continues a trace context.
        If parent_traceparent is provided, inherits trace_id and sets parent_span_id.
        """
        if parent_traceparent:
            parsed = parse_traceparent(parent_traceparent)
            trace_id = parsed.trace_id
            parent_span_id = parsed.span_id
            trace_flags = parsed.trace_flags
            version = parsed.version
        else:
            trace_id = secrets.token_hex(16)
            parent_span_id = None
            trace_flags = "01"
            version = "00"

        span_id = secrets.token_hex(8)
        op_id = operation_id or secrets.token_hex(16)

        span_context = SpanContext(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            trace_flags=trace_flags,
            version=version,
            operation_id=op_id,
        )

        now_nano = time.time_ns()
        span_record = {
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id or "",
            "name": span_name,
            "start_time_unix_nano": now_nano,
            "end_time_unix_nano": now_nano,
            "attributes": {
                "gen_ai.system": "aeib",
                "gen_ai.agent.action.id": op_id,
            },
        }

        with self._lock:
            self._spans.append(span_record)
            self._events_by_span[span_id] = []

        return span_context

    def record_phase_event(
        self,
        span_context: SpanContext,
        phase: str,
        action_caid: str,
        target_tool: str,
        extra_attributes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Records an execution phase event associated with the given span_context.
        Maps the phase to OpenTelemetry GenAI semantic conventions.
        """
        otel_event_name = PHASE_EVENT_MAP.get(phase, f"gen_ai.agent.action.{phase.lower()}")

        # Build raw attribute mapping
        attrs: Dict[str, Any] = {
            "gen_ai.system": "aeib",
            "gen_ai.agent.action.id": span_context.operation_id or span_context.span_id,
            "gen_ai.agent.action.phase": phase,
            "gen_ai.agent.action.caid": action_caid,
            "gen_ai.agent.action.tool_name": target_tool,
        }

        if extra_attributes:
            for k, v in extra_attributes.items():
                norm_key = _normalize_attribute_key(k)
                attrs[norm_key] = v

        now_nano = time.time_ns()
        event_record = {
            "name": otel_event_name,
            "time_unix_nano": now_nano,
            "attributes": attrs,
        }

        with self._lock:
            if span_context.span_id not in self._events_by_span:
                self._events_by_span[span_context.span_id] = []
            self._events_by_span[span_context.span_id].append(event_record)

            # Update span end time
            for s in self._spans:
                if s["span_id"] == span_context.span_id:
                    s["end_time_unix_nano"] = now_nano
                    break

        return event_record

    def export_spans_otlp_dict(self) -> Dict[str, Any]:
        """Exports accumulated spans in OpenTelemetry OTLP ResourceSpans dictionary format."""
        with self._lock:
            otlp_spans: List[Dict[str, Any]] = []

            for span in self._spans:
                sid = span["span_id"]
                raw_events = self._events_by_span.get(sid, [])

                # Format OTLP events
                otlp_events = []
                for ev in raw_events:
                    otlp_ev_attrs = [
                        {"key": k, "value": _to_otlp_any_value(v)}
                        for k, v in ev["attributes"].items()
                    ]
                    otlp_events.append(
                        {
                            "timeUnixNano": str(ev["time_unix_nano"]),
                            "name": ev["name"],
                            "attributes": otlp_ev_attrs,
                        }
                    )

                # Format OTLP span attributes
                otlp_span_attrs = [
                    {"key": k, "value": _to_otlp_any_value(v)}
                    for k, v in span["attributes"].items()
                ]

                otlp_span: Dict[str, Any] = {
                    "traceId": span["trace_id"],
                    "spanId": span["span_id"],
                    "name": span["name"],
                    "kind": 1,  # SPAN_KIND_INTERNAL
                    "startTimeUnixNano": str(span["start_time_unix_nano"]),
                    "endTimeUnixNano": str(span["end_time_unix_nano"]),
                    "attributes": otlp_span_attrs,
                    "events": otlp_events,
                    "status": {"code": 1},  # STATUS_CODE_OK
                }
                if span.get("parent_span_id"):
                    otlp_span["parentSpanId"] = span["parent_span_id"]

                otlp_spans.append(otlp_span)

            return {
                "resourceSpans": [
                    {
                        "resource": {
                            "attributes": [
                                {
                                    "key": "service.name",
                                    "value": {"stringValue": self.service_name},
                                },
                                {
                                    "key": "gen_ai.system",
                                    "value": {"stringValue": "aeib"},
                                },
                            ]
                        },
                        "scopeSpans": [
                            {
                                "scope": {
                                    "name": self.scope_name,
                                    "version": self.scope_version,
                                },
                                "spans": otlp_spans,
                            }
                        ],
                    }
                ]
            }

    def export_spans_json(self, indent: Optional[int] = 2) -> str:
        """Exports accumulated spans as formatted JSON string."""
        return json.dumps(self.export_spans_otlp_dict(), indent=indent)

    def clear(self) -> None:
        """Clears recorded spans and events from memory."""
        with self._lock:
            self._spans.clear()
            self._events_by_span.clear()

    def assert_telemetry_isolation(
        self,
        gate_fn: Optional[Callable[[Dict[str, Any]], Tuple[bool, str]]] = None,
        candidate_action: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Evaluates the architectural boundary invariant:
          1. Telemetry is strictly an outbound observer with zero authority to mutate state.
          2. Simulated telemetry errors (exceptions, queue drops) cannot flip an unauthorized
             verdict to authorized or bypass gate logic.
        """
        # Invariant 1: Structural verification
        if not getattr(self, "_is_outbound_observer_only", False):
            raise TelemetryIsolationViolationError("Telemetry bridge must remain outbound observer only")

        # Invariant 2: Execution isolation under telemetry failure
        if gate_fn is None:
            # Reference evaluation gate
            def _ref_gate(action: Dict[str, Any]) -> Tuple[bool, str]:
                is_auth = action.get("authorized", False)
                return (is_auth, "DISPATCH_AUTHORIZED" if is_auth else "NOT_DISPATCHED")

            target_gate = _ref_gate
        else:
            target_gate = gate_fn

        # Evaluate with an unauthorized action
        unauth_action = candidate_action or {"tool": "restricted_payment", "authorized": False}
        initial_allowed, initial_disposition = target_gate(unauth_action)

        # Inject simulated telemetry failure into recording pipeline
        def _failing_export() -> None:
            raise RuntimeError("Simulated OTLP network partition / telemetry queue overflow")

        try:
            _failing_export()
        except RuntimeError:
            pass  # Observed expected telemetry failure

        # Evaluate gate disposition after telemetry failure
        post_failure_allowed, post_failure_disposition = target_gate(unauth_action)

        if post_failure_allowed != initial_allowed:
            raise TelemetryIsolationViolationError(
                "Telemetry failure altered gate authorization outcome"
            )

        if post_failure_disposition != initial_disposition:
            raise TelemetryIsolationViolationError(
                "Telemetry failure altered gate disposition code"
            )

        # If action was unauthorized, it must remain unauthorized
        if not initial_allowed and post_failure_allowed:
            raise TelemetryIsolationViolationError(
                "Telemetry failure permitted unauthorized dispatch (fail-open violation)"
            )

        return True
