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
pqc_signer_bridge.py — Hybrid Ed25519 + ML-DSA-65 PQC Signer Python Bridge
AEIB v0.4.0 Native Post-Quantum Signing Interface (FIPS 204 ML-DSA-65)

Bridges Python engine execution to the native Rust smaos-pqc-signer binary,
supporting persistent key stores (0600 POSIX permissions) and ephemeral execution.
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

from src.jcs_canonicalizer import encode_jcs

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BINARY = REPO_ROOT / "target" / "debug" / "smaos-pqc-signer"


def get_signer_binary_path() -> Path:
    """Resolves the compiled smaos-pqc-signer binary path."""
    if DEFAULT_BINARY.is_file():
        return DEFAULT_BINARY
    release_path = REPO_ROOT / "target" / "release" / "smaos-pqc-signer"
    if release_path.is_file():
        return release_path
    raise FileNotFoundError(
        f"smaos-pqc-signer binary not found at {DEFAULT_BINARY}. "
        "Run `cargo build --manifest-path smaos-pqc-signer/Cargo.toml` first."
    )


def sign_hybrid_envelope(
    payload: Dict[str, Any],
    key_file: Optional[Path] = None,
    binary_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Signs a canonical payload with hybrid Ed25519 and ML-DSA-65 keys.
    Returns the parsed receipt dictionary containing both signature blocks.
    Raises ValueError if self-verification fails.
    """
    bin_path = binary_path or get_signer_binary_path()
    canonical_bytes = encode_jcs(payload)
    message_str = canonical_bytes.decode("utf-8")

    cmd = [str(bin_path), message_str]
    if key_file:
        cmd.extend(["--key-file", str(key_file)])

    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    receipt = json.loads(proc.stdout)

    if not receipt.get("self_verified", False):
        raise ValueError("Hybrid PQC signature verification failed self-test.")

    return receipt
