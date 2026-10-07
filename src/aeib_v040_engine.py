#!/usr/bin/env python3
r"""
aeib_v040_engine.py — AEIB v0.4.0 Engine & Bounded Authority Implementation
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity Benchmark (AEIB)

Implements the AEIB v0.4.0 specification:
- L7a: Immutable transport observation (cannot be altered by L1-L6 model hypotheses)
- L7b: Explicit probe scope (authority_scope, consistency_model; handles replica lag)
- L7c: Fail-closed disposition & retry policy derivation
- L8: Evidence receipt canonicalization (RFC 8785 JCS) and dynamic Ed25519 verification
- Offline Tycho structural state verification (fail-closed gate):
  an absent / un-evaluated YAML contract halts execution with
  STRUCTURAL_VERIFICATION_FAILED before any receipt is signed (no fail-open path)
- Authority registry with strict cannot_assert boundary validation
- ANSI 86-inspired software lockout interlock
- OpenTelemetry aeib.effect_disposition event emission
"""

import os
import stat
import hashlib
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

from src.jcs_canonicalizer import encode_jcs, generate_jcs_payload_hash


class AuthorityViolationError(Exception):
    """Raised when a layer attempts to assert an attribute outside its authority bounds."""
    pass


class ImmutableFactViolationError(Exception):
    """Raised when an upstream layer attempts to override or downgrade an immutable wire fact."""
    pass


class StructuralVerificationError(Exception):
    """
    Raised when the Tycho structural gate halts execution (fail-closed).

    Emitted when the structural verdict is absent or the YAML contract was never
    evaluated. The ANSI 86 latch for the CAID is engaged *before* this error is
    raised, so the halted action cannot be re-dispatched.
    """

    disposition = "STRUCTURAL_VERIFICATION_FAILED"

    def __init__(self, detail: str):
        super().__init__(f"{self.disposition}: {detail}")


# Verdicts that represent an *evaluated* Tycho YAML contract.
# Anything outside this set (None, empty, non-string, un-evaluated contract
# objects) is treated as un-evaluated and halts execution fail-closed.
EVALUATED_TYCHO_VERDICTS = frozenset({
    "VERIFIED",
    "FAILED",
    "STALE",
    "INDETERMINATE",
    "ERROR",
})


# Authority Registration Boundaries & cannot_assert Rules
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
    for attr, val in asserted_attributes.items():
        if attr in forbidden:
            raise AuthorityViolationError(
                f"Layer {layer} ({AUTHORITY_REGISTRY[layer]['authority_class']}) "
                f"is forbidden from asserting attribute '{attr}' under registry rules."
            )
        # Release authorization strict validation
        if attr == "aeib.release_authorization" and val != "not_provided":
            raise AuthorityViolationError(
                f"Layer {layer} asserted unauthorized release authorization: '{val}'. "
                "Must be strictly 'not_provided' without explicit multi-party quorum."
            )


