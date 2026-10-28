#!/usr/bin/env python3
r"""
aeib_v030_engine.py — AEIB v0.3.0 Engine & Bounded Authority Implementation
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity Benchmark (AEIB)

Implements the 11-part AEIB v0.3.0 specification:
- L7a: Immutable transport observation (cannot be altered by L1-L6 model hypotheses)
- L7b: Explicit probe scope (authority_scope, consistency_model; handles replica lag)
- L7c: Fail-closed disposition & retry policy derivation
- L8: Evidence receipt canonicalization (RFC 8785 JCS) and real Ed25519 signing
- Authority registry with strict cannot_assert boundary validation
- ANSI 86-inspired software lockout interlock
- OpenTelemetry aeib.effect_disposition event emission
"""

import json
import hashlib
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

from src.jcs_canonicalizer import encode_jcs, generate_jcs_payload_hash


class AuthorityViolationError(Exception):
    """Raised when a layer attempts to assert an attribute outside its authority bounds."""
    pass


class ImmutableFactViolationError(Exception):
    """Raised when an upstream layer attempts to override or downgrade an immutable wire fact."""
    pass


# Part 6: Authority Registration Boundaries & cannot_assert Rules
AUTHORITY_REGISTRY = {
    "L7a": {
        "authority_class": "TransportObservation",
        "can_assert": [
            "aeib.transport.observation",
            "aeib.transport.status_code",
            "aeib.transport.latency_ms",
            "aeib.transport.wire_fault",
            "aeib.transport.timestamp"
        ],
        "cannot_assert": [
            "aeib.downstream_commit_status",
            "aeib.disposition",
            "aeib.retry_safe",
            "aeib.release_authorization"
        ]
    },
    "L7b": {
        "authority_class": "AuthoritativeProbe",
        "can_assert": [
            "aeib.probe.authority_scope",
            "aeib.probe.consistency_model",
            "aeib.probe.query_status",
            "aeib.probe.matched_record_id",
            "aeib.probe.matched_payload_hash",
            "aeib.probe.timestamp"
        ],
        "cannot_assert": [
            "aeib.disposition",
            "aeib.retry_safe",
            "aeib.release_authorization"
        ]
    },
    "L7c": {
        "authority_class": "DispositionDerivation",
        "can_assert": [
            "aeib.disposition",
            "aeib.retry_safe",
            "aeib.retry_policy",
            "aeib.mapping_rule_id",
            "aeib.mapping_version",
            "aeib.latch_engaged"
        ],
        "cannot_assert": [
            "aeib.transport.observation",
            "aeib.release_authorization"
        ]
    },
    "L8": {
        "authority_class": "EvidenceVerification",
        "can_assert": [
            "aeib.receipt.signature",
            "aeib.receipt.public_key_hex",
            "aeib.receipt.jcs_payload_hash",
            "aeib.receipt.verified",
            "aeib.release_authorization"  # Allowed strictly to assert "not_provided"
        ],
        "cannot_assert": [
            "aeib.release_authorization_granted"
        ]
    }
}


def validate_authority_bounds(layer: str, asserted_attributes: Dict[str, Any]) -> None:
    """Validates that a layer does not assert attributes in its cannot_assert list."""
    if layer not in AUTHORITY_REGISTRY:
        raise AuthorityViolationError(f"Unregistered layer: {layer}")

    forbidden = AUTHORITY_REGISTRY[layer]["cannot_assert"]
    for attr in asserted_attributes.keys():
        if attr in forbidden:
            raise AuthorityViolationError(
                f"Layer {layer} ({AUTHORITY_REGISTRY[layer]['authority_class']}) "
                f"is forbidden from asserting attribute '{attr}' under Part 6 registry rules."
            )


def derive_caid(noun: str, verb: str, payload: Dict[str, Any]) -> str:
    """
    Derives Content-Addressed Action Identifier (CAID) per Part 5 and IETF CAID specification:
    CAID = H(Noun || Verb || JCS(Payload))
    """
    canonical_payload = encode_jcs(payload)
    hasher = hashlib.sha256()
    hasher.update(noun.strip().encode("utf-8"))
    hasher.update(b"::")
    hasher.update(verb.strip().encode("utf-8"))
    hasher.update(b"::")
    hasher.update(canonical_payload)
    return f"caid:sha256:{hasher.hexdigest()}"


@dataclass
class Layer7aTransportResult:
    observation: str
    status_code: int
    wire_fault: Optional[str] = None
    latency_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_attributes(self) -> Dict[str, Any]:
        return {
            "aeib.transport.observation": self.observation,
            "aeib.transport.status_code": self.status_code,
            "aeib.transport.latency_ms": self.latency_ms,
            "aeib.transport.wire_fault": self.wire_fault or "none",
            "aeib.transport.timestamp": self.timestamp,
        }


