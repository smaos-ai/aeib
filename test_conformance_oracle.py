#!/usr/bin/env python3
r"""
test_aeib_v030_oracle.py — Conformance Oracle for AEIB v0.3.0 Specification (Part 9)
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity Benchmark (AEIB)

Evaluates all six assertions of the AEIB v0.3.0 6-Point Conformance Oracle
under an injected HTTP 504 post-dispatch fault condition:
1. Transport Fact Preservation (L7a)
2. No Layer Override (L1-L6 vs L7a)
3. Explicit Probe Scope (L7b authority_scope & consistency_model)
4. Fail-Closed Retry Derivation (L7c replica lag & idempotency checks)
5. Release Authorization Separation (L9 separation: "not_provided")
6. Attribution Isolation (Authority Registry cannot_assert bounds)
Plus ANSI 86-inspired software lockout interlock verification (Part 7).
"""

import os
import sys
import unittest
from datetime import datetime, timezone

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.aeib_v030_engine import (
    AEIB030Pipeline,
    derive_caid,
    validate_authority_bounds,
    AuthorityViolationError,
    ImmutableFactViolationError,
    AUTHORITY_REGISTRY,
)
from src.jcs_canonicalizer import encode_jcs
from cryptography.hazmat.primitives.asymmetric import ed25519


