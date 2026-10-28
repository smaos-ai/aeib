#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
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
src/model_manifest_verifier.py
================================================================================
Model Manifest Verifier (Scaffold).

Evaluated under the stated model (scaffold verifier):
Binds Proof-Carrying Code (PCC) mathematically to the exact model weights/version.
If the vendor updates the model behind the API endpoint, the proof is invalidated.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class LiveModelState:
    """Represents the live model manifest and weight digest at runtime."""

    model_id: str
    manifest_hash: str  # SHA-256 of the model weights / snapshot version
    last_updated_utc: str


class ModelManifestVerifier:
    """
    Evaluates that the model executing code matches the exact pinned manifest.
    Fails closed if the vendor silently updates weights.
    """

    @staticmethod
    def verify_model_provenance(
        artifact_model_hash: str, live_model: LiveModelState
    ) -> bool:
        """
        Returns True if the live model matches the proof, False if it drifted or is empty.
        """
        if not artifact_model_hash:
            return False

        if not live_model.manifest_hash:
            return False

        if artifact_model_hash != live_model.manifest_hash:
            return False

        return True

    @staticmethod
    def compute_manifest_hash(model_weights_bytes: bytes) -> str:
        """Computes deterministic sha256 manifest hash over raw bytes."""
        return f"sha256:{hashlib.sha256(model_weights_bytes).hexdigest()}"