def derive_caid(noun: str, verb: str, payload: Dict[str, Any]) -> str:
    """
    Derives Content-Addressed Action Identifier (CAID) per IETF CAID specification:
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
    authority_scope: str         # e.g., "provider_primary", "replica_read"
    consistency_model: str       # e.g., "strong_read", "eventual_read"
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
    mapping_version: str = "0.4.0"
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


class AEIB040Pipeline:
    """
    AEIB v0.4.0 Master Pipeline orchestrating:
    L1-L6 (Model Intent) -> L7a (Transport) -> L7b (Probe) -> L7c (Disposition) -> L8 (Receipt)
    """

    def __init__(
        self,
        signing_private_key: Optional[ed25519.Ed25519PrivateKey] = None,
        key_path: Optional[str] = None,
        enforce_tycho: bool = True
    ):
        if not enforce_tycho:
            # Fail-closed: the structural gate has no bypass switch under v0.4.0.
            raise ValueError(
                "enforce_tycho=False is not permitted under AEIB v0.4.0: the Tycho "
                "structural gate is mandatory and has no fail-open fallback path."
            )
        self.enforce_tycho = enforce_tycho
        self.signing_key = self._resolve_signing_key(signing_private_key, key_path)
        self.public_key_hex = self.signing_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        ).hex()
        # ANSI 86 software lockout latch state store by CAID
        self.locked_latches: Dict[str, bool] = {}

    def _resolve_signing_key(
        self,
        explicit_key: Optional[ed25519.Ed25519PrivateKey],
        key_path: Optional[str]
    ) -> ed25519.Ed25519PrivateKey:
        if explicit_key:
            return explicit_key

        if key_path and os.path.exists(key_path):
            with open(key_path, "rb") as f:
                return serialization.load_pem_private_key(f.read(), password=None)

        key = ed25519.Ed25519PrivateKey.generate()
        if key_path:
            pem = key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            # Write with restricted permissions (0600)
            fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
            with open(fd, "wb") as f:
                f.write(pem)

        return key

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
        tycho_verdict: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes a single end-to-end AEIB v0.4.0 flow and returns the signed OpenTelemetry event.
        """
        caid = derive_caid(noun, verb, payload)

        # Check ANSI 86 Interlock latch
        if self.locked_latches.get(caid, False):
            raise RuntimeError(
                f"ANSI 86 Software Lockout Latch active for CAID {caid}. "
                "Dispatches are rejected until an explicit authoritative reset event."
            )

        # -------------------------------------------------------------
        # Step 1: L7a Transport Observation
        # -------------------------------------------------------------
        wire_fault = None
        if transport_status_code == 504 or transport_observation == "http_504_gateway_timeout":
            wire_fault = "http_504_gateway_timeout"
        elif transport_status_code == 0 and "tcp_rst" in transport_observation.lower():
            wire_fault = "tcp_rst"

        l7a = Layer7aTransportResult(
            observation=transport_observation,
            status_code=transport_status_code,
            wire_fault=wire_fault,
        )
        l7a_attrs = l7a.to_attributes()
        validate_authority_bounds("L7a", l7a_attrs)

        # Assertion: Model hypothesis cannot override L7a transport facts
        if model_hypothesis:
            for k, v in model_hypothesis.items():
                if k.startswith("aeib.transport."):
                    if k in l7a_attrs and l7a_attrs[k] != v:
                        raise ImmutableFactViolationError(
                            f"Model hypothesis attempted to overwrite immutable wire fact '{k}': "
                            f"actual '{l7a_attrs[k]}' vs model '{v}'."
                        )
                elif k in ("aeib.disposition", "aeib.retry_safe", "aeib.release_authorization"):
                    raise ImmutableFactViolationError(
                        f"Model hypothesis forbidden from asserting governance attribute '{k}'."
                    )

        # -------------------------------------------------------------
        # Step 2: L7b Authoritative Probe
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
        # Step 3: L7c Disposition Derivation
        # -------------------------------------------------------------
        l7c = self._derive_disposition(
            transport_obs=l7a.observation,
            status_code=l7a.status_code,
            probe=l7b,
            has_idempotency_contract=provider_idempotency_contract_present,
        )

        # -------------------------------------------------------------
        # AEIB v0.4.0: Offline Tycho Verifier Integration (Fail-Closed)
        # -------------------------------------------------------------
        # Exact vocabulary match only: no whitespace normalization, no coercion.
        verdict = tycho_verdict if isinstance(tycho_verdict, str) else None

        if verdict is None or verdict not in EVALUATED_TYCHO_VERDICTS:
            # Un-evaluated or missing YAML contract: latch the CAID first, then
            # halt execution before any receipt is emitted (no fail-open path).
            self.locked_latches[caid] = True
            raise StructuralVerificationError(
                f"Tycho structural verdict missing or un-evaluated for CAID {caid}; "
                f"received {tycho_verdict!r}. Execution halted before receipt signing."
            )

        if verdict != "VERIFIED":
            # Evaluated non-VERIFIED state: sign an intercept receipt and latch.
            l7c.disposition = f"STRUCTURAL_VERIFICATION_{verdict}"
            l7c.retry_safe = False
            l7c.retry_policy = "PROHIBITED_TYCHO_LATCH"
            l7c.mapping_rule_id = "RULE-TYCHO-INTERCEPT"
            l7c.latch_engaged = True

        l7c_attrs = l7c.to_attributes()
        validate_authority_bounds("L7c", l7c_attrs)

        # Engage latch if unconfirmed or quarantined
        if l7c.latch_engaged:
            self.locked_latches[caid] = True

        # -------------------------------------------------------------
        # Step 4: L8 Evidence Verification & Dynamic Signing
        # -------------------------------------------------------------
        event_body = {
            "aeib.caid": caid,
            "aeib.action.noun": noun,
            "aeib.action.verb": verb,
            "aeib.payload_hash": generate_jcs_payload_hash(payload),
            **l7a_attrs,
            **l7b_attrs,
            **l7c_attrs,
            "aeib.release_authorization": "not_provided",
            "aeib.spec_version": "0.4.0",
        }

        if model_hypothesis:
            event_body["aeib.model_hypothesis"] = {
                k: v for k, v in model_hypothesis.items() if not k.startswith("aeib.")
            }

        # Canonicalize via strict RFC 8785 JCS
        canonical_event_bytes = encode_jcs(event_body)
        event_digest = hashlib.sha256(canonical_event_bytes).hexdigest()

        # Sign with Ed25519
        signature = self.signing_key.sign(canonical_event_bytes)

        # Dynamic verification: verify immediately against public key
        pubkey = self.signing_key.public_key()
        try:
            pubkey.verify(signature, canonical_event_bytes)
            receipt_verified = True
        except InvalidSignature:
            receipt_verified = False

        l8_attrs = {
            "aeib.receipt.signature": signature.hex(),
            "aeib.receipt.public_key_hex": self.public_key_hex,
            "aeib.receipt.jcs_payload_hash": f"sha256:{event_digest}",
            "aeib.receipt.verified": receipt_verified,
            "aeib.release_authorization": "not_provided"
        }
        validate_authority_bounds("L8", l8_attrs)

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
        """Derives disposition and retry safety under v0.4.0 mapping contract rules."""
        
        # Scenario: HTTP 504 / Transport Timeout Drop
        if status_code == 504 or transport_obs in ("http_504_gateway_timeout", "HTTP_504_GATEWAY_TIMEOUT"):
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
                if probe.consistency_model == "eventual_read":
                    return Layer7cDispositionResult(
                        disposition="EFFECT_INDETERMINATE",
                        retry_safe=False,
                        retry_policy="PROHIBITED_REPLICA_LAG_HOLD",
                        mapping_rule_id="RULE-504-04-INDETERMINATE",
                        latch_engaged=True
                    )
                else:
                    if has_idempotency_contract:
                        return Layer7cDispositionResult(
                            disposition="RECONCILIATION_NOT_FOUND_AFTER_GRACE",
                            retry_safe=True,
                            retry_policy="PERMITTED_IDEMPOTENCY_BOUND",
                            mapping_rule_id="RULE-504-05-NOT_FOUND_PERMITTED",
                            latch_engaged=False
                        )
                    else:
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

        # Authoritative Probe Confirmation under Any Wire Anomaly (e.g. TCP RST)
        if probe.query_status == "RECORD_FOUND":
            return Layer7cDispositionResult(
                disposition="OUTCOME_VERIFIED",
                retry_safe=False,
                retry_policy="PROHIBITED_ALREADY_COMMITTED",
                mapping_rule_id="RULE-PROBE-01-VERIFIED",
                latch_engaged=False
            )
        elif probe.query_status == "PAYLOAD_MISMATCH":
            return Layer7cDispositionResult(
                disposition="RECONCILIATION_CONFLICT",
                retry_safe=False,
                retry_policy="PROHIBITED_ESCALATE_AUDIT",
                mapping_rule_id="RULE-PROBE-02-CONFLICT",
                latch_engaged=True
            )

        # Default fallback: Unclassified transport anomaly
        return Layer7cDispositionResult(
            disposition="DISPATCHED_UNCONFIRMED",
            retry_safe=False,
            retry_policy="PROHIBITED_DEFAULT_LATCH",
            mapping_rule_id="RULE-DEFAULT-UNCONFIRMED",
            latch_engaged=True
        )
