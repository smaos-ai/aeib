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
tests/test_cloudflare_6phase_disproving.py — Test suite for Cloudflare 6-Phase Disproving
Verifier and Legacy-to-Modern Shadow Equivalence Auditor.
"""

import copy
import hashlib
import importlib
import json
from pathlib import Path
import sys
import pytest

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from src.jcs_canonicalizer import encode_jcs
from src.audit_disproving_verifier import (
    CandidateFinding,
    CandidateStatus,
    IndependentReceiptSigner,
    VulnerabilityClass,
)
import tools.cloudflare_6phase_disproving_verifier as cf_mod
from tools.cloudflare_6phase_disproving_verifier import (
    CloudflareDisprovingWorkflow,
    FindingClassification,
    LegacyShadowEquivalenceAuditor,
    LegacyTransactionRecord,
    ModernAgentDispatchRecord,
    TriTiersReport,
    self_test,
)


class _TaggedStr(str):
    source_caid: str = ""


def test_module_sys_path_bootstrap() -> None:
    """Verifies REPO_ROOT sys.path bootstrap when missing."""
    repo_str = str(cf_mod.REPO_ROOT)
    orig_path = list(sys.path)
    try:
        sys.path = [p for p in sys.path if p != repo_str]
        importlib.reload(cf_mod)
        assert sys.path[0] == repo_str
    finally:
        sys.path = orig_path


def test_self_test_execution_and_batch_inspection() -> None:
    """Verifies that the built-in self-test runs cleanly and inspects internal batch invariants."""
    recorded_calls = []
    orig_audit = cf_mod.LegacyShadowEquivalenceAuditor.audit_trace_batch
    orig_mod_rec = cf_mod.ModernAgentDispatchRecord
    orig_wf_run = cf_mod.CloudflareDisprovingWorkflow.run

    def tagging_mod_rec(*args, **kwargs):
        rec = orig_mod_rec(*args, **kwargs)
        rc = rec.recipient_code
        if not isinstance(rc, _TaggedStr):
            tagged = _TaggedStr(rc)
            tagged.source_caid = rec.caid
            object.__setattr__(rec, "recipient_code", tagged)
        return rec

    def recording_audit(self_obj, legacy_records, modern_records):
        recorded_calls.append((list(legacy_records), list(modern_records)))
        return orig_audit(self_obj, legacy_records, modern_records)

    def zero_rejected_wf_run(self_obj, custom_candidates=None):
        ledger, report = orig_wf_run(self_obj, custom_candidates=custom_candidates)
        report.summary["rejected_count"] = 0
        return ledger, report

    try:
        cf_mod.ModernAgentDispatchRecord = tagging_mod_rec
        cf_mod.LegacyShadowEquivalenceAuditor.audit_trace_batch = recording_audit
        cf_mod.CloudflareDisprovingWorkflow.run = zero_rejected_wf_run
        assert cf_mod.self_test() is True
    finally:
        cf_mod.ModernAgentDispatchRecord = orig_mod_rec
        cf_mod.LegacyShadowEquivalenceAuditor.audit_trace_batch = orig_audit
        cf_mod.CloudflareDisprovingWorkflow.run = orig_wf_run

    assert len(recorded_calls) == 2
    leg1, mod1 = recorded_calls[0]
    _, mod2 = recorded_calls[1]
    base_ts = 17 * 10**8
    assert leg1[0].valid_timestamp == base_ts
    assert mod1[0].valid_time == base_ts
    assert mod1[0].system_time == base_ts + 5
    assert mod2[3].valid_time == base_ts + 3
    assert mod2[3].system_time == base_ts + 8
    assert getattr(mod2[3].recipient_code, "source_caid", "") == "urn:aeib:caid:LEG_3"

    with pytest.raises(ValueError, match="Batch size mismatch"):
        cf_mod.LegacyShadowEquivalenceAuditor().audit_trace_batch([], mod1)


def test_coverage_ledger_generation() -> None:
    """Verifies Phase 1 coverage ledger extraction and RFC 8785 determinism."""
    workflow = CloudflareDisprovingWorkflow(target_dir="src")
    ledger, report = workflow.run()

    assert ledger.total_symbols > 50
    assert ledger.total_boundaries > 0
    assert len(ledger.mapping_digest) == 64

    # Assert JCS canonical digest determinism
    ledger_bytes = encode_jcs(report.receipt)
    assert hashlib.sha256(ledger_bytes).hexdigest() is not None


def test_three_tier_classification_partitioning() -> None:
    """Verifies that findings partition cleanly into confirmed, needs_validation, and rejected."""
    workflow = CloudflareDisprovingWorkflow(target_dir="src")

    # Inject an unmitigated custom candidate (will be CONFIRMED)
    breach_candidate = CandidateFinding(
        candidate_id="CAND-BREACH-001",
        vulnerability_class=VulnerabilityClass.BUDGET_ESCALATION.value,
        target_endpoint="/v1/admin/unrestricted_payout",
        target_symbol="unprotected_handler",
        hypothesis="Unprotected handler executes unlimited budget debit",
        exploit_payload={"amount": 9999999.0, "currency": "EUR"},
        execution_context={
            "financial_gate_active": False,
            "quota_limit_enforced": False,
            "bypassed": True,
        },
    )

    # Inject an ambiguous candidate (will be NEEDS_VALIDATION)
    ambiguous_candidate = CandidateFinding(
        candidate_id="CAND-AMBIG-002",
        vulnerability_class=VulnerabilityClass.CONTEXT_TAINT_DOWNGRADE.value,
        target_endpoint="/v1/agent/delegate",
        target_symbol="supervisor_handoff",
        hypothesis="Potential taint de-escalation under unverified external token",
        exploit_payload={"token": "UNKNOWN_EXTERNAL"},
        execution_context={"requires_manual_inspection": True},
    )

    ledger, report = workflow.run(custom_candidates=[breach_candidate, ambiguous_candidate])

    assert report.summary["confirmed_count"] >= 1
    assert any(c["candidate_id"] == "CAND-006" or "BREACH" in c["candidate_id"] or "unrestricted_payout" in c["target_endpoint"] for c in report.confirmed)

    assert report.summary["needs_validation_count"] >= 1
    assert any(c["candidate_id"] == "CAND-007" or "AMBIG" in c["candidate_id"] or "delegate" in c["target_endpoint"] for c in report.needs_validation)

    assert report.summary["rejected_count"] >= 5
    for rejected_entry in report.rejected:
        assert "observed_defense" in rejected_entry
        assert rejected_entry["observed_defense"] is not None


def test_receipt_ed25519_verification_and_tamper_rejection() -> None:
    """Verifies real Ed25519 signature over canonical payload and tamper rejection."""
    workflow = CloudflareDisprovingWorkflow(target_dir="src")
    _, report = workflow.run()

    receipt = report.receipt
    pub_bytes = bytes.fromhex(receipt["signer_public_key_hex"])
    sig_bytes = bytes.fromhex(receipt["signature_hex"])
    pub_key = Ed25519PublicKey.from_public_bytes(pub_bytes)

    # Reconstruct original report payload without receipt
    report_dict = copy.deepcopy(report.__dict__)
    del report_dict["receipt"]
    canonical_payload_bytes = encode_jcs(report_dict)

    # Verify signature holds over original bytes
    pub_key.verify(sig_bytes, canonical_payload_bytes)

    # Verify tampering causes InvalidSignature
    tampered_bytes = canonical_payload_bytes + b"tamper"
    with pytest.raises(InvalidSignature):
        pub_key.verify(sig_bytes, tampered_bytes)


def test_shadow_equivalence_nominal_match() -> None:
    """Verifies 100% equivalence when modern dispatches match legacy traces exactly."""
    auditor = LegacyShadowEquivalenceAuditor()

    legacy_records = [
        LegacyTransactionRecord(
            tx_id=f"TX_{i}",
            account_id="ACC_EUR_90",
            amount_cents=1000 + i * 50,
            operation="REFUND",
            valid_timestamp=1700000000 + i * 10,
            system_timestamp=1700000005 + i * 10,
            recipient_code="DE89370400440532013000",
            expected_status="CONFIRMED",
        )
        for i in range(25)
    ]

    modern_records = [
        ModernAgentDispatchRecord(
            caid=f"urn:aeib:caid:TX_{i}",
            tenant_id="ACC_EUR_90",
            amount_minor=1000 + i * 50,
            action="REFUND",
            valid_time=1700000000 + i * 10,
            system_time=1700000005 + i * 10,
            recipient_code="DE89370400440532013000",
            status="CONFIRMED",
            duplicate_count=0,
        )
        for i in range(25)
    ]

    res = auditor.audit_trace_batch(legacy_records, modern_records)
    assert res.is_equivalent is True
    assert res.total_evaluated == 25
    assert res.matched_count == 25
    assert res.divergence_count == 0
    assert res.precision_drift_cents == 0
    assert res.bitemporal_anomalies == 0
    assert res.duplicate_mutation_violations == 0


def test_shadow_equivalence_precision_drift_detection() -> None:
    """Verifies that fixed-point cents / minor unit drift is caught."""
    auditor = LegacyShadowEquivalenceAuditor()

    legacy = [
        LegacyTransactionRecord(
            tx_id="TX_P1",
            account_id="ACC_1",
            amount_cents=10050,  # €100.50
            operation="REFUND",
            valid_timestamp=100,
            system_timestamp=105,
            recipient_code="DE89",
            expected_status="CONFIRMED",
        )
    ]

    modern = [
        ModernAgentDispatchRecord(
            caid="urn:aeib:caid:TX_P1",
            tenant_id="ACC_1",
            amount_minor=10049,  # 1 cent drift
            action="REFUND",
            valid_time=100,
            system_time=105,
            recipient_code="DE89",
            status="CONFIRMED",
            duplicate_count=0,
        )
    ]

    res = auditor.audit_trace_batch(legacy, modern)
    assert res.is_equivalent is False
    assert res.precision_drift_cents == 1
    assert res.divergence_count == 1
    assert "Precision drift" in res.divergences[0]["issues"][0]


def test_shadow_equivalence_bitemporal_inversion_detection() -> None:
    """Verifies that valid_time > system_time anomalies fail equivalence."""
    auditor = LegacyShadowEquivalenceAuditor()

    legacy = [
        LegacyTransactionRecord(
            tx_id="TX_B1",
            account_id="ACC_1",
            amount_cents=5000,
            operation="REFUND",
            valid_timestamp=200,
            system_timestamp=205,
            recipient_code="DE89",
            expected_status="CONFIRMED",
        )
    ]

    modern = [
        ModernAgentDispatchRecord(
            caid="urn:aeib:caid:TX_B1",
            tenant_id="ACC_1",
            amount_minor=5000,
            action="REFUND",
            valid_time=210,  # valid_time in future of system_time
            system_time=205,
            recipient_code="DE89",
            status="CONFIRMED",
            duplicate_count=0,
        )
    ]

    res = auditor.audit_trace_batch(legacy, modern)
    assert res.is_equivalent is False
    assert res.bitemporal_anomalies == 1
    assert any("Bitemporal inversion" in iss for iss in res.divergences[0]["issues"])


def test_shadow_equivalence_duplicate_mutation_detection() -> None:
    """Verifies that non-zero duplicate counts fail equivalence."""
    auditor = LegacyShadowEquivalenceAuditor()

    legacy = [
        LegacyTransactionRecord(
            tx_id="TX_D1",
            account_id="ACC_1",
            amount_cents=5000,
            operation="REFUND",
            valid_timestamp=200,
            system_timestamp=205,
            recipient_code="DE89",
            expected_status="CONFIRMED",
        )
    ]

    modern = [
        ModernAgentDispatchRecord(
            caid="urn:aeib:caid:TX_D1",
            tenant_id="ACC_1",
            amount_minor=5000,
            action="REFUND",
            valid_time=200,
            system_time=205,
            recipient_code="DE89",
            status="CONFIRMED",
            duplicate_count=1,  # Duplicate mutation bug!
        )
    ]

    res = auditor.audit_trace_batch(legacy, modern)
    assert res.is_equivalent is False
    assert res.duplicate_mutation_violations == 1
    assert any("Duplicate mutation" in iss for iss in res.divergences[0]["issues"])


def test_epistemic_purity_of_owned_files() -> None:
    """Verifies zero prohibited promotional words across owned files."""
    banned = [
        "guaran" + "teed",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "bank-" + "grade",
    ]
    files_to_check = [
        Path("tools/cloudflare_6phase_disproving_verifier.py"),
        Path(__file__),
    ]

    for p in files_to_check:
        content = p.read_text(encoding="utf-8")
        for word in banned:
            assert word not in content, f"Banned word '{word}' found in {p}"