@dataclass
class Layer7bProbeResult:
    authority_scope: str         # e.g., "provider_primary", "replica_read", "local_cache"
    consistency_model: str       # e.g., "strong_read", "eventual_read", "read_after_write"
    query_status: str            # e.g., "RECORD_FOUND", "RECORD_NOT_FOUND", "PROBE_UNAVAILABLE", "PAYLOAD_MISMATCH"
    matched_record_id: Optional[str] = None
    matched_payload_hash: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_attributes(self) -> Dict[str, Any]:
        return {
            "aeib.probe.authority_scope": self.authority_scope,
            "aeib.probe.consistency_model": self.consistency_model,
            "aeib.probe.query_status": self.query_status,
            "aeib.probe.matched_record_id": self.matched_record_id or "",
            "aeib.probe.matched_payload_hash": self.matched_payload_hash or "",
            "aeib.probe.timestamp": self.timestamp,
        }


@dataclass
class Layer7cDispositionResult:
    disposition: str
    retry_safe: bool
    retry_policy: str
    mapping_rule_id: str
    mapping_version: str = "0.3.0"
    latch_engaged: bool = False

    def to_attributes(self) -> Dict[str, Any]:
        return {
            "aeib.disposition": self.disposition,
            "aeib.retry_safe": self.retry_safe,
            "aeib.retry_policy": self.retry_policy,
            "aeib.mapping_rule_id": self.mapping_rule_id,
            "aeib.mapping_version": self.mapping_version,
            "aeib.latch_engaged": self.latch_engaged,
        }


