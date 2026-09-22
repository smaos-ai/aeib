#!/usr/bin/env python3
"""
test_smaos_audit_unified.py — Master Test Suite for Unified smaos-audit Architecture
Sovereign Multi-Agent OS (SMAOS) / STAR Protocol v1.1.0

Tests:
  1. Moat 10: protocols.mcp_guard (MCPDriftSentinel schema freeze & rug-pull rejection)
  2. Moat 11: protocols.x402_invariant (Stripe 402 upstream_timeout disambiguation & double-pay prevention)
  3. Moat 12: runtime.trust_ratchet (ADLC dynamic capability degradation & mutating tool lockout)
  4. Blind Spot 5: runtime.postgres_wal (Row-level SKIP LOCKED & composite PK idempotency)
  5. Moat 13: protocols.a2a_attestation (RFC 8615 Signed Agent Card to MCP receipt binding)
  6. Moat 3: core.detector (Normative six-disposition precedence ordering)
  7. Moat 10: Sovereign Cross-Jurisdiction Translation & PQC Agility (SovereignReporter & GlobalAuditReporter)

Zero external dependencies.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

# Ensure smaos-audit modules are in Python path
SYS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SYS_PATH not in sys.path:
    sys.path.insert(0, SYS_PATH)

# Ensure ocr_audit is in Python path for Moat 10 test
WORKSPACE_ROOT = os.path.abspath(os.path.join(SYS_PATH, ".."))
OCR_AUDIT_PATH = os.path.join(WORKSPACE_ROOT, "ocr-audit-engine", "src")
if OCR_AUDIT_PATH not in sys.path:
    sys.path.insert(0, OCR_AUDIT_PATH)

from protocols.mcp_guard import MCPDriftSentinel, SecurityViolationError
from protocols.x402_invariant import X402InvariantEngine
from protocols.a2a_attestation import A2AAttestationLink
from runtime.trust_ratchet import CapabilityLevel, TrustRatchet, proof_or_ratchet
from runtime.postgres_wal import PostgresWALCoordinator
from core.detector import resolve_precedence, classify_trace
from ocr_audit.reporter import SovereignReporter, GlobalAuditReporter, Disposition, PQCScheme, TRIPARTITE_MAPPING


class TestUnifiedSMAOSAudit(unittest.TestCase):

    def test_moat_10_mcp_drift_sentinel(self):
        sentinel = MCPDriftSentinel()
        baseline_tools = [
            {"name": "check_balance", "inputSchema": {"type": "object"}},
            {"name": "transfer_funds", "inputSchema": {"type": "object"}}
        ]
        
        # 1. Baseline establishment
        p1 = sentinel.intercept_request("tools/list", {"tools": baseline_tools})
        self.assertIn("tools", p1)
        self.assertFalse(sentinel.is_frozen)

        # 2. Identical subsequent request passes
        p2 = sentinel.intercept_request("tools/list", {"tools": baseline_tools})
        self.assertEqual(p1, p2)

        # 3. Silent tool expansion / Rug pull raises SecurityViolationError
        rogue_tools = list(baseline_tools)
        rogue_tools.append({"name": "exfiltrate_keys", "inputSchema": {"type": "object"}})
        with self.assertRaises(SecurityViolationError) as ctx:
            sentinel.intercept_request("tools/list", {"tools": rogue_tools})
        self.assertIn("MCP Tool Drift Detected (Rug Pull)", str(ctx.exception))
        self.assertTrue(sentinel.is_frozen)

        # 4. Subsequent calls remain frozen fail-closed
        with self.assertRaises(SecurityViolationError):
            sentinel.intercept_request("tools/list", {"tools": baseline_tools})

    def test_moat_10_credential_redaction(self):
        sentinel = MCPDriftSentinel()
        raw_resp = {
            "result": {
                "content": [
                    {"type": "text", "text": "Leaked key: sk-ant-1234567890abcdef12345678 and AWS AKIAIOSFODNN7EXAMPLE"}
                ]
            }
        }
        sanitized = sentinel.intercept_response(raw_resp)
        text = sanitized["result"]["content"][0]["text"]
        self.assertNotIn("sk-ant-1234567890abcdef12345678", text)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", text)
        self.assertIn("[REDACTED_ANTHROPIC_KEY]", text)
        self.assertIn("[REDACTED_AWS_KEY]", text)

    def test_moat_11_x402_invariant_engine(self):
        engine = X402InvariantEngine()

        # Non-402 status proceeds
        self.assertEqual(engine.evaluate_response(200, {}, "OK"), "PROCEED_WITH_STANDARD_LOGIC")

        # Legitimate 402 invoice -> REFUSED (awaiting policy approval)
        legit_headers = {"X-Payment-Amount": "10.00", "X-Payment-Proof": "required"}
        self.assertEqual(engine.evaluate_response(402, legit_headers, '{"invoice": 101}'), "REFUSED")

        # Stripe 402 upstream_timeout anomaly -> forced UNKNOWN (halts re-signing)
        timeout_headers = {"X-Error-Type": "upstream_timeout"}
        res = engine.evaluate_response(402, timeout_headers, '{"error": "upstream_timeout"}')
        self.assertEqual(res, "UNKNOWN")

        # Timeout in body also forces UNKNOWN
        res_body = engine.evaluate_response(402, {}, '{"detail": "gateway timeout dropped downstream"}')
        self.assertEqual(res_body, "UNKNOWN")

    def test_moat_12_dynamic_trust_ratchet(self):
        ratchet = TrustRatchet(initial_level=CapabilityLevel.UNRESTRICTED)

        @proof_or_ratchet(tool_type="mutating", custom_ratchet=ratchet)
        def settle_payment(amount: int):
            # Returns unconfirmed wire fact
            return {"status": "dispatched", "wire_confirmed": False}

        # Step 1: Call trips ratchet to READ_ONLY
        res = settle_payment(1000)
        self.assertEqual(res["status"], "UNKNOWN")
        self.assertEqual(res["ratchet_state"], "READ_ONLY")
        self.assertEqual(ratchet.level, CapabilityLevel.READ_ONLY)

        # Step 2: Second mutating call raises PermissionError
        with self.assertRaises(PermissionError) as ctx:
            settle_payment(2000)
        self.assertIn("blocked by Trust Ratchet", str(ctx.exception))

    def test_blind_spot_5_postgres_wal(self):
        wal = PostgresWALCoordinator()

        # 1. Idempotent composite primary key insert
        ok1, msg1 = wal.checkpoint("ACT-1", 1, "did:key:123", "payout", {"amt": 500})
        self.assertTrue(ok1)
        self.assertIn("COMMITTED", msg1)

        # 2. Duplicate is NOOP
        ok2, msg2 = wal.checkpoint("ACT-1", 1, "did:key:123", "payout", {"amt": 500})
        self.assertFalse(ok2)
        self.assertIn("IDEMPOTENT_NOOP", msg2)

        # 3. Row lock simulation (SKIP LOCKED)
        self.assertTrue(wal.acquire_lock_skip_locked("ACT-1"))
        self.assertFalse(wal.acquire_lock_skip_locked("ACT-1"))
        wal.release_lock("ACT-1")
        self.assertTrue(wal.acquire_lock_skip_locked("ACT-1"))

    def test_moat_13_a2a_attestation_link(self):
        link = A2AAttestationLink()
        card_digest = link.register_agent_card(
            agent_id="agent-eu-treasury",
            organization_did="did:ebsi:org-bank-prague",
            public_key="0xed25519_pub_key_here",
            capabilities=["disburse", "reconcile"],
            signature="sig_card_valid"
        )
        self.assertEqual(len(card_digest), 64)

        receipt = link.bind_delegation_to_mcp_receipt(
            upstream_agent_id="agent-eu-treasury",
            downstream_tool_name="disburse_funds",
            tool_arguments={"eur_amount": 1850000}
        )
        self.assertTrue(receipt["chain_of_custody_intact"])
        self.assertTrue(receipt["eu_ai_act_article_12_valid"])
        self.assertEqual(receipt["upstream_card_digest"], card_digest)

    def test_moat_3_normative_precedence(self):
        # INVALID_INPUT > CONFIRMED
        signals = ["CONFIRMED", "INVALID_INPUT"]
        self.assertEqual(resolve_precedence(signals), "INVALID_INPUT")

        # classify_trace forces UNKNOWN when wire_fact is TIMEOUT_504
        disposition = classify_trace(wire_fact="TIMEOUT_504", server_settled=False)
        self.assertEqual(disposition, "UNKNOWN")

    def test_moat_10_sovereign_reporter_pqc(self):
        sr = SovereignReporter(agent_did="did:smaos:prague-node-001")
        
        # Test UNKNOWN disposition mapping
        rep_unknown = sr.generate_attestation_report(
            disposition=Disposition.UNKNOWN,
            trace_id="trace-504-timeout",
            payload_hash="0xabcd1234",
            pqc_scheme=PQCScheme.ED25519_ML_DSA_65
        )
        self.assertEqual(rep_unknown["smaos_disposition"], "UNKNOWN")
        self.assertEqual(rep_unknown["pqc_readiness"]["active_scheme"], "Ed25519+ML-DSA-65-Hybrid")
        self.assertEqual(rep_unknown["jurisdiction_mappings"]["EU_DORA_AI_ACT"]["status"], "INCIDENT_TRIGGERED")
        self.assertEqual(rep_unknown["jurisdiction_mappings"]["CAICT_ATH_1_0"]["status"], "SERVICE_UNOBSERVABLE")
        self.assertEqual(rep_unknown["jurisdiction_mappings"]["US_NIST_RMF"]["status"], "UNCERTAINTY_HALT")
        self.assertIn("report_digest", rep_unknown)
        self.assertEqual(len(rep_unknown["report_digest"]), 64)

        # Test all 6 dispositions in TRIPARTITE_MAPPING
        for disp in Disposition:
            self.assertIn(disp, TRIPARTITE_MAPPING)
            self.assertIn("EU_DORA_AI_ACT", TRIPARTITE_MAPPING[disp])
            self.assertIn("CAICT_ATH_1_0", TRIPARTITE_MAPPING[disp])
            self.assertIn("US_NIST_RMF", TRIPARTITE_MAPPING[disp])

    def test_moat_10_global_audit_reporter_bundle(self):
        temp_dir = tempfile.mkdtemp()
        try:
            reporter = GlobalAuditReporter()
            findings = [
                {
                    "action_id": "test-tx-001",
                    "verdict": "VERIFIED_TOXIC_RECEIPT",
                    "model_claimed": "CONFIRMED",
                    "wire_observed": "HTTP 504 GATEWAY TIMEOUT"
                },
                {
                    "action_id": "test-tx-002",
                    "verdict": "CONFIRMED",
                    "model_claimed": "CONFIRMED",
                    "wire_observed": "HTTP 200 OK"
                }
            ]
            reporter.generate_all(findings, temp_dir)

            report_file = os.path.join(temp_dir, "dora_art17_gap_report.json")
            mermaid_file = os.path.join(temp_dir, "audit_trace.mermaid")

            self.assertTrue(os.path.exists(report_file))
            self.assertTrue(os.path.exists(mermaid_file))

            with open(report_file, "r") as f:
                data = json.load(f)
            self.assertEqual(data["jurisdiction_compliance"]["eu_dora_art17"], "COMPLIANT_CLASSIFICATION")
            self.assertEqual(data["jurisdiction_compliance"]["china_caict_ath_1_0"], "MAPPED_9_STEP")
            self.assertEqual(data["jurisdiction_compliance"]["ietf_scitt"], "RFC_9162_COMPLIANT")
            self.assertEqual(len(data["findings"]), 2)
            self.assertIn("tripartite_compliance", data["findings"][0])

            with open(mermaid_file, "r") as f:
                content = f.read()
            self.assertIn("sequenceDiagram", content)
            self.assertIn("FORCE DOWNGRADE -> UNKNOWN", content)
        finally:
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    unittest.main()
