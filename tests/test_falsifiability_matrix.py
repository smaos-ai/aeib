import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ocr-audit-engine" / "src"))
"""Falsifiability & Non-Mock Verification Test Suite (test_falsifiability.py).

Explicitly validates the 5 verification criteria proving the code executes
real computational logic with zero mock stubs:
  1. dispatcher.py: Line counts and byte offsets shift dynamically.
  2. bundler.py: Timestamp shifts of ±10s dynamically split bundles.
  3. reflector.py: HTTP 200 + unique_xid==1 dynamically rejects false positives.
  4. attestation_and_sufficiency.py: Expired TTL -> STALE, jcs_match=False -> UNVERIFIABLE.
  5. core_proof_engine.py: 1-char mutation alters SHA-256 digest and triggers audit failure.
"""

import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ed25519

from ocr_audit.dispatcher import DeterministicDispatcher, TraceRecord
from ocr_audit.bundler import ActionBundle, SmartActionBundler
from ocr_audit.reflector import WireTruthReflector
from ocr_audit.interrogator import CandidateFinding
from ocr_audit.attestation_and_sufficiency import (
    AttestationAndSufficiencyEvaluator,
    RelyingPartyVerdict,
)
from ocr_audit.core_proof_engine import (
    CoreProofEngine,
    ERR_SUCCESS,
    ERR_MERKLE_PROOF_MISMATCH,
    ERR_SIGNATURE_INVALID,
    rfc9162_hash_leaf,
)


