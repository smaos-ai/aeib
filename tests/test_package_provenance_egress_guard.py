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
tests/test_package_provenance_egress_guard.py
================================================================================
Test suite for Dynamic Package Registry Isolation & Network Provenance Verification Gate.
Evaluated under the stated model (scaffold verifier).
Zero-mock, deterministic test assertions and mutation adequacy verification.
"""

from __future__ import annotations

import dataclasses
import pytest

from src.package_provenance_egress_guard import (
    PackageDownloadIntent,
    PackageProvenanceEgressGuard,
    ProvenanceDecision,
)


def test_package_provenance_dataclass_frozenness() -> None:
    intent = PackageDownloadIntent(
        package_name="test-pkg",
        version="1.0.0",
        source_url="https://pypi.org/simple/test-pkg/",
        sha256_digest="abc123",
        tenant_id="tenant-1",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        intent.package_name = "tampered"  # type: ignore[misc]

    with pytest.raises(dataclasses.FrozenInstanceError):
        intent.version = "2.0.0"  # type: ignore[misc]

    decision = ProvenanceDecision(
        passed=True,
        reason_code="OK",
        package_name="test_pkg",
        source_url="https://pypi.org/simple/",
        canonical_intent_digest="sha256:111",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.passed = False  # type: ignore[misc]

    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.reason_code = "HALT"  # type: ignore[misc]


def test_registry_allowlist_validation() -> None:
    guard = PackageProvenanceEgressGuard()

    # Allowed default registries
    assert guard.is_registry_allowed("https://pypi.org/simple/requests/") is True
    assert guard.is_registry_allowed("https://files.pythonhosted.org/packages/abc") is True
    assert guard.is_registry_allowed("https://repo.sovereignnexus.internal/packages/pkg-1/") is True

    # Disallowed external / rogue registries
    assert guard.is_registry_allowed("https://evil-unvetted-proxy.com/packages/") is False
    assert guard.is_registry_allowed("http://unencrypted-repo.org/simple/") is False

    # Private IP / metadata service interception
    assert guard.is_registry_allowed("http://169.254.169.254/latest/meta-data/") is False
    assert guard.is_registry_allowed("https://127.0.0.1:8080/pypi/") is False
    assert guard.is_registry_allowed("https://10.0.0.5/simple/") is False
    assert guard.is_registry_allowed("https://192.168.1.1/simple/") is False
    assert guard.is_registry_allowed("https://[::1]/simple/") is False

    # Invalid URLs & edge cases
    assert guard.is_registry_allowed("") is False
    assert guard.is_registry_allowed("   \t  ") is False
    assert guard.is_registry_allowed("ftp://pypi.org/simple/") is False
    assert guard.is_registry_allowed("mailto:user@domain.com") is False
    assert guard.is_registry_allowed("http:///no-host-path/") is False
    assert guard.is_registry_allowed("https://8.8.8.8/simple/") is False  # Public IP not in registry allowlist

    # Custom registry allowlist
    custom_guard = PackageProvenanceEgressGuard(
        verified_registry_allowlist=["https://internal.registry.corp/simple/"]
    )
    assert custom_guard.is_registry_allowed("https://internal.registry.corp/simple/pkg/") is True
    assert custom_guard.is_registry_allowed("https://pypi.org/simple/pkg/") is False

    # Custom registry allowlist with public IP (kills CMP_FLIP in private IP check)
    ip_guard = PackageProvenanceEgressGuard(
        verified_registry_allowlist=["https://93.184.216.34/packages/"]
    )
    assert ip_guard.is_registry_allowed("https://93.184.216.34/packages/pkg-1/") is True
    assert ip_guard.is_registry_allowed("https://93.184.216.35/packages/pkg-1/") is False
    assert ip_guard.is_registry_allowed("https://127.0.0.1/packages/pkg-1/") is False


def test_package_download_verification_flow() -> None:
    sbom = {
        "verified_lib==2.1.0": "sha256:deadbeef12345678",
        "crypto_tool==1.0.0": "sha256:cafe000099991111",
    }
    guard = PackageProvenanceEgressGuard(signed_sbom_hashes=sbom)

    # 1. Unauthorized registry egress
    intent_bad_reg = PackageDownloadIntent(
        package_name="verified-lib",
        version="2.1.0",
        source_url="https://rogue-proxy.com/packages/verified_lib.tar.gz",
        sha256_digest="sha256:deadbeef12345678",
        tenant_id="prod-tenant",
    )
    dec_bad_reg = guard.verify_package_download(intent_bad_reg)
    assert dec_bad_reg.passed is False
    assert dec_bad_reg.reason_code == "HALT_UNAUTHORIZED_REGISTRY_EGRESS"
    assert dec_bad_reg.package_name == "verified_lib"
    assert dec_bad_reg.canonical_intent_digest.startswith("sha256:")

    # 2. Unsigned / missing in SBOM
    intent_unsigned = PackageDownloadIntent(
        package_name="unregistered-helper",
        version="1.0.0",
        source_url="https://pypi.org/simple/unregistered-helper/",
        sha256_digest="sha256:0000111122223333",
        tenant_id="prod-tenant",
    )
    dec_unsigned = guard.verify_package_download(intent_unsigned)
    assert dec_unsigned.passed is False
    assert dec_unsigned.reason_code == "HALT_UNSIGNED_PACKAGE_DOWNLOAD"
    assert dec_unsigned.package_name == "unregistered_helper"

    # 3. Hash mismatch
    intent_tampered = PackageDownloadIntent(
        package_name="verified-lib",
        version="2.1.0",
        source_url="https://pypi.org/simple/verified-lib/",
        sha256_digest="sha256:tampered_digest_value",
        tenant_id="prod-tenant",
    )
    dec_tampered = guard.verify_package_download(intent_tampered)
    assert dec_tampered.passed is False
    assert dec_tampered.reason_code == "HALT_PACKAGE_HASH_MISMATCH"
    assert dec_tampered.package_name == "verified_lib"

    # 4. Valid provenance and verified digest
    intent_valid = PackageDownloadIntent(
        package_name="verified-lib",
        version="2.1.0",
        source_url="https://pypi.org/simple/verified-lib/",
        sha256_digest="sha256:deadbeef12345678",
        tenant_id="prod-tenant",
    )
    dec_valid = guard.verify_package_download(intent_valid)
    assert dec_valid.passed is True
    assert dec_valid.reason_code == "OK_PACKAGE_PROVENANCE_VERIFIED"
    assert dec_valid.package_name == "verified_lib"
    assert dec_valid.source_url == "https://pypi.org/simple/verified-lib/"
    assert dec_valid.canonical_intent_digest.startswith("sha256:")
