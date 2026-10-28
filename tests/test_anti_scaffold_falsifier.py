"""
tests/test_anti_scaffold_falsifier.py — Verification suite for anti-scaffold falsification.

Under the stated model, this suite evaluates:
1. Scope classification and signed ParallelOutOfScopeTrackSpec verification.
2. Prior-art AST linting detecting hand-rolled algorithms and stubs in sync/async functions.
3. Live physical execution oracle detecting static constant returns and timing properties.
4. Differential mutation falsifier trapping trivially accepting verifiers and calculating kill ratios.
5. Immutability of dataclasses (FrozenInstanceError on mutation attempts).
"""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from typing import Any, Dict

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.anti_scaffold_falsifier import (
    DifferentialMutationFalsifier,
    DynamicExperimentSpec,
    ExecutionRunResult,
    LiveExperimentOracle,
    MutationClass,
    MutationTestCase,
    ParallelOutOfScopeTrackSpec,
    PreFlightScopeDecoupler,
    PriorArtLinter,
    ScopeTier,
    _sha256_jcs,
)
from src.capability_status import CapabilityUnavailableError
from src.jcs_canonicalizer import encode_jcs


# ---------------------------------------------------------------------------
# Test Gate 1: Scope Decoupler & Signed Parallel Track Spec
# ---------------------------------------------------------------------------


def test_scope_tier_classification() -> None:
    """Evaluate deterministic classification across Tiers 0..3."""
    decoupler = PreFlightScopeDecoupler()
    assert decoupler.sponsor_pubkey_hex is not None
    assert len(decoupler.sponsor_pubkey_hex) == 64

    # Tier 0: native inline domain logic
    tier_0 = decoupler.classify_requirement(
        subsystem_name="state_capsule",
        capability_tag="pure_python_memory",
        is_ecosystem_primitive=False,
        is_complex_subsystem=False,
    )
    assert tier_0 == ScopeTier.TIER_0_INLINE

    # Tier 1: known ecosystem primitive that must be composed
    tier_1 = decoupler.classify_requirement(
        subsystem_name="sqlite_fts5_index",
        capability_tag="fts5",
        is_ecosystem_primitive=True,
    )
    assert tier_1 == ScopeTier.TIER_1_ECOSYSTEM_COMPOSITION

    # Tier 2: complex subsystem requiring parallel worktree
    tier_2 = decoupler.classify_requirement(
        subsystem_name="pqc_lattice_signer",
        capability_tag="post_quantum_rust_crate",
        is_complex_subsystem=True,
    )
    assert tier_2 == ScopeTier.TIER_2_PARALLEL_WORKTREE

    # Tier 3: missing host capability (executable)
    tier_3_exe = decoupler.classify_requirement(
        subsystem_name="kernel_lsm_guard",
        capability_tag="tetragon",
    )
    assert tier_3_exe == ScopeTier.TIER_3_HOST_UNAVAILABLE_CAPABILITY

    # Tier 3: missing host device node
    tier_3_dev = decoupler.classify_requirement(
        subsystem_name="hardware_tpm",
        capability_tag="tpm_device",
    )
    assert tier_3_dev == ScopeTier.TIER_3_HOST_UNAVAILABLE_CAPABILITY


def test_signed_parallel_out_of_scope_track_spec() -> None:
    """Evaluate generation and cryptographic verification of ParallelOutOfScopeTrackSpec."""
    key = Ed25519PrivateKey.generate()
    decoupler = PreFlightScopeDecoupler(signing_key=key)

    spec = decoupler.create_parallel_track_spec(
        track_id="TRACK-2026-EBPF-LSM",
        subsystem_name="LinuxKernelLsmEnforcer",
        scope_tier=ScopeTier.TIER_3_HOST_UNAVAILABLE_CAPABILITY,
        target_worktree_branch="feat/linux-ebpf-lsm-sandbox",
        boundary_protocol_name="KernelSecurityBoundaryProtocol",
        acceptance_criteria=[
            "Zero socket egress outside unix domain sockets",
            "Hardware quote binding via PCR 11",
        ],
        target_mutation_kill_bps=9500,
    )

    # Assert signature verifies under sponsor public key
    assert spec.verify_signature() is True

    # Assert immutability on frozen dataclass
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.subsystem_name = "tampered"  # type: ignore

    # Assert tampering causes verification failure
    tampered_dict = spec.to_canonical_dict()
    tampered_dict["target_worktree_branch"] = "feat/malicious-redirect"
    tampered_bytes = encode_jcs(tampered_dict)

    pubkey = Ed25519PublicKey.from_public_bytes(bytes.fromhex(spec.sponsor_pubkey_hex))
    with pytest.raises(Exception):
        pubkey.verify(bytes.fromhex(spec.signature_hex), tampered_bytes)


