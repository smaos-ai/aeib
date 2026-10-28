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
tests/test_model_manifest_verifier.py
================================================================================
Verification & Falsification Suite for ModelManifestVerifier.
"""

from __future__ import annotations

import dataclasses
import hashlib
import pytest

from src.model_manifest_verifier import (
    LiveModelState,
    ModelManifestVerifier,
)


def test_matching_manifest_verifies_provenance() -> None:
    raw_weights = b"opus_weights_v5_5_mock_blob_12345"
    expected_digest = f"sha256:{hashlib.sha256(raw_weights).hexdigest()}"

    live_state = LiveModelState(
        model_id="claude-opus-5.5",
        manifest_hash=expected_digest,
        last_updated_utc="2026-10-27T00:00:00Z",
    )

    is_valid = ModelManifestVerifier.verify_model_provenance(expected_digest, live_state)
    assert is_valid is True


def test_weight_drift_fails_provenance() -> None:
    live_state = LiveModelState(
        model_id="claude-opus-5.5",
        manifest_hash="sha256:weights_v2_stealth_update",
        last_updated_utc="2026-10-27T00:00:00Z",
    )
    old_digest = "sha256:weights_v1"

    is_valid = ModelManifestVerifier.verify_model_provenance(old_digest, live_state)
    assert is_valid is False


def test_empty_hashes_fail_closed() -> None:
    live_state = LiveModelState(
        model_id="claude-opus-5.5",
        manifest_hash="sha256:valid_hash",
        last_updated_utc="2026-10-27T00:00:00Z",
    )

    assert ModelManifestVerifier.verify_model_provenance("", live_state) is False

    empty_live = LiveModelState(
        model_id="claude-opus-5.5",
        manifest_hash="",
        last_updated_utc="2026-10-27T00:00:00Z",
    )
    assert ModelManifestVerifier.verify_model_provenance("sha256:valid_hash", empty_live) is False


def test_compute_manifest_hash() -> None:
    data = b"deterministic_weight_bytes_sample"
    digest = ModelManifestVerifier.compute_manifest_hash(data)
    assert digest.startswith("sha256:")
    assert digest == f"sha256:{hashlib.sha256(data).hexdigest()}"


def test_live_model_state_frozen_immutability() -> None:
    state = LiveModelState(
        model_id="model-1",
        manifest_hash="sha256:abc",
        last_updated_utc="2026-10-27T12:00:00Z",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.model_id = "mutated"  # type: ignore