class TestFalsifiabilityMatrix(unittest.TestCase):
    """Verifies that each component runs genuine computational algorithms."""

    def test_1_dispatcher_dynamic_byte_offsets(self):
        """Proof: Byte offsets and line numbers shift dynamically based on content length."""
        # Create two JSONL files with different record lengths
        with tempfile.TemporaryDirectory() as tmpdir:
            file_a = Path(tmpdir) / "trace_short.jsonl"
            file_b = Path(tmpdir) / "trace_long.jsonl"

            # File A: short records
            line1_a = '{"action_id": "a1", "is_mutating": true}\n'
            line2_a = '{"action_id": "a2", "is_mutating": true}\n'
            file_a.write_text(line1_a + line2_a, encoding="utf-8")

            # File B: long records with multiline UTF-8 text
            line1_b = '{"action_id": "b1_extended_description_€€€", "is_mutating": true, "padding": "0000000000000000"}\n'
            line2_b = '{"action_id": "b2", "is_mutating": true}\n'
            file_b.write_text(line1_b + line2_b, encoding="utf-8")

            traces_a = DeterministicDispatcher.load_jsonl(file_a)
            traces_b = DeterministicDispatcher.load_jsonl(file_b)

            self.assertEqual(len(traces_a), 2)
            self.assertEqual(len(traces_b), 2)

            # Offset 0 is identical for first lines
            self.assertEqual(traces_a[0].byte_offset, 0)
            self.assertEqual(traces_b[0].byte_offset, 0)

            # Offset for second line must differ dynamically based on first line byte length
            len_line1_a = len(line1_a.encode("utf-8"))
            len_line1_b = len(line1_b.encode("utf-8"))

            self.assertEqual(traces_a[1].byte_offset, len_line1_a)
            self.assertEqual(traces_b[1].byte_offset, len_line1_b)
            self.assertNotEqual(traces_a[1].byte_offset, traces_b[1].byte_offset)

    def test_2_bundler_dynamic_cascade_splitting(self):
        """Proof: Shifting timestamps by ±10s dynamically splits events into distinct bundles."""
        bundler = SmartActionBundler(window_seconds=5.0)
        base_time = datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)

        # Case A: Two events within 2 seconds -> Grouped into 1 bundle
        t1 = TraceRecord.from_line(
            json.dumps({"action_id": "act-c1", "timestamp": base_time.isoformat(), "is_mutating": True}),
            line_no=1, byte_offset=0
        )
        t2_close = TraceRecord.from_line(
            json.dumps({"action_id": "act-c1", "timestamp": (base_time + timedelta(seconds=2)).isoformat(), "is_mutating": True}),
            line_no=2, byte_offset=50
        )

        bundles_close = bundler.bundle([t1, t2_close])
        self.assertEqual(len(bundles_close), 1)
        self.assertEqual(len(bundles_close[0].traces), 2)

        # Case B: Second event shifted by +12s (outside ±5s window) -> 2 distinct bundles
        t2_far = TraceRecord.from_line(
            json.dumps({"action_id": "act-c2", "account_id": "acc-1", "timestamp": (base_time + timedelta(seconds=12)).isoformat(), "is_mutating": True}),
            line_no=3, byte_offset=100
        )
        t1_actor = TraceRecord.from_line(
            json.dumps({"action_id": "act-c1", "account_id": "acc-1", "timestamp": base_time.isoformat(), "is_mutating": True}),
            line_no=1, byte_offset=0
        )

        bundles_split = bundler.bundle([t1_actor, t2_far])
        self.assertEqual(len(bundles_split), 2)
        self.assertEqual(bundles_split[0].action_id, "act-c1")
        self.assertEqual(bundles_split[1].action_id, "act-c2")

    def test_3_reflector_wire_facts_override(self):
        """Proof: Wire facts (HTTP 200 + xid==1) dynamically discard false positive alarms."""
        reflector = WireTruthReflector()

        bundle = ActionBundle(
            bundle_id="b-1",
            action_id="act-ref-1",
            idempotency_key="key-1",
        )
        # Wire facts confirm atomic single settlement
        bundle.wire_facts = {
            "unique_commit_xid_count": 1,
            "http_statuses": [200],
            "has_wire_fault": False,
        }

        finding = CandidateFinding(
            finding_id="f-001",
            severity="HIGH",
            category="DOUBLE_EXECUTION_RISK",
            action_id="act-ref-1",
            claimed_verdict="CONFIRMED",
            rationale="Model guessed double execution on retry",
            proposed_remediation="Freeze ledger",
        )

        # Ground truth overrides model: Must be rejected
        is_valid, reason = reflector.verify(finding, bundle)
        self.assertFalse(is_valid)
        self.assertIn("single unique commit XID", reason)

        # If xid was 2 (true double spend), finding MUST be verified as valid
        bundle.wire_facts["unique_commit_xid_count"] = 2
        is_valid_double, reason2 = reflector.verify(finding, bundle)
        self.assertTrue(is_valid_double)

    def test_4_attestation_and_sufficiency(self):
        """Proof: Older than ttl -> STALE; jcs_match=False -> UNVERIFIABLE."""
        evaluator = AttestationAndSufficiencyEvaluator(ttl_seconds=1800.0) # 30 min
        now = datetime.now(timezone.utc)

        # Event older than 30 minutes -> STALE
        stale_event = {
            "action_id": "act-stale-01",
            "timestamp": (now - timedelta(seconds=2000)).isoformat(),
            "verdict": "CONFIRMED",
            "jcs_match": True,
        }
        res_stale = evaluator.evaluate_event(stale_event, now_dt=now)
        self.assertEqual(res_stale.verdict, RelyingPartyVerdict.STALE)

        # Event with jcs_match = False -> UNVERIFIABLE
        tampered_event = {
            "action_id": "act-tampered-01",
            "timestamp": now.isoformat(),
            "verdict": "CONFIRMED",
            "jcs_match": False,
        }
        res_tampered = evaluator.evaluate_event(tampered_event, now_dt=now)
        self.assertEqual(res_tampered.verdict, RelyingPartyVerdict.UNVERIFIABLE)

    def test_5_core_proof_engine_single_char_mutation_failure(self):
        """Proof: Mutating 1 single character immediately alters Merkle root / JCS and fails audit."""
        # 1. Setup valid cryptographic key and receipt
        priv = ed25519.Ed25519PrivateKey.generate()
        pub = priv.public_key()
        pub_hex = pub.public_bytes_raw().hex()

        action_id = "act-crypto-001"
        intent_hex = "44" * 32
        verdict = "CONFIRMED"
        ts = "2026-09-18T18:00:00Z"

        leaf_content = action_id.encode("utf-8") + bytes.fromhex(intent_hex) + verdict.encode("utf-8")
        root_bytes = rfc9162_hash_leaf(leaf_content)
        root_hex = root_bytes.hex()

        # Sign
        signed_msg = root_bytes + action_id.encode("utf-8") + verdict.encode("utf-8") + ts.encode("utf-8")
        sig_bytes = priv.sign(signed_msg)
        sig_hex = sig_bytes.hex()

        valid_receipt = {
            "version": "1.1.0",
            "action_id": action_id,
            "leaf_index": 0,
            "tree_size": 1,
            "timestamp": ts,
            "intent_digest": intent_hex,
            "verdict": verdict,
            "root_hash": root_hex,
            "inclusion_proof": [],
            "signature": sig_hex,
            "signer_pubkey": pub_hex,
        }

        # Clean receipt MUST pass
        clean_res = CoreProofEngine.verify_receipt(valid_receipt)
        self.assertTrue(clean_res.is_valid)
        self.assertEqual(clean_res.status_code, ERR_SUCCESS)

        # Mutate single character in action_id: "act-crypto-001" -> "act-crypto-002"
        mutated_action = dict(valid_receipt, action_id="act-crypto-002")
        mutated_res = CoreProofEngine.verify_receipt(mutated_action)
        self.assertFalse(mutated_res.is_valid)
        self.assertEqual(mutated_res.status_code, ERR_MERKLE_PROOF_MISMATCH)

        # Mutate single character in intent_digest: "444..." -> "544..."
        mutated_intent = dict(valid_receipt, intent_digest="5" + intent_hex[1:])
        intent_res = CoreProofEngine.verify_receipt(mutated_intent)
        self.assertFalse(intent_res.is_valid)
        self.assertEqual(intent_res.status_code, ERR_MERKLE_PROOF_MISMATCH)

        # Mutate single character in signature
        mutated_sig = dict(valid_receipt, signature="ff" + sig_hex[2:])
        sig_res = CoreProofEngine.verify_receipt(mutated_sig)
        self.assertFalse(sig_res.is_valid)
        self.assertEqual(sig_res.status_code, ERR_SIGNATURE_INVALID)


if __name__ == "__main__":
    unittest.main()