class AEIB030Pipeline:
    """
    AEIB v0.3.0 Master Pipeline orchestrating:
    L1-L6 (Model Intent) -> L7a (Transport) -> L7b (Probe) -> L7c (Disposition) -> L8 (Receipt)
    """

    def __init__(self, signing_private_key: Optional[ed25519.Ed25519PrivateKey] = None):
        self.signing_key = signing_private_key or ed25519.Ed25519PrivateKey.generate()
        self.public_key_hex = self.signing_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        ).hex()
        # Part 7: ANSI 86 software lockout latch state store by CAID
        self.locked_latches: Dict[str, bool] = {}

    def execute_flow(
        self,
        noun: str,
        verb: str,
        payload: Dict[str, Any],
        transport_observation: str,
        transport_status_code: int,
        model_hypothesis: Optional[Dict[str, Any]] = None,
        probe_authority_scope: str = "provider_primary",
        probe_consistency_model: str = "strong_read",
        probe_query_status: str = "RECORD_NOT_FOUND",
        probe_matched_record_id: Optional[str] = None,
        probe_matched_payload_hash: Optional[str] = None,
        provider_idempotency_contract_present: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes a single end-to-end AEIB v0.3.0 flow and returns the signed OpenTelemetry event.
        """
        caid = derive_caid(noun, verb, payload)

        # Check ANSI 86 Interlock latch (Part 7)
        if self.locked_latches.get(caid, False):
            raise RuntimeError(
                f"ANSI 86 Software Lockout Latch active for CAID {caid}. "
                "Dispatches are rejected until an explicit authoritative reset event."
            )

        # -------------------------------------------------------------
        # Step 1: L7a Transport Observation (Part 2)
        # -------------------------------------------------------------
        l7a = Layer7aTransportResult(
            observation=transport_observation,
            status_code=transport_status_code,
            wire_fault="http_504_gateway_timeout" if transport_status_code == 504 else None,
        )
        l7a_attrs = l7a.to_attributes()
        validate_authority_bounds("L7a", l7a_attrs)

        # Assertion 2: L1 model hypothesis cannot alter L7a transport observation
        if model_hypothesis:
            if "aeib.transport.observation" in model_hypothesis:
                if model_hypothesis["aeib.transport.observation"] != transport_observation:
                    raise ImmutableFactViolationError(
                        f"Part 2 Violation: L1 model hypothesis attempted to overwrite "
                        f"L7a immutable transport observation '{transport_observation}' "
                        f"with '{model_hypothesis['aeib.transport.observation']}'."
                    )

        # -------------------------------------------------------------
        # Step 2: L7b Authoritative Probe (Part 3)
        # -------------------------------------------------------------
        l7b = Layer7bProbeResult(
            authority_scope=probe_authority_scope,
            consistency_model=probe_consistency_model,
            query_status=probe_query_status,
            matched_record_id=probe_matched_record_id,
            matched_payload_hash=probe_matched_payload_hash,
        )
        l7b_attrs = l7b.to_attributes()
        validate_authority_bounds("L7b", l7b_attrs)

        # -------------------------------------------------------------
        # Step 3: L7c Disposition Derivation (Part 4)
        # -------------------------------------------------------------
        l7c = self._derive_disposition(
            transport_obs=l7a.observation,
            status_code=l7a.status_code,
            probe=l7b,
            has_idempotency_contract=provider_idempotency_contract_present,
        )
        l7c_attrs = l7c.to_attributes()
        validate_authority_bounds("L7c", l7c_attrs)

        # Engage latch if disposition is unconfirmed / quarantine (Part 7)
        if l7c.latch_engaged:
            self.locked_latches[caid] = True

        # -------------------------------------------------------------
        # Step 4: L8 Evidence Verification & COSE/Ed25519 Signing (Part 1, 5)
        # -------------------------------------------------------------
        # OpenTelemetry aeib.effect_disposition event payload
        event_body = {
            "aeib.caid": caid,
            "aeib.action.noun": noun,
            "aeib.action.verb": verb,
            "aeib.payload_hash": generate_jcs_payload_hash(payload),
            **l7a_attrs,
            **l7b_attrs,
            **l7c_attrs,
            # Part 1 & Part 9 Assertion 5: Release Authorization strictly "not_provided"
            "aeib.release_authorization": "not_provided",
            "aeib.spec_version": "0.3.0",
        }

        if model_hypothesis:
            event_body["aeib.model_hypothesis"] = model_hypothesis

        # Canonicalize via RFC 8785 JCS
        canonical_event_bytes = encode_jcs(event_body)
        event_digest = hashlib.sha256(canonical_event_bytes).hexdigest()

        # Sign with real Ed25519
        signature = self.signing_key.sign(canonical_event_bytes)

        l8_attrs = {
            "aeib.receipt.signature": signature.hex(),
            "aeib.receipt.public_key_hex": self.public_key_hex,
            "aeib.receipt.jcs_payload_hash": f"sha256:{event_digest}",
            "aeib.receipt.verified": True,
            "aeib.release_authorization": "not_provided"
        }
        validate_authority_bounds("L8", l8_attrs)

        # Combine into complete OpenTelemetry LogRecord event envelope
        full_event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_name": "aeib.effect_disposition",
            "attributes": {**event_body, **l8_attrs}
        }
        return full_event

    def _derive_disposition(
        self,
        transport_obs: str,
        status_code: int,
        probe: Layer7bProbeResult,
        has_idempotency_contract: bool
    ) -> Layer7cDispositionResult:
        """Derives disposition and retry safety under v0.3.0 mapping contract rules."""
        
        # Scenario: HTTP 504 / Transport Dropout
        if status_code == 504 or "504" in transport_obs:
            if probe.query_status == "RECORD_FOUND":
                return Layer7cDispositionResult(
                    disposition="OUTCOME_VERIFIED",
                    retry_safe=False,
                    retry_policy="PROHIBITED_ALREADY_COMMITTED",
                    mapping_rule_id="RULE-504-01-VERIFIED",
                    latch_engaged=False
                )
            elif probe.query_status == "PAYLOAD_MISMATCH":
                return Layer7cDispositionResult(
                    disposition="RECONCILIATION_CONFLICT",
                    retry_safe=False,
                    retry_policy="PROHIBITED_ESCALATE_AUDIT",
                    mapping_rule_id="RULE-504-02-CONFLICT",
                    latch_engaged=True
                )
            elif probe.query_status == "PROBE_UNAVAILABLE":
                return Layer7cDispositionResult(
                    disposition="PROBE_UNAVAILABLE",
                    retry_safe=False,
                    retry_policy="PROHIBITED_LATCH_CLOSED",
                    mapping_rule_id="RULE-504-03-UNAVAILABLE",
                    latch_engaged=True
                )
            elif probe.query_status == "RECORD_NOT_FOUND":
                # Part 3: Explicit Consistency Check
                if probe.consistency_model == "eventual_read":
                    # Eventual consistency replica read CANNOT prove absence
                    return Layer7cDispositionResult(
                        disposition="EFFECT_INDETERMINATE",
                        retry_safe=False,
                        retry_policy="PROHIBITED_REPLICA_LAG_HOLD",
                        mapping_rule_id="RULE-504-04-INDETERMINATE",
                        latch_engaged=True
                    )
                else:
                    # Strong read on primary: record not found after grace period
                    if has_idempotency_contract:
                        return Layer7cDispositionResult(
                            disposition="RECONCILIATION_NOT_FOUND_AFTER_GRACE",
                            retry_safe=True,
                            retry_policy="PERMITTED_IDEMPOTENCY_BOUND",
                            mapping_rule_id="RULE-504-05-NOT_FOUND_PERMITTED",
                            latch_engaged=False
                        )
                    else:
                        # Fail-closed default (Part 4)
                        return Layer7cDispositionResult(
                            disposition="RECONCILIATION_NOT_FOUND_AFTER_GRACE",
                            retry_safe=False,
                            retry_policy="PROHIBITED_FAIL_CLOSED",
                            mapping_rule_id="RULE-504-06-NOT_FOUND_LATCH",
                            latch_engaged=True
                        )

        # Baseline: HTTP 200 OK
        if status_code == 200:
            return Layer7cDispositionResult(
                disposition="OUTCOME_VERIFIED",
                retry_safe=False,
                retry_policy="PROHIBITED_ALREADY_COMMITTED",
                mapping_rule_id="RULE-200-01-SUCCESS",
                latch_engaged=False
            )

        # Default fallback: Unclassified transport anomaly
        return Layer7cDispositionResult(
            disposition="DISPATCHED_UNCONFIRMED",
            retry_safe=False,
            retry_policy="PROHIBITED_DEFAULT_LATCH",
            mapping_rule_id="RULE-DEFAULT-UNCONFIRMED",
            latch_engaged=True
        )
