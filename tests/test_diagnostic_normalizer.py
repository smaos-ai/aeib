#!/usr/bin/env python3
"""
test_diagnostic_normalizer.py — Comprehensive Test Suite for diagnostic_normalizer.py
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity (AEIB)

Tests:
  1. MCP JSON-RPC 2.0 parser (valid, malformed, non-MCP namespaces)
  2. Four-step SMAOS execution wrap cycle
  3. Pre-dispatch authority checks (valid, expired TTL, future valid_from, unauthorized tool)
  4. Transport fault trapping (HTTP 504, TCP RST)
  5. Post-condition probe abstractions (DatabaseStateProber, HTTPReconciliationProber)
  6. Granular disposition state machine (all 7 states + REFUSED)
  7. Freshness state machine (UNMEASURED, CLOCK_ORDER_INVALID, STALE, FRESH)
  8. RFC 9052 COSE_Sign1 envelope verification, kid resolution, and negative tamper cases
  9. Invariant: Wire 200 without probe strictly yields ACK_UNVERIFIED
"""

import os
import sys
import json
import time
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from cryptography.hazmat.primitives.asymmetric import ed25519

from src.diagnostic_normalizer import (
    MCPJSONRPCParser,
    DiagnosticExecutionNormalizer,
    AuthorityContext,
    DatabaseStateProber,
    HTTPReconciliationProber,
    COSESign1Engine,
    KeyRegistry,
    MinimalCBOR,
    COSE_ALG_EDDSA,
    deterministic_digest,
    deterministic_json_bytes,
    SERIALIZATION_LABEL
)


class MockMCPClient:
    """Mock client simulating downstream tool execution and wire exceptions."""
    def __init__(self):
        self.fault_mode = None
        self.recorded_headers = None
        self.recorded_args = None

    def set_fault(self, mode: str):
        self.fault_mode = mode

    def call_tool(self, tool_name: str, arguments: dict, headers: dict = None) -> dict:
        self.recorded_headers = headers
        self.recorded_args = arguments

        if self.fault_mode == "504_timeout":
            raise TimeoutError("Gateway timed out after 30000ms")
        elif self.fault_mode == "tcp_rst":
            raise ConnectionResetError("Connection reset by peer (ECONNRESET)")
        elif self.fault_mode == "http_500":
            err = RuntimeError("Internal server error")
            err.status_code = 500
            raise err

        return {"status": "SUCCESS", "ack": True, "tool": tool_name}


