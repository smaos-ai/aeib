"""Comprehensive Test Suite for the 8 Moats Architecture (test_moats.py)."""

import hashlib
import unittest
from datetime import datetime, timezone, timedelta

from ocr_audit.moats import (
    AttestationClosure,
    AttestationClosureSealer,
    RelyingPartySufficiencyEvaluator,
    RelyingPartyVerdict,
    GroundEvalFuzzer,
    GroundEvalScenarioType,
    SARCDataQualityGate,
    SARCQualityStatus,
    SubMillisecondVerifierBenchmark,
    EnclaveType,
    HardwareAttestationVerifier,
    ContinuousVerificationEngine,
    HandshakeDisposition,
    PreToolUseComplianceGate,
)


class TestThe8Moats(unittest.TestCase):
    """Verifies all 8 Moats in code."""

    def test_moat_1_attestation_closure(self):
        """Moat 1: Decision Reproducibility via Attestation Closure (IETF AAT draft-03)."""
        sealer = AttestationClosureSealer()
        closure = sealer.seal(
            tokenizer_data=b"mock-tokenizer-data",
            chat_template="system: you are a banking agent...",
            engine_binary_or_version="vllm-0.6.2-cuda124",
            numeric_params={"precision": "bfloat16", "seed": 42},
        )
        self.assertTrue(closure.is_valid())
        self.assertEqual(len(closure.tokenizer_digest), 64)
        self.assertEqual(len(closure.chat_template_digest), 64)
        self.assertEqual(len(closure.engine_build_digest), 64)
        self.assertEqual(len(closure.numeric_environment_digest), 64)

        # Enrichment
        raw_rcpt = {"action_id": "act-1", "verdict": "CONFIRMED"}
        enriched = sealer.enrich_receipt(raw_rcpt, closure)
        self.assertEqual(enriched["version"], "1.1.0")
        self.assertIn("attestation_closure", enriched)

    def test_moat_2_evidence_sufficiency(self):
        """Moat 2: Evidence Sufficiency (IETF EP-AEG draft-00 §4.2)."""
        evaluator = RelyingPartySufficiencyEvaluator(max_ttl_seconds=3600)
        now = datetime.now(timezone.utc)

        valid_receipt = {
            "version": "1.1.0",
            "action_id": "act-suff-001",
            "leaf_index": 0,
            "tree_size": 1,
            "timestamp": now.isoformat(),
            "intent_digest": "0" * 64,
            "verdict": "CONFIRMED",
            "root_hash": "1" * 64,
            "signature": "2" * 64,
            "signer_pubkey": "3" * 64,
            "inclusion_proof": [],
        }

        # 1. Admissible
        ev = evaluator.evaluate_receipt(valid_receipt, now_dt=now)
        self.assertEqual(ev.verdict, RelyingPartyVerdict.ADMISSIBLE)

        # 2. Missing Evidence
        missing_rcpt = dict(valid_receipt, verdict="UNKNOWN")
        ev2 = evaluator.evaluate_receipt(missing_rcpt, now_dt=now)
        self.assertEqual(ev2.verdict, RelyingPartyVerdict.MISSING_EVIDENCE)

        # 3. Conflicted
        conflict_rcpt = dict(valid_receipt, verdict="CONFLICT")
        ev3 = evaluator.evaluate_receipt(conflict_rcpt, now_dt=now)
        self.assertEqual(ev3.verdict, RelyingPartyVerdict.CONFLICTED)

        # 4. Stale
        old_time = (now - timedelta(hours=2)).isoformat()
        stale_rcpt = dict(valid_receipt, timestamp=old_time)
        ev4 = evaluator.evaluate_receipt(stale_rcpt, now_dt=now)
        self.assertEqual(ev4.verdict, RelyingPartyVerdict.STALE)

        # 5. Unverifiable
        unverifiable_rcpt = dict(valid_receipt, root_hash="short")
        ev5 = evaluator.evaluate_receipt(unverifiable_rcpt, now_dt=now)
        self.assertEqual(ev5.verdict, RelyingPartyVerdict.UNVERIFIABLE)

    def test_moat_3_ground_eval(self):
        """Moat 3: Evidence-Path Correctness via GroundEval (arXiv:2606.22737)."""
        fuzzer = GroundEvalFuzzer()

        # Silence: wire drops, agent must preserve UNKNOWN
        silence_sound = fuzzer.evaluate_silence({"action_id": "s1", "wire_status": 504, "verdict": "UNKNOWN"})
        self.assertTrue(silence_sound.is_sound)

        silence_toxic = fuzzer.evaluate_silence({"action_id": "s2", "wire_status": 504, "verdict": "CONFIRMED"})
        self.assertFalse(silence_toxic.is_sound)

        # Perspective: divergent amounts trigger conflict
        persp_res = fuzzer.evaluate_perspective(
            {"action_id": "p1", "xid": 101, "amount": 1000, "verdict": "CONFIRMED"},
            {"action_id": "p1", "xid": 101, "amount": 1050},
        )
        self.assertFalse(persp_res.is_sound)  # because claimed was CONFIRMED while ground truth was CONFLICT

        # Counterfactual: parameter skimming caught
        cf_res = fuzzer.evaluate_counterfactual(
            {"action": "transfer", "amount": 1000},
            {"action": "transfer", "amount": 1050, "disposition": "CLEAN_PASS"},
        )
        self.assertFalse(cf_res.is_sound)

    def test_moat_4_sarc_data_quality_gate(self):
        """Moat 4: Runtime Data-Quality Gating (arXiv:2607.26313)."""
        gate = SARCDataQualityGate(allowed_namespaces={"payments"})
        now = datetime.now(timezone.utc)

        # Valid
        v = gate.check_record({
            "action_id": "act-sarc-1",
            "namespace": "payments",
            "timestamp": now.isoformat(),
            "intent_digest": "a" * 64,
        }, now_dt=now)
        self.assertEqual(v.status, SARCQualityStatus.VALID)
        self.assertTrue(v.is_admissible)

        # Out of scope
        v_oos = gate.check_record({
            "action_id": "act-sarc-2",
            "namespace": "crypto_meme_token",
        }, now_dt=now)
        self.assertEqual(v_oos.status, SARCQualityStatus.OUT_OF_SCOPE)
        self.assertFalse(v_oos.is_admissible)

        # Malformed
        v_mal = gate.check_record({"action_id": "act-3", "intent_digest": "xyz"}, now_dt=now)
        self.assertEqual(v_mal.status, SARCQualityStatus.MALFORMED)

    def test_moat_5_sub_millisecond_verification(self):
        """Moat 5: Sub-Millisecond Verification Gate (draft-wang-ccs)."""
        metrics = SubMillisecondVerifierBenchmark.run_benchmark(iterations=1000)
        self.assertTrue(metrics["passed_ccs_gate_under_800ms"])
        self.assertTrue(metrics["is_sub_millisecond"])
        self.assertLess(metrics["p99_latency_ms"], 1.0)

    def test_moat_6_hardware_attestation(self):
        """Moat 6: Hardware-Rooted Attestation (IETF RATS / TPM 2.0)."""
        verifier = HardwareAttestationVerifier()

        # TPM 2.0 Quote
        rep_tpm = verifier.verify({"tpm_quote": "AAECBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA="})
        self.assertEqual(rep_tpm.enclave_type, EnclaveType.TPM_2_0)
        self.assertTrue(rep_tpm.is_valid)

        # AMD SEV-SNP
        rep_sev = verifier.verify({"sev_snp_measurement": "0123456789abcdef" * 6})
        self.assertEqual(rep_sev.enclave_type, EnclaveType.AMD_SEV_SNP)
        self.assertTrue(rep_sev.is_valid)

    def test_moat_7_continuous_verification(self):
        """Moat 7: Economic Incentive Alignment (AIGA draft-00)."""
        engine = ContinuousVerificationEngine(max_tri_threshold_pct=0.0)

        # 1. Clean event
        res1 = engine.process_trace_event({"action_id": "e1", "wire_status": 200, "verdict": "CONFIRMED"})
        self.assertEqual(res1["verdict"], "CLEAN_PASS")
        self.assertEqual(res1["running_tri_pct"], 0.0)

        # 2. Toxic event
        res2 = engine.process_trace_event({"action_id": "e2", "wire_status": 504, "verdict": "CONFIRMED"})
        self.assertEqual(res2["verdict"], "TOXIC_RECEIPT_DETECTED")
        self.assertEqual(res2["running_tri_pct"], 50.0)
        self.assertEqual(res2["sla_status"], "BREACH")

    def test_moat_8_compliance_handshake(self):
        """Moat 8: Pre-Access Compliance Handshake (ACD draft-03)."""
        gate = PreToolUseComplianceGate(
            max_transaction_amount_eur=5000.0,
            permitted_scopes={"payments:sepa:initiate"},
            enforce_attestation_closure=True,
        )

        valid_caller = {
            "scopes": ["payments:sepa:initiate"],
            "attestation_closure": {"tokenizer_digest": "a" * 64},
        }

        # 1. Authorized
        d1 = gate.negotiate(
            {"action_id": "a1", "tool_name": "sepa_transfer", "parameters": {"amount": 2500.0}},
            valid_caller,
        )
        self.assertEqual(d1.disposition, HandshakeDisposition.AUTHORIZED)
        self.assertTrue(d1.is_permitted)

        # 2. Refused Spending Ceiling
        d2 = gate.negotiate(
            {"action_id": "a2", "tool_name": "sepa_transfer", "parameters": {"amount": 7500.0}},
            valid_caller,
        )
        self.assertEqual(d2.disposition, HandshakeDisposition.REFUSED_SPENDING_CEILING)
        self.assertFalse(d2.is_permitted)

        # 3. Refused Missing Attestation
        d3 = gate.negotiate(
            {"action_id": "a3", "tool_name": "sepa_transfer", "parameters": {"amount": 100.0}},
            {"scopes": ["payments:sepa:initiate"]},
        )
        self.assertEqual(d3.disposition, HandshakeDisposition.REFUSED_MISSING_ATTESTATION)
        self.assertFalse(d3.is_permitted)


if __name__ == "__main__":
    unittest.main()
