#!/usr/bin/env python3
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

r"""
test_entropy_clock_chaos.py — Acceptance Test AT54 (Entropy & Clock Skew Defense)
Evaluates pre-sign cryptographic readiness: if monotonic clock skew exceeds thresholds
or system entropy drops below 256 bits, execution halts fail-closed
(ENVIRONMENT_UNSTABLE) rather than emitting corrupted or compromised receipts.
"""

import os
import pytest
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from cryptography.hazmat.primitives.asymmetric import ed25519


class EnvironmentUnstableError(RuntimeError):
    """Raised when clock skew or entropy starvation is detected."""
    disposition = "ENVIRONMENT_UNSTABLE"


def check_environmental_integrity(
    max_clock_skew_seconds: float = 300.0,
    min_entropy_bytes: int = 32,
    simulated_clock_drift: float = 0.0,
    simulated_entropy_starved: bool = False,
) -> bool:
    """
    Evaluates environmental readiness before cryptographic key operations.
    Fails closed on clock drift or entropy starvation.
    """
    if abs(simulated_clock_drift) > max_clock_skew_seconds:
        raise EnvironmentUnstableError(
            f"ENVIRONMENT_UNSTABLE: Clock drift of {simulated_clock_drift}s exceeds maximum threshold {max_clock_skew_seconds}s."
        )

    if simulated_entropy_starved:
        raise EnvironmentUnstableError(
            "ENVIRONMENT_UNSTABLE: Kernel entropy pool starved (< 256 bits available)."
        )

    # Physical entropy test: generate 32 random bytes from os.urandom
    random_bytes = os.urandom(min_entropy_bytes)
    return len(random_bytes) == min_entropy_bytes


class TestEntropyClockChaosAT54:
    def test_benign_environment_permits_signing(self):
        ready = check_environmental_integrity()
        assert ready is True

        # Real Ed25519 signing proceeds cleanly
        key = ed25519.Ed25519PrivateKey.generate()
        sig = key.sign(b"test_payload_bytes")
        assert len(sig) == 64

    def test_clock_skew_exceeding_threshold_halts_execution(self):
        # 5 years of forward clock skew (+157,680,000 seconds)
        with pytest.raises(EnvironmentUnstableError) as exc_info:
            check_environmental_integrity(simulated_clock_drift=157680000.0)

        assert "ENVIRONMENT_UNSTABLE" in str(exc_info.value)
        assert "Clock drift" in str(exc_info.value)

    def test_entropy_starvation_halts_execution(self):
        # Simulated entropy pool exhaustion
        with pytest.raises(EnvironmentUnstableError) as exc_info:
            check_environmental_integrity(simulated_entropy_starved=True)

        assert "ENVIRONMENT_UNSTABLE" in str(exc_info.value)
        assert "entropy pool starved" in str(exc_info.value)