class TestDiagnosticNormalizer(unittest.TestCase):

    def setUp(self):
        self.priv_key = ed25519.Ed25519PrivateKey.generate()
        self.pub_key = self.priv_key.public_key()
        self.kid = "key:test-ed25519-01"
        self.normalizer = DiagnosticExecutionNormalizer(
            signing_key=self.priv_key,
            key_id=self.kid,
            freshness_limit_ms=5000.0  # 5 seconds for test precision
        )
        self.mock_client = MockMCPClient()

    # ── 1. MCP JSON-RPC 2.0 Parser Tests ─────────────────────────────────────

    def test_01_valid_mcp_tools_call_parsing(self):
        """Verifies standard tools/call JSON-RPC 2.0 parsing."""
        raw = {
            "jsonrpc": "2.0",
            "id": "rpc-42",
            "method": "tools/call",
            "params": {
                "name": "payment.disburse",
                "arguments": {"iban": "CZ123", "amount": 1000}
            }
        }
        tool_name, args, rpc_id = MCPJSONRPCParser.parse_tools_call(raw)
        self.assertEqual(tool_name, "payment.disburse")
        self.assertEqual(args, {"iban": "CZ123", "amount": 1000})
        self.assertEqual(rpc_id, "rpc-42")

    def test_02_legacy_mcp_tool_prefix_parsing(self):
        """Verifies tools/{name} shorthand method parsing."""
        raw = {
            "jsonrpc": "2.0",
            "id": "rpc-99",
            "method": "tools/fx_swap",
            "params": {"pair": "EURCZK", "lot": 5}
        }
        tool_name, args, rpc_id = MCPJSONRPCParser.parse_tools_call(raw)
        self.assertEqual(tool_name, "fx_swap")
        self.assertEqual(args["pair"], "EURCZK")

    def test_03_malformed_jsonrpc_rejection(self):
        """Verifies rejection of non-2.0 JSON-RPC or missing params."""
        # Bad version
        with self.assertRaises(ValueError):
            MCPJSONRPCParser.parse_tools_call({"jsonrpc": "1.0", "method": "tools/call"})
        # Missing params
        with self.assertRaises(ValueError):
            MCPJSONRPCParser.parse_tools_call({"jsonrpc": "2.0", "id": "1", "method": "tools/call"})
        # Non-MCP namespace
        with self.assertRaises(ValueError):
            MCPJSONRPCParser.parse_tools_call({"jsonrpc": "2.0", "id": "1", "method": "admin/shutdown", "params": {}})

    def test_04_action_id_and_uuidv5_determinism(self):
        """Verifies composite action_id format and UUIDv5 idempotency key determinism."""
        action_id = MCPJSONRPCParser.generate_composite_action_id("sess-a", 4, "rpc-1", "swift.wire")
        self.assertEqual(action_id, "mcp://sess-a/4/rpc-1/swift.wire")

        payload_hash = deterministic_digest({"beneficiary": "bank-b", "val": 500})
        key1 = MCPJSONRPCParser.generate_uuidv5_idempotency_key(action_id, payload_hash)
        key2 = MCPJSONRPCParser.generate_uuidv5_idempotency_key(action_id, payload_hash)
        self.assertEqual(key1, key2)
        self.assertEqual(len(key1), 36)  # Standard UUID format

    # ── 2. Step 1: Pre-Dispatch Authority Checks ─────────────────────────────

    def test_05_pre_dispatch_authority_valid(self):
        """Verifies valid authority passes and computes authority digest."""
        ctx = AuthorityContext(
            actor="did:bank:treasury",
            tool="swift.wire",
            allowed_tools=["swift.wire", "swift.status"]
        )
        is_auth, reason, h = self.normalizer.pre_dispatch_authority_check(ctx)
        self.assertTrue(is_auth)
        self.assertEqual(reason, "AUTHORITY_CONFIRMED")
        self.assertIsNotNone(h)

    def test_06_pre_dispatch_authority_disallowed_tool(self):
        """Verifies caller attempting unauthorized tool fails closed."""
        ctx = AuthorityContext(
            actor="did:bank:junior-clerk",
            tool="core.delete_ledger",
            allowed_tools=["core.read_balance"]
        )
        is_auth, reason, h = self.normalizer.pre_dispatch_authority_check(ctx)
        self.assertFalse(is_auth)
        self.assertIn("not permitted", reason)

    def test_07_pre_dispatch_authority_expired_ttl(self):
        """Verifies expired authority TTL halts before wire dispatch."""
        past_iso = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        ctx = AuthorityContext(
            actor="did:bank:treasury",
            tool="swift.wire",
            authority_ttl=past_iso
        )
        is_auth, reason, h = self.normalizer.pre_dispatch_authority_check(ctx)
        self.assertFalse(is_auth)
        self.assertIn("expired", reason)

    def test_08_pre_dispatch_authority_unmanufactured_ttl(self):
        """Verifies absence of TTL preserves None in evidence (no fabricated default)."""
        ctx = AuthorityContext(
            actor="did:bank:treasury",
            tool="swift.wire",
            authority_ttl=None
        )
        is_auth, reason, h = self.normalizer.pre_dispatch_authority_check(ctx)
        self.assertTrue(is_auth)
        self.assertIsNone(ctx.authority_ttl)

    # ── 3. Step 2 & 3: Dispatch & Probe Granular Dispositions ────────────────

    def test_09_disposition_outcome_verified_via_database_prober(self):
        """Verifies physical confirmation yields OUTCOME_VERIFIED via DatabaseStateProber."""
        db_prober = DatabaseStateProber(":memory:")
        sample_call = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "tools/call",
            "params": {"name": "escrow.release", "arguments": {"contract": "CNT-991"}}
        }
        # Pre-populate database with committed record
        tool_name, args, rpc_id = MCPJSONRPCParser.parse_tools_call(sample_call)
        action_id = MCPJSONRPCParser.generate_composite_action_id("sess-1", 1, rpc_id, tool_name)
        payload_hash = deterministic_digest(args)
        idem_key = MCPJSONRPCParser.generate_uuidv5_idempotency_key(action_id, payload_hash)

        db_prober.insert_record(idem_key, action_id, payload_hash, "COMMITTED", '{"released": true}')

        receipt = self.normalizer.execute_lifecycle(
            raw_mcp_request=sample_call,
            actor="did:bank:escrow-officer",
            session_id="sess-1",
            step_sequence=1,
            mcp_client=self.mock_client,
            state_prober=db_prober
        )

        self.assertEqual(receipt.disposition, "OUTCOME_VERIFIED")
        self.assertTrue(receipt.outcome_verified)
        self.assertIsNotNone(receipt.downstream_state_hash)
        self.assertFalse(receipt.retry_policy["retry_allowed"])

    def test_10_invariant_wire_200_without_probe_is_ack_unverified(self):
        """The Core Invariant: HTTP 200 without authoritative probe defaults to ACK_UNVERIFIED."""
        sample_call = {
            "jsonrpc": "2.0",
            "id": "2",
            "method": "tools/call",
            "params": {"name": "wire.transfer", "arguments": {"amount": 50000}}
        }
        receipt = self.normalizer.execute_lifecycle(
            raw_mcp_request=sample_call,
            actor="did:bank:teller",
            session_id="sess-2",
            step_sequence=2,
            mcp_client=self.mock_client,
            state_prober=None  # NO probe supplied!
        )

        self.assertEqual(receipt.disposition, "ACK_UNVERIFIED")
        self.assertFalse(receipt.outcome_verified)
        self.assertIsNone(receipt.downstream_state_hash)
        self.assertIn("unverified without downstream state probe", receipt.observed_outcome["note"])

    def test_11_disposition_dispatched_unconfirmed_on_504_drop(self):
        """Verifies HTTP 504 wire drop without probe quarantines to DISPATCHED_UNCONFIRMED."""
        self.mock_client.set_fault("504_timeout")
        sample_call = {
            "jsonrpc": "2.0",
            "id": "3",
            "method": "tools/call",
            "params": {"name": "swift.dispatch", "arguments": {"ref": "SW-771"}}
        }
        receipt = self.normalizer.execute_lifecycle(
            raw_mcp_request=sample_call,
            actor="did:bank:treasury",
            session_id="sess-3",
            step_sequence=3,
            mcp_client=self.mock_client,
            state_prober=None
        )

        self.assertEqual(receipt.disposition, "DISPATCHED_UNCONFIRMED")
        self.assertFalse(receipt.outcome_verified)
        self.assertIn("504", receipt.transport_fault)
        self.assertFalse(receipt.retry_policy["retry_allowed"])

    def test_12_disposition_reconciliation_not_found(self):
        """Verifies probe querying missing downstream record yields RECONCILIATION_NOT_FOUND."""
        self.mock_client.set_fault("tcp_rst")
        db_prober = DatabaseStateProber(":memory:")  # Empty database
        sample_call = {
            "jsonrpc": "2.0",
            "id": "4",
            "method": "tools/call",
            "params": {"name": "funds.freeze", "arguments": {"acc": "ACC-901"}}
        }
        receipt = self.normalizer.execute_lifecycle(
            raw_mcp_request=sample_call,
            actor="did:bank:compliance",
            session_id="sess-4",
            step_sequence=4,
            mcp_client=self.mock_client,
            state_prober=db_prober
        )

        self.assertEqual(receipt.disposition, "RECONCILIATION_NOT_FOUND")
        self.assertFalse(receipt.outcome_verified)
        self.assertTrue(receipt.retry_policy["retry_allowed"])  # Retry allowed with fresh authority!

    def test_13_disposition_reconciliation_failed_tampering(self):
        """Verifies payload hash divergence yields RECONCILIATION_FAILED."""
        db_prober = DatabaseStateProber(":memory:")
        sample_call = {
            "jsonrpc": "2.0",
            "id": "5",
            "method": "tools/call",
            "params": {"name": "loan.originate", "arguments": {"amount": 100000}}
        }
        tool_name, args, rpc_id = MCPJSONRPCParser.parse_tools_call(sample_call)
        action_id = MCPJSONRPCParser.generate_composite_action_id("sess-5", 5, rpc_id, tool_name)
        payload_hash = deterministic_digest(args)
        idem_key = MCPJSONRPCParser.generate_uuidv5_idempotency_key(action_id, payload_hash)

        # Insert tampered row: same key, but different payload hash
        db_prober.insert_record(idem_key, action_id, "sha256:TAMPERED_HASH", "COMMITTED")

        receipt = self.normalizer.execute_lifecycle(
            raw_mcp_request=sample_call,
            actor="did:bank:loan-officer",
            session_id="sess-5",
            step_sequence=5,
            mcp_client=self.mock_client,
            state_prober=db_prober
        )

        self.assertEqual(receipt.disposition, "RECONCILIATION_FAILED")
        self.assertFalse(receipt.outcome_verified)
        self.assertFalse(receipt.retry_policy["retry_allowed"])

    def test_14_disposition_probe_exception(self):
        """Verifies probe backend error maps cleanly to PROBE_EXCEPTION without crashing."""
        class FaultyProber:
            def probe(self, key, action, h):
                raise ConnectionError("Database network interface down")

        sample_call = {
            "jsonrpc": "2.0",
            "id": "6",
            "method": "tools/call",
            "params": {"name": "core.audit", "arguments": {}}
        }
        receipt = self.normalizer.execute_lifecycle(
            raw_mcp_request=sample_call,
            actor="did:bank:auditor",
            session_id="sess-6",
            step_sequence=6,
            mcp_client=self.mock_client,
            state_prober=FaultyProber()
        )

        self.assertEqual(receipt.disposition, "PROBE_EXCEPTION")
        self.assertFalse(receipt.outcome_verified)

    def test_15_disposition_reconciliation_conflict(self):
        """Verifies duplicate/conflicting records yield RECONCILIATION_CONFLICT."""
        receipt = self.normalizer.execute_lifecycle(
            raw_mcp_request={
                "jsonrpc": "2.0", "id": "7", "method": "tools/call",
                "params": {"name": "tx.post", "arguments": {"id": 1}}
            },
            actor="did:bank:ledger",
            manual_probe_result={"conflict_detected": True, "duplicate_count": 2}
        )
        self.assertEqual(receipt.disposition, "RECONCILIATION_CONFLICT")
        self.assertFalse(receipt.outcome_verified)

    # ── 4. Step 4: Freshness Policy State-Machine ────────────────────────────

    def test_16_freshness_unmeasured(self):
        """Missing valid_from or transaction_time yields UNMEASURED."""
        receipt = self.normalizer.execute_lifecycle(
            raw_mcp_request={"jsonrpc": "2.0", "id": "8", "method": "tools/call", "params": {"name": "t.test", "arguments": {}}},
            actor="did:test",
            valid_time_t0=None
        )
        self.assertEqual(receipt.freshness_status, "UNMEASURED")
        self.assertIsNone(receipt.wall_clock_delta_ms)

    def test_17_freshness_clock_order_invalid(self):
        """Clock backward step (tn < t0) yields CLOCK_ORDER_INVALID."""
        t_base = time.time()
        receipt = self.normalizer.attest_execution(
            action_id="mcp://sess/1/1/t.test",
            actor="did:test",
            authority_hash="sha256:00",
            authority_ttl=None,
            dispatched_at_iso="2026-09-28T00:00:00Z",
            req_payload_hash="sha256:11",
            downstream_state_hash=None,
            observed_outcome={},
            outcome_verified=True,
            verification_method="test",
            disposition="OUTCOME_VERIFIED",
            transport_fault=None,
            valid_time_t0=t_base + 10.0,  # t0 is in the future
            transaction_time_tn=t_base     # tn is earlier
        )
        self.assertEqual(receipt.freshness_status, "CLOCK_ORDER_INVALID")
        self.assertLess(receipt.wall_clock_delta_ms, 0)

    def test_18_freshness_stale_vs_fresh(self):
        """Verifies policy threshold compliance (delta > limit -> STALE; delta <= limit -> FRESH)."""
        t0 = 1000.0
        # Exceeds 5000ms limit -> STALE
        r_stale = self.normalizer.attest_execution(
            action_id="mcp://sess/1/1/t.test", actor="did:test", authority_hash="sha256:00",
            authority_ttl=None, dispatched_at_iso="2026-09-28T00:00:00Z", req_payload_hash="sha256:11",
            downstream_state_hash=None, observed_outcome={}, outcome_verified=True,
            verification_method="test", disposition="OUTCOME_VERIFIED", transport_fault=None,
            valid_time_t0=t0, transaction_time_tn=t0 + 6.0, freshness_limit_ms=5000.0
        )
        self.assertEqual(r_stale.freshness_status, "STALE")
        self.assertEqual(r_stale.wall_clock_delta_ms, 6000.0)

        # Within 5000ms limit -> FRESH
        r_fresh = self.normalizer.attest_execution(
            action_id="mcp://sess/1/1/t.test", actor="did:test", authority_hash="sha256:00",
            authority_ttl=None, dispatched_at_iso="2026-09-28T00:00:00Z", req_payload_hash="sha256:11",
            downstream_state_hash=None, observed_outcome={}, outcome_verified=True,
            verification_method="test", disposition="OUTCOME_VERIFIED", transport_fault=None,
            valid_time_t0=t0, transaction_time_tn=t0 + 1.2, freshness_limit_ms=5000.0
        )
        self.assertEqual(r_fresh.freshness_status, "FRESH")
        self.assertEqual(r_fresh.wall_clock_delta_ms, 1200.0)

    # ── 5. Step 4: RFC 9052 COSE_Sign1 Cryptographic Verification ─────────────

    def test_19_cose_sign1_envelope_verification(self):
        """Verifies standard COSE_Sign1 envelope validates with public key."""
        receipt = self.normalizer.execute_lifecycle(
            raw_mcp_request={"jsonrpc": "2.0", "id": "10", "method": "tools/call", "params": {"name": "vault.open", "arguments": {}}},
            actor="did:bank:security-officer"
        )
        self.assertIsNotNone(receipt.cose_envelope_hex)
        self.assertEqual(receipt.cose_alg, COSE_ALG_EDDSA)
        self.assertEqual(receipt.cose_kid, self.kid)

        env_bytes = bytes.fromhex(receipt.cose_envelope_hex)
        is_valid, payload, meta = COSESign1Engine.verify_envelope(env_bytes, self.pub_key)
        self.assertTrue(is_valid)
        self.assertEqual(meta["cose_alg"], COSE_ALG_EDDSA)
        self.assertEqual(meta["cose_kid"], self.kid)

        # Check payload matches receipt canonical bytes
        parsed_payload = json.loads(payload.decode("utf-8"))
        self.assertEqual(parsed_payload["action_id"], receipt.action_id)
        self.assertEqual(parsed_payload["serialization_format"], SERIALIZATION_LABEL)

    def test_20_cose_sign1_tamper_rejection(self):
        """Any bit flip in the COSE_Sign1 payload or signature must fail verification."""
        receipt = self.normalizer.execute_lifecycle(
            raw_mcp_request={"jsonrpc": "2.0", "id": "11", "method": "tools/call", "params": {"name": "auth.grant", "arguments": {}}},
            actor="did:bank:admin"
        )
        env_bytes = bytearray(bytes.fromhex(receipt.cose_envelope_hex))
        
        # Tamper last byte of signature
        env_bytes[-1] ^= 0x01
        is_valid, payload, meta = COSESign1Engine.verify_envelope(bytes(env_bytes), self.pub_key)
        self.assertFalse(is_valid)
        self.assertIn("error", meta)

    def test_21_cose_sign1_wrong_public_key_rejection(self):
        """Verifying with a different Ed25519 public key must fail."""
        receipt = self.normalizer.execute_lifecycle(
            raw_mcp_request={"jsonrpc": "2.0", "id": "12", "method": "tools/call", "params": {"name": "token.mint", "arguments": {}}},
            actor="did:bank:treasury"
        )
        env_bytes = bytes.fromhex(receipt.cose_envelope_hex)
        wrong_pub = ed25519.Ed25519PrivateKey.generate().public_key()
        is_valid, payload, meta = COSESign1Engine.verify_envelope(env_bytes, wrong_pub)
        self.assertFalse(is_valid)

    def test_22_key_registry_management(self):
        """Verifies KeyRegistry registers, looks up, and exports/imports PEM."""
        reg = KeyRegistry()
        reg.register_key("kid-1", self.pub_key)
        self.assertEqual(reg.get_key("kid-1"), self.pub_key)

        pem = reg.export_pem("kid-1")
        reg2 = KeyRegistry()
        reg2.register_from_pem("kid-imported", pem)
        self.assertIsNotNone(reg2.get_key("kid-imported"))

    def test_23_cose_sign1_pkcs11_zero_ram_signing(self):
        """Verifies COSESign1Engine signing via PKCS#11 enclave callback (Zero-RAM exposure)."""
        from pkcs11_hsm_enclave import get_hsm_enclave
        enclave = get_hsm_enclave(strict_hardware=False)

        engine = COSESign1Engine(pkcs11_signer_callback=enclave.sign_digest)
        receipt = engine.create_receipt({
            "action": "mcp://core/wire:transfer",
            "amount": 25000.0,
            "beneficiary": "DE89370400440532013000"
        })

        self.assertEqual(receipt["serialization"], SERIALIZATION_LABEL)
        self.assertNotEqual(receipt["signature"], "UNSIGNED_DEVELOPMENT_MODE")
        self.assertEqual(len(bytes.fromhex(receipt["signature"])), 64)

    def test_24_jcs_rfc8785_canonicalization_strict(self):
        """Verifies deterministic_json_bytes enforces strict RFC 8785 formatting."""
        payload = {"z": 1, "a": 2, "m": [3, 1, 2]}
        jcs_bytes = deterministic_json_bytes(payload)
        expected = b'{"a":2,"m":[3,1,2],"z":1}'
        self.assertEqual(jcs_bytes, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