def test_enforce_host_capability_fail_closed_and_opt_in() -> None:
    """Evaluate fail-closed behavior on missing host capability vs explicit opt-in."""
    decoupler = PreFlightScopeDecoupler()

    # Missing executable capability without opt-in must raise CapabilityUnavailableError
    with pytest.raises(CapabilityUnavailableError) as exc_info:
        decoupler.enforce_host_capability("lean4", allow_simulation=False)
    assert "ERR_CAPABILITY_UNAVAILABLE_ON_HOST" in str(exc_info.value)

    # Missing device capability without opt-in must raise CapabilityUnavailableError
    with pytest.raises(CapabilityUnavailableError) as exc_info_dev:
        decoupler.enforce_host_capability("tpm_device", allow_simulation=False)
    assert "ERR_CAPABILITY_UNAVAILABLE_ON_HOST" in str(exc_info_dev.value)

    # With explicit simulation opt-in, returns SIMULATED_OPT_IN
    status_sim = decoupler.enforce_host_capability("lean4", allow_simulation=True)
    assert status_sim == "SIMULATED_OPT_IN"

    status_sim_dev = decoupler.enforce_host_capability("tpm_device", allow_simulation=True)
    assert status_sim_dev == "SIMULATED_OPT_IN"

    # Capability not in missing maps (e.g. standard known or local)
    status_real = decoupler.enforce_host_capability("local_unregistered_capability")
    assert status_real == "REAL_EXECUTED"


# ---------------------------------------------------------------------------
# Test Gate 2: Prior-Art Ecosystem Linter
# ---------------------------------------------------------------------------


def test_prior_art_linter_detects_hand_rolled_sha256_sync_and_async() -> None:
    """Evaluate detection of naive hand-rolled SHA-256 bitwise loops in sync and async."""
    sync_source = '''
def naive_sha256_hash(data: bytes) -> str:
    h = 0x6a09e667
    for byte in data:
        h = ((h << 5) ^ (h >> 2)) & 0xffffffff
        h = (h + byte) & 0xffffffff
    return hex(h)
'''
    findings = PriorArtLinter.lint_source(sync_source, "bad_hash.py")
    assert len(findings) >= 1
    assert any(f.reinvention_class == "HAND_ROLLED_HASH_ALGORITHM" for f in findings)

    async_source = '''
async def custom_hash_async(data: bytes) -> str:
    acc = 0
    for b in data:
        acc = (acc << 4) ^ (acc >> 1)
    return str(acc)
'''
    findings_async = PriorArtLinter.lint_source(async_source, "bad_async_hash.py")
    assert len(findings_async) >= 1
    assert any(f.reinvention_class == "HAND_ROLLED_HASH_ALGORITHM" for f in findings_async)


def test_prior_art_linter_detects_naive_linear_search() -> None:
    """Evaluate detection of linear dictionary search scans when indexing is mandated."""
    bad_source = '''
def search_records(query: str, records: list) -> list:
    results = []
    for item in records:
        if query in item["text"]:
            results.append(item)
    return results

async def retrieve_entries(keyword: str, items: list) -> list:
    res = []
    for el in items:
        if keyword in el:
            res.append(el)
    return res
'''
    findings = PriorArtLinter.lint_source(bad_source, "bad_search.py")
    assert len(findings) >= 2
    assert all(f.reinvention_class == "NAIVE_LINEAR_SEARCH_SCAN" for f in findings)


