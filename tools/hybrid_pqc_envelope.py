# Copyright 2026 SovereignNexus Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
tools/hybrid_pqc_envelope.py — Post-Quantum Hybrid Evidence Envelope (PQEE).

Binds an AEIB evidence statement to both:
1. Classical Ed25519 (RFC 8032) for current interoperability and low-latency verification.
2. Post-Quantum ML-DSA-65 (FIPS 204) for post-quantum signature authenticity.

Verification Rule: require_both_valid (fails if either signature fails).
Emits a formal Crypto Bill of Materials (CBOM) compliant with FIPS 204.
"""

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from src.jcs_canonicalizer import encode_jcs

SIGNER_BINARY_DEBUG = REPO_ROOT / "target" / "debug" / "smaos-pqc-signer"
SIGNER_BINARY_RELEASE = REPO_ROOT / "target" / "release" / "smaos-pqc-signer"


def get_signer_binary_path() -> Path:
    if SIGNER_BINARY_DEBUG.is_file():
        return SIGNER_BINARY_DEBUG
    if SIGNER_BINARY_RELEASE.is_file():
        return SIGNER_BINARY_RELEASE
    raise FileNotFoundError(
        f"smaos-pqc-signer binary not found at {SIGNER_BINARY_DEBUG}. "
        "Run `cargo build --manifest-path smaos-pqc-signer/Cargo.toml` first."
    )


@dataclass(frozen=True)
class HybridPqcEnvelope:
    statement_hash: str
    ed25519_public_key_hex: str
    ed25519_signature_hex: str
    mldsa65_public_key_hex: str
    mldsa65_signature_hex: str
    crypto_bill_of_materials: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statement_hash": self.statement_hash,
            "signatures": {
                "ed25519": {
                    "public_key": self.ed25519_public_key_hex,
                    "signature": self.ed25519_signature_hex,
                },
                "ml-dsa-65": {
                    "public_key": self.mldsa65_public_key_hex,
                    "signature": self.mldsa65_signature_hex,
                },
            },
            "crypto_bill_of_materials": self.crypto_bill_of_materials,
        }


class HybridPqcSigner:
    """
    Hybrid signing coordinator combining Ed25519 and ML-DSA-65 (FIPS 204).
    Invokes the native Rust smaos-pqc-signer engine.
    """

    def __init__(self, key_file: Optional[Path] = None, binary_path: Optional[Path] = None) -> None:
        self.key_file = key_file
        self.binary_path = binary_path or get_signer_binary_path()

    def sign_statement(self, statement: Dict[str, Any], ephemeral: bool = True) -> HybridPqcEnvelope:
        payload_bytes = encode_jcs(statement)
        message_str = payload_bytes.decode("utf-8")
        stmt_hash = f"sha256:{hashlib.sha256(payload_bytes).hexdigest()}"

        cmd = [str(self.binary_path)]
        if ephemeral:
            cmd.append("--ephemeral")
        elif self.key_file:
            cmd.extend(["--key-file", str(self.key_file)])
        cmd.append(message_str)

        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        raw_output = proc.stdout.strip()
        json_start = raw_output.find("{")
        if json_start == -1:
            raise ValueError(f"Failed to parse JSON output from signer: {raw_output}")

        receipt = json.loads(raw_output[json_start:])
        sigs = receipt.get("signatures", {})
        ed_data = sigs.get("ed25519", {})
        ml_data = sigs.get("ml-dsa-65", {})

        ed_pk = ed_data.get("public_key", "")
        ed_sig = ed_data.get("signature", "")
        ml_pk = ml_data.get("public_key", "")
        ml_sig = ml_data.get("signature", "")

        if not (ed_pk and ed_sig and ml_pk and ml_sig):
            raise ValueError("Incomplete signature envelope received from signer")

        cbom = {
            "signature_scheme": "hybrid-ed25519-mldsa65-v1",
            "classical_algorithm": "Ed25519",
            "pqc_algorithm": "ML-DSA-65",
            "pqc_standard": "FIPS 204",
            "pqc_implementation": "RustCrypto/ml-dsa-v0.1.1",
            "verification_policy": "require_both_valid",
            "serialization_format": "rfc8785_jcs",
            "statement_hash": stmt_hash,
        }

        return HybridPqcEnvelope(
            statement_hash=stmt_hash,
            ed25519_public_key_hex=ed_pk,
            ed25519_signature_hex=ed_sig,
            mldsa65_public_key_hex=ml_pk,
            mldsa65_signature_hex=ml_sig,
            crypto_bill_of_materials=cbom,
        )

    @staticmethod
    def verify_envelope(
        statement: Dict[str, Any],
        env: HybridPqcEnvelope,
        binary_path: Optional[Path] = None,
    ) -> bool:
        """
        Verifies both classical Ed25519 and ML-DSA-65 (FIPS 204) signatures.
        Enforces require_both_valid policy.
        """
        payload_bytes = encode_jcs(statement)
        message_str = payload_bytes.decode("utf-8")

        # 1. Classical verification in Python using cryptography.hazmat
        try:
            ed_pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(env.ed25519_public_key_hex))
            ed_sig = bytes.fromhex(env.ed25519_signature_hex)
            ed_pub.verify(ed_sig, payload_bytes)
        except Exception:
            return False

        # 2. Both signatures verification via native FIPS 204 verifier
        bin_path = binary_path or get_signer_binary_path()
        cmd = [
            str(bin_path),
            "--verify-hybrid",
            env.ed25519_public_key_hex,
            env.ed25519_signature_hex,
            env.mldsa65_public_key_hex,
            env.mldsa65_signature_hex,
            message_str,
        ]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                return False
            result = json.loads(proc.stdout.strip())
            return bool(result.get("verified", False))
        except Exception:
            return False