class TestAEIB030ConformanceOracle(unittest.TestCase):
    """Automated evaluation harness for the AEIB v0.3.0 Conformance Oracle."""

    def setUp(self):
        self.pipeline = AEIB030Pipeline()
        self.noun = "scholarly_dataset"
        self.verb = "deposit_record"
        self.payload = {
            "title": "Autonomous Agent Protocol Benchmarks",
            "repository": "Figshare",
            "doi_prefix": "10.5281/zenodo"
        }

    # --------------------------------------------------------------------------
    # Assertion 1: Transport Fact Preservation (L7a)
    # --------------------------------------------------------------------------
    def test_assertion_1_transport_fact_preservation(self):
        """L7a records immutable transport observation = 'http_504_after_dispatch'."""
        event = self.pipeline.execute_flow(
            noun=self.noun,
            verb=self.verb,
            payload=self.payload,
            transport_observation="http_504_after_dispatch",
            transport_status_code=504,
        )

        attrs = event["attributes"]
        self.assertEqual(attrs["aeib.transport.observation"], "http_504_after_dispatch")
        self.assertEqual(int(attrs["aeib.transport.status_code"]), 504)
        self.assertEqual(attrs["aeib.transport.wire_fault"], "http_504_gateway_timeout")

    # --------------------------------------------------------------------------
    # Assertion 2: No Layer Override (L1 Model Hypothesis vs L7a Fact)
    # --------------------------------------------------------------------------
    def test_assertion_2_no_layer_override(self):
        """L1 model hypothesis cannot alter, overwrite, or downgrade L7a transport facts."""
        malicious_hypothesis = {
            "aeib.transport.observation": "success_inferred_from_prompt",  # Illegal override attempt
            "theory": "The gateway timed out but the server might have committed anyway."
        }

        # Attempting to override the immutable fact must raise ImmutableFactViolationError
        with self.assertRaises(ImmutableFactViolationError):
            self.pipeline.execute_flow(
                noun=self.noun,
                verb=self.verb,
                payload=self.payload,
                transport_observation="http_504_after_dispatch",
                transport_status_code=504,
                model_hypothesis=malicious_hypothesis,
            )

        # Compliant hypothesis recording (doesn't attempt to overwrite observation)
        valid_hypothesis = {
            "model_confidence": 0.42,
            "speculative_retry_requested": True
        }
        event = self.pipeline.execute_flow(
            noun=self.noun,
            verb=self.verb,
            payload=self.payload,
            transport_observation="http_504_after_dispatch",
            transport_status_code=504,
            model_hypothesis=valid_hypothesis,
        )
        self.assertEqual(event["attributes"]["aeib.transport.observation"], "http_504_after_dispatch")
        self.assertEqual(event["attributes"]["aeib.model_hypothesis"]["model_confidence"], 0.42)

    # --------------------------------------------------------------------------
    # Assertion 3: Explicit Probe Scope (L7b)
    # --------------------------------------------------------------------------
    def test_assertion_3_explicit_probe_scope(self):
        """L7b records explicit authority_scope and consistency_model."""
        event = self.pipeline.execute_flow(
            noun=self.noun,
            verb=self.verb,
            payload=self.payload,
            transport_observation="http_504_after_dispatch",
            transport_status_code=504,
            probe_authority_scope="provider_primary",
            probe_consistency_model="strong_read",
            probe_query_status="RECORD_NOT_FOUND",
        )

        attrs = event["attributes"]
        self.assertEqual(attrs["aeib.probe.authority_scope"], "provider_primary")
        self.assertEqual(attrs["aeib.probe.consistency_model"], "strong_read")
        self.assertEqual(attrs["aeib.probe.query_status"], "RECORD_NOT_FOUND")

    # --------------------------------------------------------------------------
    # Assertion 4: Fail-Closed Retry Derivation (L7c)
    # --------------------------------------------------------------------------
    def test_assertion_4a_eventual_consistency_yields_indeterminate_and_prohibits_retry(self):
        """Eventual consistency read (replica lag) cannot prove absence -> EFFECT_INDETERMINATE."""
        event = self.pipeline.execute_flow(
            noun=self.noun,
            verb=self.verb,
            payload=self.payload,
            transport_observation="http_504_after_dispatch",
            transport_status_code=504,
            probe_authority_scope="read_replica_eu_central",
            probe_consistency_model="eventual_read",
            probe_query_status="RECORD_NOT_FOUND",
        )

        attrs = event["attributes"]
        self.assertEqual(attrs["aeib.disposition"], "EFFECT_INDETERMINATE")
        self.assertFalse(attrs["aeib.retry_safe"])
        self.assertEqual(attrs["aeib.retry_policy"], "PROHIBITED_REPLICA_LAG_HOLD")
        self.assertTrue(attrs["aeib.latch_engaged"])

    def test_assertion_4b_fail_closed_default_without_idempotency_contract(self):
        """Strong read on primary without provider idempotency contract -> retry_safe: False."""
        event = self.pipeline.execute_flow(
            noun=self.noun,
            verb=self.verb,
            payload=self.payload,
            transport_observation="http_504_after_dispatch",
            transport_status_code=504,
            probe_authority_scope="provider_primary",
            probe_consistency_model="strong_read",
            probe_query_status="RECORD_NOT_FOUND",
            provider_idempotency_contract_present=False,  # No contract
        )

        attrs = event["attributes"]
        self.assertEqual(attrs["aeib.disposition"], "RECONCILIATION_NOT_FOUND_AFTER_GRACE")
        self.assertFalse(attrs["aeib.retry_safe"])
        self.assertEqual(attrs["aeib.retry_policy"], "PROHIBITED_FAIL_CLOSED")
        self.assertTrue(attrs["aeib.latch_engaged"])

    def test_assertion_4c_retry_permitted_only_with_idempotency_contract(self):
        """Strong read on primary with verified provider idempotency contract -> retry_safe: True."""
        event = self.pipeline.execute_flow(
            noun=self.noun,
            verb=self.verb,
            payload=self.payload,
            transport_observation="http_504_after_dispatch",
            transport_status_code=504,
            probe_authority_scope="provider_primary",
            probe_consistency_model="strong_read",
            probe_query_status="RECORD_NOT_FOUND",
            provider_idempotency_contract_present=True,  # Explicit contract verified
        )

        attrs = event["attributes"]
        self.assertEqual(attrs["aeib.disposition"], "RECONCILIATION_NOT_FOUND_AFTER_GRACE")
        self.assertTrue(attrs["aeib.retry_safe"])
        self.assertEqual(attrs["aeib.retry_policy"], "PERMITTED_IDEMPOTENCY_BOUND")
        self.assertFalse(attrs["aeib.latch_engaged"])

    # --------------------------------------------------------------------------
    # Assertion 5: Release Authorization Separation (L9 vs L8)
    # --------------------------------------------------------------------------
    def test_assertion_5_release_authorization_strictly_separated(self):
        """Core Boundary: 'Verified is not released'. aeib.release_authorization must be 'not_provided'."""
        event = self.pipeline.execute_flow(
            noun=self.noun,
            verb=self.verb,
            payload=self.payload,
            transport_observation="http_504_after_dispatch",
            transport_status_code=504,
            probe_query_status="RECORD_FOUND",
            probe_matched_record_id="rec-99120",
        )

        attrs = event["attributes"]
        # The evidence is verified
        self.assertEqual(attrs["aeib.disposition"], "OUTCOME_VERIFIED")
        self.assertTrue(attrs["aeib.receipt.verified"])

        # BUT release authorization is strictly not provided by the verifier
        self.assertEqual(attrs["aeib.release_authorization"], "not_provided")

        # Cryptographically verify the Ed25519 signature
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(attrs["aeib.receipt.public_key_hex"])
        )
        sig_bytes = bytes.fromhex(attrs["aeib.receipt.signature"])

        # Re-build canonical signed payload
        signed_body = {k: v for k, v in attrs.items() if not k.startswith("aeib.receipt.")}
        canonical_bytes = encode_jcs(signed_body)
        public_key.verify(sig_bytes, canonical_bytes)  # Will raise InvalidSignature if forged

    # --------------------------------------------------------------------------
    # Assertion 6: Attribution Isolation & cannot_assert Rules
    # --------------------------------------------------------------------------
    def test_assertion_6_attribution_isolation_enforced(self):
        """Each layer is structurally prevented from asserting attributes outside its authority."""
        # L7a cannot assert release_authorization or disposition
        with self.assertRaises(AuthorityViolationError):
            validate_authority_bounds("L7a", {"aeib.release_authorization": "granted"})

        with self.assertRaises(AuthorityViolationError):
            validate_authority_bounds("L7a", {"aeib.disposition": "OUTCOME_VERIFIED"})

        # L7b cannot assert retry_safe or disposition
        with self.assertRaises(AuthorityViolationError):
            validate_authority_bounds("L7b", {"aeib.retry_safe": True})

        # L7c cannot assert release_authorization
        with self.assertRaises(AuthorityViolationError):
            validate_authority_bounds("L7c", {"aeib.release_authorization": "granted"})

        # L8 cannot grant release authorization
        with self.assertRaises(AuthorityViolationError):
            validate_authority_bounds("L8", {"aeib.release_authorization_granted": True})

    # --------------------------------------------------------------------------
    # Part 7: ANSI 86-Inspired Software Lockout Latch Interlock
    # --------------------------------------------------------------------------
    def test_part_7_ansi_86_software_lockout_interlock(self):
        """When an unconfirmed latch engages, immediate re-dispatch of the same CAID is rejected."""
        # 1. Trigger an unconfirmed state that engages the latch
        event1 = self.pipeline.execute_flow(
            noun=self.noun,
            verb=self.verb,
            payload=self.payload,
            transport_observation="http_504_after_dispatch",
            transport_status_code=504,
            probe_query_status="RECORD_NOT_FOUND",
            provider_idempotency_contract_present=False,  # Latch engages
        )
        self.assertTrue(event1["attributes"]["aeib.latch_engaged"])

        # 2. Speculative re-dispatch of identical CAID must be rejected by the ANSI 86 interlock
        with self.assertRaises(RuntimeError) as ctx:
            self.pipeline.execute_flow(
                noun=self.noun,
                verb=self.verb,
                payload=self.payload,
                transport_observation="http_504_after_dispatch",
                transport_status_code=504,
            )
        self.assertIn("ANSI 86 Software Lockout Latch active", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