def test_prior_art_linter_detects_mock_string_signatures() -> None:
    """Evaluate detection of dummy string concatenation signatures."""
    bad_source = '''
def sign_payload(payload_id: str) -> str:
    return "sig_" + payload_id
'''
    findings = PriorArtLinter.lint_source(bad_source, "mock_signer.py")
    assert len(findings) >= 1
    assert any(f.reinvention_class == "MOCK_STRING_SIGNATURE" for f in findings)


def test_prior_art_linter_passes_clean_code() -> None:
    """Assert clean code using stdlib and vetted primitives produces zero findings."""
    clean_source = '''
import hashlib
from src.jcs_canonicalizer import encode_jcs

def compute_record_digest(payload: dict) -> str:
    canonical_bytes = encode_jcs(payload)
    return hashlib.sha256(canonical_bytes).hexdigest()
'''
    findings = PriorArtLinter.lint_source(clean_source, "clean_module.py")
    assert len(findings) == 0


# ---------------------------------------------------------------------------
# Test Gate 3: Live Experiment Oracle (Physical Execution & Dynamic Variance)
# ---------------------------------------------------------------------------


def test_dataclasses_frozen_immutability() -> None:
    """Assert that all core dataclasses are immutable and raise FrozenInstanceError."""
    spec = DynamicExperimentSpec(
        experiment_name="test_immutability",
        target_callable=lambda s, n: s + n,
        seeds=(1,),
        scales=(1,),
        declared_effect_profile="CPU_DETERMINISTIC",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.experiment_name = "altered"  # type: ignore

    run_res = ExecutionRunResult(seed=1, scale=1, output_digest="sha256:abc", elapsed_ns=100)
    with pytest.raises(dataclasses.FrozenInstanceError):
        run_res.elapsed_ns = 200  # type: ignore

    mut_case = MutationTestCase(
        mutation_id="MUT_TEST",
        mutation_class=MutationClass.TAMPER_PAYLOAD,
        mutated_input={},
        description="desc",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        mut_case.description = "new_desc"  # type: ignore


def test_live_experiment_oracle_positive_dynamic_execution() -> None:
    """Evaluate genuine dynamic execution producing non-constant outputs with real timing."""
    def dynamic_workload(seed: int, scale: int) -> Dict[str, Any]:
        acc = seed
        for step in range(scale):
            acc = (acc * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        return {"seed": seed, "scale": scale, "final_val": acc}

    spec = DynamicExperimentSpec(
        experiment_name="dynamic_pseudo_random_walk",
        target_callable=dynamic_workload,
        seeds=(42, 137, 2026),
        scales=(32, 128, 512),
        declared_effect_profile="CPU_DETERMINISTIC",
    )

    verdict = LiveExperimentOracle.evaluate_dynamic_execution(spec)
    assert verdict.is_valid is True
    assert verdict.rejection_code is None
    assert verdict.distinct_digest_count == 9
    assert verdict.total_elapsed_ns > 0
    assert len(verdict.runs) == 9

    with pytest.raises(dataclasses.FrozenInstanceError):
        verdict.is_valid = False  # type: ignore


def test_live_experiment_oracle_catches_static_constant_mock() -> None:
    """Evaluate detection and rejection of static constant returns."""
    def mock_scaffold_workload(seed: int, scale: int) -> Dict[str, Any]:
        return {"status": "ok", "computed_metric": 42}

    # Test 1: Multiple seeds, multiple scales
    spec1 = DynamicExperimentSpec(
        experiment_name="fake_scaffold_workload_1",
        target_callable=mock_scaffold_workload,
        seeds=(10, 20, 30),
        scales=(100, 200),
        declared_effect_profile="CPU_DETERMINISTIC",
    )
    verdict1 = LiveExperimentOracle.evaluate_dynamic_execution(spec1)
    assert verdict1.is_valid is False
    assert verdict1.rejection_code == "HALT_STATIC_CONSTANT_OUTPUT_DETECTED"
    assert verdict1.distinct_digest_count == 1

    # Test 2: Single seed, multiple scales (still static)
    spec2 = DynamicExperimentSpec(
        experiment_name="fake_scaffold_workload_2",
        target_callable=mock_scaffold_workload,
        seeds=(10,),
        scales=(100, 200),
        declared_effect_profile="CPU_DETERMINISTIC",
    )
    verdict2 = LiveExperimentOracle.evaluate_dynamic_execution(spec2)
    assert verdict2.is_valid is False
    assert verdict2.rejection_code == "HALT_STATIC_CONSTANT_OUTPUT_DETECTED"

    # Test 3: Multiple seeds, single scale (still static)
    spec3 = DynamicExperimentSpec(
        experiment_name="fake_scaffold_workload_3",
        target_callable=mock_scaffold_workload,
        seeds=(10, 20),
        scales=(100,),
        declared_effect_profile="CPU_DETERMINISTIC",
    )
    verdict3 = LiveExperimentOracle.evaluate_dynamic_execution(spec3)
    assert verdict3.is_valid is False
    assert verdict3.rejection_code == "HALT_STATIC_CONSTANT_OUTPUT_DETECTED"

    # Test 4: Empty seeds/scales leading to zero execution time
    spec4 = DynamicExperimentSpec(
        experiment_name="zero_time_workload",
        target_callable=mock_scaffold_workload,
        seeds=(),
        scales=(100,),
        declared_effect_profile="CPU_DETERMINISTIC",
    )
    verdict4 = LiveExperimentOracle.evaluate_dynamic_execution(spec4)
    assert verdict4.is_valid is False
    assert verdict4.rejection_code == "HALT_ZERO_EXECUTION_TIME_DETECTED"
    assert verdict4.total_elapsed_ns == 0


def test_live_experiment_oracle_accepts_two_distinct_outputs() -> None:
    """Assert experiment producing exactly 2 distinct outputs is considered non-static."""
    spec = DynamicExperimentSpec(
        experiment_name="binary_state_workload",
        target_callable=lambda seed, scale: {"state": seed % 2},
        seeds=(0, 1, 2, 3),
        scales=(10,),
        declared_effect_profile="CPU_DETERMINISTIC",
    )
    verdict = LiveExperimentOracle.evaluate_dynamic_execution(spec)
    assert verdict.is_valid is True
    assert verdict.distinct_digest_count == 2
    assert verdict.rejection_code is None


# ---------------------------------------------------------------------------
# Test Gate 4: Differential Mutation Falsifier (Oracle Adversarial Trap)
# ---------------------------------------------------------------------------


def test_differential_mutation_falsifier_on_robust_verifier() -> None:
    """Evaluate that a real cryptographic verifier kills 100% of mutants."""
    key = Ed25519PrivateKey.generate()
    pubkey = key.public_key()
    pubkey_bytes = pubkey.public_bytes_raw()

    nominal_payload = {
        "amount_minor": 5000,
        "basis_points": 7500,
        "caid": "caid_test_01",
    }
    nominal_sig = key.sign(encode_jcs(nominal_payload)).hex()

    nominal_input = {
        "payload": nominal_payload,
        "sig": nominal_sig,
        "pubkey": pubkey_bytes.hex(),
    }

    # Real robust verifier checking signature, required fields, and metric ranges
    def robust_verifier(data: Any) -> bool:
        if not isinstance(data, dict):
            return False
        payload = data.get("payload")
        sig_hex = data.get("sig")
        pk_hex = data.get("pubkey", pubkey_bytes.hex())
        if not payload or not sig_hex or not pk_hex:
            return False

        # Validate bounds
        bps = payload.get("basis_points")
        if bps is None or bps < 0 or bps > 10000:
            return False

        # Verify cryptographic signature
        try:
            sig = bytes.fromhex(sig_hex)
            pk = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pk_hex))
            pk.verify(sig, encode_jcs(payload))
            return True
        except Exception:
            return False

    mutants = DifferentialMutationFalsifier.generate_standard_mutants(
        nominal_payload=nominal_payload,
        nominal_signature_hex=nominal_sig,
    )
    assert len(mutants) == 4
    # Check exact structure of corrupt signature mutant
    corrupt_sig_mutant = next(m for m in mutants if m.mutation_id == "MUT_01_CORRUPT_SIG")
    assert corrupt_sig_mutant.mutated_input["sig"] == "00000000" + nominal_sig[8:]
    assert len(corrupt_sig_mutant.mutated_input["sig"]) == len(nominal_sig)

    # Check short signature fallback path (< 8 chars)
    short_mutants = DifferentialMutationFalsifier.generate_standard_mutants(
        nominal_payload=nominal_payload,
        nominal_signature_hex="beef",
    )
    short_sig_mutant = next(m for m in short_mutants if m.mutation_id == "MUT_01_CORRUPT_SIG")
    assert short_sig_mutant.mutated_input["sig"] == "deadbeef" * 8
    assert len(short_sig_mutant.mutated_input["sig"]) == 64

    # Check exact threshold signature (exactly 8 chars)
    exact_mutants = DifferentialMutationFalsifier.generate_standard_mutants(
        nominal_payload=nominal_payload,
        nominal_signature_hex="abcdef12",
    )
    exact_sig_mutant = next(m for m in exact_mutants if m.mutation_id == "MUT_01_CORRUPT_SIG")
    assert exact_sig_mutant.mutated_input["sig"] == "00000000"

    # Check exact structure of tampered payload mutant (+1 increment)
    tampered_mutant = next(m for m in mutants if m.mutation_id == "MUT_02_TAMPER_PAYLOAD")
    assert tampered_mutant.mutated_input["payload"]["amount_minor"] == nominal_payload["amount_minor"] + 1

    # Augment mutants with public key
    augmented_mutants = [
        MutationTestCase(
            mutation_id=m.mutation_id,
            mutation_class=m.mutation_class,
            mutated_input={"payload": m.mutated_input["payload"], "sig": m.mutated_input["sig"], "pubkey": pubkey_bytes.hex()},
            description=m.description,
        )
        for m in mutants
    ]

    verdict = DifferentialMutationFalsifier.evaluate_verifier(
        verifier_name="RobustEd25519Verifier",
        verifier_callable=robust_verifier,
        nominal_valid_input=nominal_input,
        adversarial_mutants=augmented_mutants,
        required_kill_bps=9000,
    )

    assert verdict.is_adequate is True
    assert verdict.rejection_code is None
    assert verdict.mutations_killed == len(augmented_mutants)
    assert verdict.mutation_kill_bps == 10000
    assert len(verdict.surviving_mutations) == 0


def test_differential_mutation_falsifier_traps_trivial_verifier() -> None:
    """Evaluate that a trivially accepting scaffold verifier is trapped immediately."""
    nominal_payload = {"amount_minor": 1000}
    nominal_sig = "deadbeef" * 8
    nominal_input = {"payload": nominal_payload, "sig": nominal_sig}

    # Trivial scaffold verifier that returns True for everything
    def trivial_scaffold_verifier(data: Any) -> bool:
        return True

    mutants = DifferentialMutationFalsifier.generate_standard_mutants(
        nominal_payload=nominal_payload,
        nominal_signature_hex=nominal_sig,
    )

    verdict = DifferentialMutationFalsifier.evaluate_verifier(
        verifier_name="TrivialScaffoldVerifier",
        verifier_callable=trivial_scaffold_verifier,
        nominal_valid_input=nominal_input,
        adversarial_mutants=mutants,
        required_kill_bps=9000,
    )

    assert verdict.is_adequate is False
    assert verdict.rejection_code == "HALT_VERIFIER_ACCEPTED_MUTATED_INPUT"
    assert verdict.mutations_killed == 0
    assert len(verdict.surviving_mutations) == len(mutants)


def test_differential_mutation_falsifier_rejects_subpar_kill_ratio() -> None:
    """Evaluate rejection when verifier does not meet required kill basis points."""
    nominal_payload = {"amount_minor": 1000}
    nominal_sig = "deadbeef" * 8
    nominal_input = {"payload": nominal_payload, "sig": nominal_sig}

    # Verifier that rejects only empty context mutant, but accepts all others
    def leaky_verifier(data: Any) -> bool:
        payload = data.get("payload", {})
        if not payload:
            return False  # Kills empty context
        return True  # Survives on corrupt sig and tampered payload

    mutants = DifferentialMutationFalsifier.generate_standard_mutants(
        nominal_payload=nominal_payload,
        nominal_signature_hex=nominal_sig,
    )

    verdict = DifferentialMutationFalsifier.evaluate_verifier(
        verifier_name="LeakyVerifier",
        verifier_callable=leaky_verifier,
        nominal_valid_input=nominal_input,
        adversarial_mutants=mutants,
        required_kill_bps=9000,
    )

    assert verdict.is_adequate is False
    assert verdict.rejection_code == "HALT_VERIFIER_ACCEPTED_MUTATED_INPUT"
    assert verdict.mutations_killed < len(mutants)


def test_differential_mutation_falsifier_handles_exception_raising_verifier() -> None:
    """Assert verifiers raising exceptions on mutated inputs count as killed mutants."""
    nominal_input = {"payload": {"valid": True}, "sig": "valid"}

    def exception_raising_verifier(data: Any) -> bool:
        if data != nominal_input:
            raise ValueError("Corrupted data input!")
        return True

    mutants = [
        MutationTestCase(
            mutation_id="MUT_ERR_01",
            mutation_class=MutationClass.TAMPER_PAYLOAD,
            mutated_input={"payload": {"valid": False}, "sig": "valid"},
            description="Mutant causing unhandled ValueError",
        )
    ]

    verdict = DifferentialMutationFalsifier.evaluate_verifier(
        verifier_name="ExceptionRaisingVerifier",
        verifier_callable=exception_raising_verifier,
        nominal_valid_input=nominal_input,
        adversarial_mutants=mutants,
        required_kill_bps=9000,
    )

    assert verdict.is_adequate is True
    assert verdict.rejection_code is None
    assert verdict.mutations_killed == 1
    assert verdict.mutation_kill_bps == 10000


def test_differential_mutation_falsifier_rejects_broken_nominal_verifier() -> None:
    """Evaluate rejection when candidate verifier fails nominal valid input."""
    nominal_input = {"payload": {"test": 123}, "sig": "valid"}

    def broken_verifier(data: Any) -> bool:
        return False

    verdict = DifferentialMutationFalsifier.evaluate_verifier(
        verifier_name="BrokenVerifier",
        verifier_callable=broken_verifier,
        nominal_valid_input=nominal_input,
        adversarial_mutants=[],
    )

    assert verdict.is_adequate is False
    assert verdict.rejection_code == "HALT_VERIFIER_REJECTED_NOMINAL_VALID_INPUT"
    assert verdict.mutations_killed == 0
    assert verdict.mutation_kill_bps == 0


def test_differential_mutation_falsifier_rejects_exploding_nominal_verifier() -> None:
    """Evaluate rejection when candidate verifier raises an exception on nominal input."""
    nominal_input = {"payload": {"test": 123}, "sig": "valid"}

    def exploding_verifier(data: Any) -> bool:
        raise RuntimeError("Crash on nominal input")

    verdict = DifferentialMutationFalsifier.evaluate_verifier(
        verifier_name="ExplodingVerifier",
        verifier_callable=exploding_verifier,
        nominal_valid_input=nominal_input,
        adversarial_mutants=[],
    )

    assert verdict.is_adequate is False
    assert verdict.rejection_code == "HALT_VERIFIER_REJECTED_NOMINAL_VALID_INPUT"
    assert verdict.mutations_killed == 0


# ---------------------------------------------------------------------------
# Test Gate 5: Epistemic & Banned Word Enforcer
# ---------------------------------------------------------------------------


def test_no_banned_words_in_anti_scaffold_files() -> None:
    """Verify that source and test files contain zero promotional banned words."""
    banned_words = [
        "guaran" + "teed",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "proven " + "universally",
        "bank-" + "grade",
        "unhack" + "able",
        "unassail" + "able",
    ]

    files_to_check = [
        Path("src/anti_scaffold_falsifier.py"),
        Path("tests/test_anti_scaffold_falsifier.py"),
    ]

    for p in files_to_check:
        text = p.read_text(encoding="utf-8").lower()
        for bw in banned_words:
            assert bw not in text, f"Banned word '{bw}' found in {p}"
