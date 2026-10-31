#!/usr/bin/env python3
"""
Unit tests for Research OS Provenance Engine, Verifier, and PDF Ingestion.
Tests RFC 8785 JCS canonicalization, RFC 9052 COSE_Sign1 verification,
hash chain continuity, and schema compliance.
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from pathlib import Path

# Add src and scripts to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))

from crypto_logger import ProvenanceLogger
from verify import verify_single_receipt, verify_receipts_in_path, load_public_key
from ingest_pdf import ingest_and_seal_pdf


class TestProvenanceEngine(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.key_dir = os.path.join(self.test_dir, "keys")
        os.makedirs(self.key_dir, exist_ok=True)
        self.priv_key = os.path.join(self.key_dir, "ed25519-private.pem")
        self.pub_key = os.path.join(self.key_dir, "ed25519-public.pem")
        self.receipts_dir = os.path.join(self.test_dir, "receipts")
        self.merkle_file = os.path.join(self.test_dir, "merkle_root.txt")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_schema_conformance(self):
        """Verify that published receipts conform to aeib_receipt_v1.json schema requirements."""
        schema_path = Path("provenance/schemas/aeib_receipt_v1.json")
        self.assertTrue(schema_path.exists(), "Schema file must exist")
        schema = json.loads(schema_path.read_text())

        receipt_files = list(Path("provenance/receipts").glob("*.json"))
        self.assertGreater(len(receipt_files), 0, "Must have at least one receipt in provenance/receipts")

        for r_file in receipt_files:
            data = json.loads(r_file.read_text())
            for req in schema["required"]:
                self.assertIn(req, data, f"Missing required field {req} in {r_file.name}")
            self.assertIn(data["receipt_version"], schema["properties"]["receipt_version"]["enum"])
            self.assertIn(data["disposition"], schema["properties"]["disposition"]["enum"])
            self.assertEqual(data["cose_alg"], -8)
            self.assertEqual(len(data["head_hash"]), 64)
            self.assertEqual(len(data["previous_hash"]), 64)

    def test_02_logger_emission_and_verification(self):
        """Test receipt generation, COSE_Sign1 signing, and verification."""
        logger = ProvenanceLogger(
            private_key_path=self.priv_key,
            log_dir=self.receipts_dir,
            merkle_file=self.merkle_file
        )
        pubkey = load_public_key(Path(self.pub_key))

        payload1 = {
            "research_session_id": "rs_20260929_1000000001",
            "query": "What is the DORA initial notification deadline?",
            "answer": "4 hours from classification, 24 hours from awareness.",
            "sources": [{"url": "https://example.com/dora", "content_hash": "a" * 64, "engine": "test"}],
            "disposition": "OUTCOME_VERIFIED"
        }
        r1 = logger.emit_receipt(payload1)

        # Verify receipt 1
        valid, errs = verify_single_receipt(r1, pubkey)
        self.assertTrue(valid, f"Receipt 1 failed verification: {errs}")
        self.assertEqual(len(errs), 0)

        # Emit receipt 2 and verify hash-chain continuity
        payload2 = {
            "research_session_id": "rs_20260929_1000000002",
            "query": "What is the Czech AI Sandbox budget?",
            "answer": "232M CZK for 2026-2028 program.",
            "sources": [{"url": "https://example.com/czech", "content_hash": "b" * 64, "engine": "test"}],
            "disposition": "OUTCOME_VERIFIED"
        }
        r2 = logger.emit_receipt(payload2)

        # Check chain link
        self.assertEqual(r2["previous_hash"], r1["head_hash"])

        # Verify receipt 2 with expected previous head
        valid2, errs2 = verify_single_receipt(r2, pubkey, expected_prev_hash=r1["head_hash"])
        self.assertTrue(valid2, f"Receipt 2 failed verification: {errs2}")

        # Verify entire directory
        dir_valid = verify_receipts_in_path(Path(self.receipts_dir), Path(self.pub_key), Path(self.merkle_file))
        self.assertTrue(dir_valid)

    def test_03_tamper_detection_payload(self):
        """Tampering with query or answer must trigger verification failure."""
        logger = ProvenanceLogger(
            private_key_path=self.priv_key,
            log_dir=self.receipts_dir,
            merkle_file=self.merkle_file
        )
        pubkey = load_public_key(Path(self.pub_key))

        r = logger.emit_receipt({
            "research_session_id": "rs_20260929_1000000003",
            "query": "Legitimate query",
            "answer": "Legitimate answer",
            "sources": [],
            "disposition": "OUTCOME_VERIFIED"
        })

        # Tamper with answer_preview
        tampered = dict(r)
        tampered["answer_preview"] = "Tampered / falsified answer"

        valid, errs = verify_single_receipt(tampered, pubkey)
        self.assertFalse(valid, "Tampered receipt should fail verification")
        self.assertTrue(any("mismatch" in e.lower() or "failed" in e.lower() for e in errs))

    def test_04_tamper_detection_signature(self):
        """Corrupted signature envelope must fail cryptographic verification."""
        logger = ProvenanceLogger(
            private_key_path=self.priv_key,
            log_dir=self.receipts_dir,
            merkle_file=self.merkle_file
        )
        pubkey = load_public_key(Path(self.pub_key))

        r = logger.emit_receipt({
            "research_session_id": "rs_20260929_1000000004",
            "query": "Test query",
            "answer": "Test answer",
            "sources": [],
            "disposition": "OUTCOME_VERIFIED"
        })

        # Corrupt envelope hex by flipping the last byte
        corrupted = dict(r)
        orig_hex = corrupted["cose_envelope_hex"]
        flipped_byte = "00" if orig_hex[-2:] != "00" else "ff"
        corrupted["cose_envelope_hex"] = orig_hex[:-2] + flipped_byte

        valid, errs = verify_single_receipt(corrupted, pubkey)
        self.assertFalse(valid, "Corrupted COSE envelope should fail verification")

    def test_05_tamper_detection_hash_chain(self):
        """Altering previous_hash must fail chain verification."""
        logger = ProvenanceLogger(
            private_key_path=self.priv_key,
            log_dir=self.receipts_dir,
            merkle_file=self.merkle_file
        )
        pubkey = load_public_key(Path(self.pub_key))

        r = logger.emit_receipt({
            "research_session_id": "rs_20260929_1000000005",
            "query": "Test query",
            "answer": "Test answer",
            "sources": [],
            "disposition": "OUTCOME_VERIFIED"
        })

        # Assert with mismatched expected_prev_hash
        valid, errs = verify_single_receipt(r, pubkey, expected_prev_hash="0" * 64)
        self.assertFalse(valid)
        self.assertTrue(any("Hash chain break" in e for e in errs))

    def test_06_pdf_ingestion(self):
        """Test document ingestion, claim hashing, and receipt emission."""
        doc_file = Path(self.test_dir) / "test_doc.txt"
        doc_file.write_text(
            "Title: DORA Regulatory Standard\n\n"
            "This is paragraph one containing statutory guidance on operational resilience.\n\n"
            "This is paragraph two detailing the 4-hour classification clock requirement.\n"
        )

        res = ingest_and_seal_pdf(
            pdf_path=str(doc_file),
            query_context="Test Document Ingestion",
            log_dir=self.receipts_dir,
            key_path=self.priv_key
        )

        self.assertEqual(res["status"], "INGESTED")
        self.assertGreater(res["total_claims_extracted"], 0)
        self.assertEqual(len(res["document_sha256"]), 64)
        self.assertEqual(res["receipt"]["disposition"], "OUTCOME_VERIFIED")

        pubkey = load_public_key(Path(self.pub_key))
        valid, errs = verify_single_receipt(res["receipt"], pubkey)
        self.assertTrue(valid, f"Ingested receipt must verify cleanly: {errs}")

    def test_07_sovereign_search_and_retrieval(self):
        """Test SearxNGClient, SovereignAcademicRetriever, and SovereignSynthesisEngine."""
        from sovereign_search import SearxNGClient, SovereignAcademicRetriever, SovereignSynthesisEngine

        web = SearxNGClient()
        w_res = web.search("latest EU AI Act Annex III deferral details and DORA Article 17 reporting thresholds")
        self.assertGreater(len(w_res), 0)
        self.assertTrue(any("CELEX:32026R1744" in r["url"] or "CELEX:32025R0301" in r["url"] for r in w_res))

        acad = SovereignAcademicRetriever()
        a_res = acad.search("DORA operational resilience")
        self.assertGreater(len(a_res), 0)

        synth = SovereignSynthesisEngine()
        summary = synth.synthesize("latest EU AI Act Annex III deferral details and DORA Article 17 reporting thresholds", w_res + a_res)
        self.assertIn("AI Act Annex III Deferral", summary)
        self.assertIn("December 2, 2027", summary)
        self.assertIn("DORA Article 17 Reporting", summary)

    def test_08_sovereign_olap_querying(self):
        """Test SovereignOLAP in-process SQL execution over receipts."""
        from sovereign_search import SovereignOLAP

        stats = SovereignOLAP.get_summary_stats()
        self.assertIn("total_receipts", stats)
        self.assertGreaterEqual(stats["total_receipts"], 1)

        result = SovereignOLAP.query("SELECT count() FROM __RECEIPTS__")
        self.assertIsNotNone(result)

    def test_09_health_check_execution(self):
        """Test health_check diagnostic execution."""
        import subprocess
        res = subprocess.run([sys.executable, "scripts/health_check.py"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("PRE-FLIGHT CHECK COMPLETE", res.stdout)

    def test_10_vision_research_execution(self):
        """Test vision_research.py with screenshot hashing and receipt minting."""
        from vision_research import run_vision_research
        test_img = Path("01-home.png")
        if test_img.exists():
            receipt = run_vision_research(str(test_img))
            self.assertEqual(receipt["disposition"], "OUTCOME_VERIFIED")
            self.assertIn("source_image_hash", receipt)
            self.assertEqual(len(receipt["source_image_hash"]), 64)
            self.assertTrue(receipt["research_session_id"].startswith("rs_img_"))


if __name__ == "__main__":
    unittest.main()


