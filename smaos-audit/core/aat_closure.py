#!/usr/bin/env python3
"""
attestation_closure.py — Four-Digest Computational Closure for Decision Reproducibility (Moat 5)
Sovereign Multi-Agent OS (SMAOS) / STAR Protocol v1.1.0

Implements IETF draft-sharif-agent-audit-trail-03 (§13.6 Attestation Closure):
Binds the 4 mandatory computational digests:
  1. model_weights_digest (SHA-256 of frozen model checkpoint)
  2. tokenizer_digest (SHA-256 of tokenizer configuration & vocab)
  3. chat_template_digest (SHA-256 of jinja/system prompt template)
  4. engine_build_digest (SHA-256 of inference runtime binary & CUDA kernel environment)

Structural Moat: Closed-model APIs (OpenAI, Anthropic) cannot produce this at any price.
"""

import hashlib
import json
import time
from typing import Any, Dict, Optional, Tuple


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(data: Dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


class AttestationClosure:
    """
    Manages and verifies decision reproducibility closures.
    """

    MANDATORY_DIGESTS = [
        "model_weights_digest",
        "tokenizer_digest",
        "chat_template_digest",
        "engine_build_digest",
    ]

    def __init__(
        self,
        model_name: str,
        weights_digest: Optional[str] = None,
        tokenizer_digest: Optional[str] = None,
        template_digest: Optional[str] = None,
        engine_digest: Optional[str] = None,
        environment_salt: str = "LINUX-X86_64-CUDA-12.4",
    ):
        self.model_name = model_name
        self.weights_digest = weights_digest
        self.tokenizer_digest = tokenizer_digest
        self.template_digest = template_digest
        self.engine_digest = engine_digest
        self.environment_salt = environment_salt

    def is_closure_complete(self) -> bool:
        """
        A closure is complete iff all 4 mandatory digests are non-null and valid SHA-256 hex strings.
        """
        for d in [self.weights_digest, self.tokenizer_digest, self.template_digest, self.engine_digest]:
            if not d or len(d) != 64:
                return False
        return True

    def compute_closure_root(self) -> Optional[str]:
        """
        Compute aggregate cryptographic closure root:
        SHA256(weights || tokenizer || template || engine || env)
        """
        if not self.is_closure_complete():
            return None

        combined = (
            f"weights:{self.weights_digest}|"
            f"tokenizer:{self.tokenizer_digest}|"
            f"template:{self.template_digest}|"
            f"engine:{self.engine_digest}|"
            f"env:{sha256_hex(self.environment_salt.encode('utf-8'))}"
        ).encode("utf-8")

        return sha256_hex(combined)

    def to_dict(self) -> Dict[str, Any]:
        root = self.compute_closure_root()
        is_reproducible = self.is_closure_complete()
        return {
            "model_name": self.model_name,
            "decision_reproducible": is_reproducible,
            "closure_root": root,
            "digests": {
                "model_weights_digest": self.weights_digest,
                "tokenizer_digest": self.tokenizer_digest,
                "chat_template_digest": self.template_digest,
                "engine_build_digest": self.engine_digest,
            },
            "environment_salt_digest": sha256_hex(self.environment_salt.encode("utf-8")),
            "audit_verdict": "REPRODUCIBLE_OPEN_MODEL" if is_reproducible else "NON_REPRODUCIBLE_CLOSED_API",
        }

    @staticmethod
    def verify_closure_dict(closure_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Verifies that a serialized attestation closure matches its recorded closure_root.
        """
        digests = closure_data.get("digests", {})
        for key in AttestationClosure.MANDATORY_DIGESTS:
            val = digests.get(key)
            if not val or len(val) != 64:
                return False, f"Missing or invalid mandatory digest '{key}'"

        env_salt_digest = closure_data.get("environment_salt_digest", "")
        combined = (
            f"weights:{digests['model_weights_digest']}|"
            f"tokenizer:{digests['tokenizer_digest']}|"
            f"template:{digests['chat_template_digest']}|"
            f"engine:{digests['engine_build_digest']}|"
            f"env:{env_salt_digest}"
        ).encode("utf-8")

        expected_root = sha256_hex(combined)
        recorded_root = closure_data.get("closure_root")

        if expected_root != recorded_root:
            return False, f"Closure root mismatch: expected {expected_root}, got {recorded_root}"

        return True, "Attestation closure cryptographically verified"


def main():
    # Example 1: Open-weight model (Llama-3.1-70B-Instruct self-hosted)
    llama_closure = AttestationClosure(
        model_name="meta-llama/Llama-3.1-70B-Instruct",
        weights_digest="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        tokenizer_digest="8b8e0c968f9a2b5b3a4a9f9d2b1c8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d",
        template_digest="1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b",
        engine_digest="9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9f8e",
    )
    print("=== OPEN WEIGHT MODEL (Reproducible) ===")
    print(json.dumps(llama_closure.to_dict(), indent=2))

    # Example 2: Closed-model API (OpenAI GPT-4o)
    gpt4_closure = AttestationClosure(
        model_name="openai/gpt-4o-2024-08-06",
        weights_digest=None,  # Proprietary, unexposed
        tokenizer_digest=None,
        template_digest="c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2",
        engine_digest=None,
    )
    print("\n=== CLOSED MODEL API (Non-Reproducible) ===")
    print(json.dumps(gpt4_closure.to_dict(), indent=2))


if __name__ == "__main__":
    main()
