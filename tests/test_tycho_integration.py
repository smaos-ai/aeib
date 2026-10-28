import tempfile
import os
import unittest
from src.aeib_v040_engine import (
    AEIB040Pipeline,
    ImmutableFactViolationError,
    AuthorityViolationError,
    StructuralVerificationError,
)
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from src.jcs_canonicalizer import encode_jcs


class TestTychoIntegration(unittest.TestCase):
    def setUp(self):
        self.engine = AEIB040Pipeline(enforce_tycho=True)

    def test_tycho_intercepts_failed(self):
        result = self.engine.execute_flow(
            noun="file",
            verb="write",
            payload={"path": "test.txt", "content": "hello"},
            transport_observation="HTTP_200_OK",
            transport_status_code=200,
            tycho_verdict="FAILED"
        )
        attrs = result["attributes"]
        self.assertEqual(attrs["aeib.disposition"], "STRUCTURAL_VERIFICATION_FAILED")
        self.assertEqual(attrs["aeib.retry_safe"], False)
        self.assertEqual(attrs["aeib.mapping_rule_id"], "RULE-TYCHO-INTERCEPT")

    def test_tycho_verified_allows_success(self):
        result = self.engine.execute_flow(
            noun="file",
            verb="write",
            payload={"path": "test.txt", "content": "hello"},
            transport_observation="HTTP_200_OK",
            transport_status_code=200,
            tycho_verdict="VERIFIED"
        )
        attrs = result["attributes"]
        self.assertEqual(attrs["aeib.disposition"], "OUTCOME_VERIFIED")
        self.assertEqual(attrs["aeib.retry_safe"], False)

    def test_tycho_missing_verdict_fails_closed(self):
        """When the YAML contract was never evaluated, execution halts with a
        STRUCTURAL_VERIFICATION_FAILED error: no receipt is signed and the
        ANSI 86 latch for the CAID stays engaged."""
        flow_args = dict(
            noun="file",
            verb="write",
            payload={"path": "test.txt", "content": "hello"},
            transport_observation="HTTP_200_OK",
            transport_status_code=200,
            tycho_verdict=None,
        )

        with self.assertRaises(StructuralVerificationError) as ctx:
            self.engine.execute_flow(**flow_args)
        self.assertIn("STRUCTURAL_VERIFICATION_FAILED", str(ctx.exception))

        # The latch engaged before the halt: the CAID is now locked out.
        with self.assertRaises(RuntimeError):
            self.engine.execute_flow(**flow_args)

    def test_tycho_un_evaluated_contract_halts(self):
        """A non-string verdict (un-evaluated YAML contract object) halts execution."""
        un_evaluated_contract = {"gates": [{"rule": "file_exists"}], "evaluated": False}

        with self.assertRaises(StructuralVerificationError):
            self.engine.execute_flow(
                noun="ledger",
                verb="commit",
                payload={"amount": 1},
                transport_observation="HTTP_200_OK",
                transport_status_code=200,
                tycho_verdict=un_evaluated_contract,
            )

        # Unknown verdict vocabulary is also treated as un-evaluated (fail-closed).
        for verdict in ("", "   ", "NOT_EVALUATED", "PENDING"):
            with self.assertRaises(StructuralVerificationError):
                self.engine.execute_flow(
                    noun="ledger",
                    verb="credit",
                    payload={"amount": 1, "verdict_probe": verdict},
                    transport_observation="HTTP_200_OK",
                    transport_status_code=200,
                    tycho_verdict=verdict,
                )

    def test_tycho_gate_has_no_bypass_switch(self):
        """enforce_tycho=False is rejected: the gate has no fail-open path."""
        with self.assertRaises(ValueError):
            AEIB040Pipeline(enforce_tycho=False)

    def test_tycho_stale_and_indeterminate(self):
        result_stale = self.engine.execute_flow(
            noun="file",
            verb="write",
            payload={"path": "test_stale.txt"},
            transport_observation="HTTP_200_OK",
            transport_status_code=200,
            tycho_verdict="STALE"
        )
        self.assertEqual(result_stale["attributes"]["aeib.disposition"], "STRUCTURAL_VERIFICATION_STALE")
        self.assertEqual(result_stale["attributes"]["aeib.retry_safe"], False)

        result_ind = self.engine.execute_flow(
            noun="file",
            verb="write",
            payload={"path": "test_ind.txt"},
            transport_observation="HTTP_200_OK",
            transport_status_code=200,
            tycho_verdict="INDETERMINATE"
        )
        self.assertEqual(result_ind["attributes"]["aeib.disposition"], "STRUCTURAL_VERIFICATION_INDETERMINATE")
        self.assertEqual(result_ind["attributes"]["aeib.retry_safe"], False)

    def test_dynamic_signature_verification(self):
        """Ensures receipt signature is genuinely verified and valid against public key."""
        result = self.engine.execute_flow(
            noun="file",
            verb="write",
            payload={"path": "test_sig.txt", "amount": 100},
            transport_observation="HTTP_200_OK",
            transport_status_code=200,
            tycho_verdict="VERIFIED"
        )
        attrs = result["attributes"]
        self.assertTrue(attrs["aeib.receipt.verified"])

        # Cryptographically verify outside engine
        sig_bytes = bytes.fromhex(attrs["aeib.receipt.signature"])
        pk_bytes = bytes.fromhex(attrs["aeib.receipt.public_key_hex"])
        pubkey = Ed25519PublicKey.from_public_bytes(pk_bytes)

        # Reconstruct canonical signed payload
        l8_keys = {
            "aeib.receipt.signature",
            "aeib.receipt.public_key_hex",
            "aeib.receipt.jcs_payload_hash",
            "aeib.receipt.verified",
            "aeib.release_authorization"
        }
        signed_body = {k: v for k, v in attrs.items() if k not in l8_keys}
        signed_body["aeib.release_authorization"] = "not_provided"

        pubkey.verify(sig_bytes, encode_jcs(signed_body))

    def test_key_persistence(self):
        """Ensures signing keys can be persisted and reloaded from disk with 0600 permissions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = os.path.join(tmpdir, "signing_key.pem")
            engine1 = AEIB040Pipeline(key_path=key_path)
            pk1 = engine1.public_key_hex

            # Ensure file created with 0600 permissions
            mode = oct(os.stat(key_path).st_mode)[-3:]
            self.assertEqual(mode, "600")

            # Load into second engine instance
            engine2 = AEIB040Pipeline(key_path=key_path)
            self.assertEqual(engine2.public_key_hex, pk1)


    def test_native_tycho_gate_execution(self):
        """Validates that verify_agent_state_gate checks real repo artifacts."""
        from compliance.tycho_verifier import verify_agent_state_gate, TychoVerdict
        result = verify_agent_state_gate()
        self.assertEqual(result.verdict, TychoVerdict.VERIFIED)
        self.assertIn("Cargo.lock", result.reason)

    def test_native_tycho_gate_missing_file_fails(self):
        """Ensures that missing required gate files fail closed."""
        from compliance.tycho_verifier import verify_agent_state_gate, TychoVerdict
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".yaml") as f:
            f.write('gates:\n  - constraints:\n      - rule: "file_exists"\n        path: "nonexistent_file.py"\n')
            f.flush()
            result = verify_agent_state_gate(gate_yaml_path=f.name)
            self.assertEqual(result.verdict, TychoVerdict.FAILED)


if __name__ == "__main__":
    unittest.main()
