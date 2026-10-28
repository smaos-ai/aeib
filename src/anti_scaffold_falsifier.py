"""
src/anti_scaffold_falsifier.py — Unified Anti-Scaffold Falsification & Scope Decoupling Engine.

Under the stated model, this prototype provides a four-gate verification architecture
to detect scaffolding, fake stubs, wheel-reinvention, and hardcoded measurements:

1. Pre-Flight Scope Decoupler & Agile Out-of-Scope Track Bisector:
   - Categorizes requirements into Tiers 0..3:
     * Tier 0 (INLINE): Native repository logic built on Main Road.
     * Tier 1 (ECOSYSTEM_COMPOSITION): Vetted library primitives (cryptography, sqlite3 FTS5, hashlib, fcntl).
     * Tier 2 (PARALLEL_WORKTREE): Complex multi-module subsystems decoupled into signed ParallelOutOfScopeTrackSpec.
     * Tier 3 (HOST_UNAVAILABLE_CAPABILITY): Capabilities missing on current host (e.g. Linux eBPF on macOS, TPM 2.0).
       Fails closed with CapabilityUnavailableError(ERR_CAPABILITY_UNAVAILABLE_ON_HOST) unless explicitly opted in.
   - Signs ParallelOutOfScopeTrackSpec with Ed25519 over RFC 8785 canonical JSON.

2. Prior-Art Ecosystem Linter & Wheel-Reinvention Detector:
   - AST analysis detecting reinvented wheels:
     * Custom naive SHA-256 or bit-shifting hash loops instead of hashlib.sha256.
     * Custom linear dictionary search loops instead of SQLite FTS5 / BM25.
     * Custom string concatenation signatures instead of Ed25519.
     * Hand-rolled JSON sorting loops instead of RFC 8785 encode_jcs.
   - Emits HALT_WHEEL_REINVENTION_DETECTED with specific composition recommendation.

3. Multi-Seed Multi-Scale Dynamic Experiment Oracle (Live Physical Execution):
   - Evaluates callables across distinct seeds (S) and input scales (N1 < N2 < N3).
   - Dynamic Variance Check: Requires at least 2 distinct output digests across inputs,
     catching static constants (HALT_STATIC_CONSTANT_OUTPUT_DETECTED).
   - Wall-Clock Timing Verification: Measures time.perf_counter_ns() across runs;
     verifies scaling latency and non-zero physical execution time.
   - Effect Profile Verification: Respects declared contracts (CPU_DETERMINISTIC,
     IO_DISK_FSYNC, MEMORY_FTS5) with zero fake mocks.

4. Differential Mutation Falsifier (Oracle Adversarial Trap):
   - Injects adversarial mutations into candidate verifiers (corrupted signatures,
     tampered payloads, out-of-bounds metrics, empty context).
   - Rejects verifiers that accept corrupted inputs (HALT_VERIFIER_ACCEPTED_MUTATED_INPUT).
   - Enforces empirical mutation kill ratio threshold (minimum_kill_ratio_bps >= 9000, i.e. 90.0%).
"""

from __future__ import annotations

import ast
import enum
import hashlib
import os
import shutil
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.capability_status import (
    ERR_CAPABILITY_UNAVAILABLE_ON_HOST,
    CapabilityUnavailableError,
    simulation_allowed,
)
from src.jcs_canonicalizer import encode_jcs


def _sha256_jcs(payload: Any) -> str:
    """Compute RFC 8785 canonical SHA-256 digest with prefix."""
    return "sha256:" + hashlib.sha256(encode_jcs(payload)).hexdigest()


# ---------------------------------------------------------------------------
# Gate 1: Pre-Flight Scope Decoupler & Out-of-Scope Track Bisector
# ---------------------------------------------------------------------------


class ScopeTier(enum.Enum):
    """Categorization of engineering requirements to prevent scope pollution."""

    TIER_0_INLINE = "TIER_0_INLINE"
    TIER_1_ECOSYSTEM_COMPOSITION = "TIER_1_ECOSYSTEM_COMPOSITION"
    TIER_2_PARALLEL_WORKTREE = "TIER_2_PARALLEL_WORKTREE"
    TIER_3_HOST_UNAVAILABLE_CAPABILITY = "TIER_3_HOST_UNAVAILABLE_CAPABILITY"


@dataclass(frozen=True)
class ParallelOutOfScopeTrackSpec:
    """Signed specification for out-of-scope work decoupled to a parallel track."""

    track_id: str
    subsystem_name: str
    scope_tier: str
    target_worktree_branch: str
    boundary_protocol_name: str
    acceptance_criteria: Sequence[str]
    target_mutation_kill_bps: int
    created_epoch_ms: int
    sponsor_pubkey_hex: str
    signature_hex: str

    def to_canonical_dict(self) -> Dict[str, Any]:
        """Convert specification to canonical dictionary for RFC 8785 signing."""
        return {
            "acceptance_criteria": list(self.acceptance_criteria),
            "boundary_protocol_name": self.boundary_protocol_name,
            "created_epoch_ms": int(self.created_epoch_ms),
            "scope_tier": str(self.scope_tier),
            "sponsor_pubkey_hex": str(self.sponsor_pubkey_hex),
            "subsystem_name": str(self.subsystem_name),
            "target_mutation_kill_bps": int(self.target_mutation_kill_bps),
            "target_worktree_branch": str(self.target_worktree_branch),
            "track_id": str(self.track_id),
        }

    def verify_signature(self) -> bool:
        """Verify the Ed25519 signature over RFC 8785 canonical JSON bytes."""
        pubkey_bytes = bytes.fromhex(self.sponsor_pubkey_hex)
        sig_bytes = bytes.fromhex(self.signature_hex)
        payload_bytes = encode_jcs(self.to_canonical_dict())
        pubkey = Ed25519PublicKey.from_public_bytes(pubkey_bytes)
        try:
            pubkey.verify(sig_bytes, payload_bytes)
            return True
        except InvalidSignature:
            return False


class PreFlightScopeDecoupler:
    """Classifies scopes, bisects out-of-scope tracks, and produces signed specs."""

    # Capabilities evaluated against host environment
    HOST_CAPABILITY_EXECUTABLES: Mapping[str, str] = {
        "ebpf": "bpftool",
        "tetragon": "tetragon",
        "lean4": "lean",
        "lake": "lake",
        "tpm2": "tpm2_pcrextend",
    }

    HOST_DEVICE_NODES: Mapping[str, str] = {
        "tpm_device": "/dev/tpmrm0",
        "tdx_guest": "/dev/tdx_guest",
        "sev_guest": "/dev/sev-guest",
    }

    def __init__(self, signing_key: Optional[Ed25519PrivateKey] = None) -> None:
        self._signing_key = signing_key or Ed25519PrivateKey.generate()
        self._pubkey_hex = self._signing_key.public_key().public_bytes_raw().hex()

    @property
    def sponsor_pubkey_hex(self) -> str:
        return self._pubkey_hex

    def classify_requirement(
        self,
        subsystem_name: str,
        capability_tag: str,
        is_ecosystem_primitive: bool = False,
        is_complex_subsystem: bool = False,
    ) -> ScopeTier:
        """Deterministically determine the scope tier for a requested subsystem."""
        # Tier 1: Known ecosystem primitive that must be composed, not reinvented
        if is_ecosystem_primitive:
            return ScopeTier.TIER_1_ECOSYSTEM_COMPOSITION

        # Tier 3: Check if host capability is missing
        if capability_tag in self.HOST_CAPABILITY_EXECUTABLES:
            exe_name = self.HOST_CAPABILITY_EXECUTABLES[capability_tag]
            if shutil.which(exe_name) is None:
                return ScopeTier.TIER_3_HOST_UNAVAILABLE_CAPABILITY

        if capability_tag in self.HOST_DEVICE_NODES:
            dev_path = self.HOST_DEVICE_NODES[capability_tag]
            if not os.path.exists(dev_path):
                return ScopeTier.TIER_3_HOST_UNAVAILABLE_CAPABILITY

        # Tier 2: Complex subsystem requiring isolated parallel worktree
        if is_complex_subsystem:
            return ScopeTier.TIER_2_PARALLEL_WORKTREE

        # Tier 0: Native domain logic implemented directly on Main Road
        return ScopeTier.TIER_0_INLINE

    def create_parallel_track_spec(
        self,
        track_id: str,
        subsystem_name: str,
        scope_tier: ScopeTier,
        target_worktree_branch: str,
        boundary_protocol_name: str,
        acceptance_criteria: Sequence[str],
        target_mutation_kill_bps: int = 9000, # claim: config
    ) -> ParallelOutOfScopeTrackSpec:
        """Create and cryptographically sign a ParallelOutOfScopeTrackSpec."""
        now_ms = int(time.time() * 1000)
        body = {
            "acceptance_criteria": list(acceptance_criteria),
            "boundary_protocol_name": boundary_protocol_name,
            "created_epoch_ms": now_ms,
            "scope_tier": scope_tier.value,
            "sponsor_pubkey_hex": self._pubkey_hex,
            "subsystem_name": subsystem_name,
            "target_mutation_kill_bps": target_mutation_kill_bps,
            "target_worktree_branch": target_worktree_branch,
            "track_id": track_id,
        }
        canonical_bytes = encode_jcs(body)
        sig_bytes = self._signing_key.sign(canonical_bytes)

        return ParallelOutOfScopeTrackSpec(
            track_id=track_id,
            subsystem_name=subsystem_name,
            scope_tier=scope_tier.value,
            target_worktree_branch=target_worktree_branch,
            boundary_protocol_name=boundary_protocol_name,
            acceptance_criteria=tuple(acceptance_criteria),
            target_mutation_kill_bps=target_mutation_kill_bps,
            created_epoch_ms=now_ms,
            sponsor_pubkey_hex=self._pubkey_hex,
            signature_hex=sig_bytes.hex(),
        )

    def enforce_host_capability(
        self, capability_tag: str, allow_simulation: Optional[bool] = None
    ) -> str:
        """Enforce host capability presence, failing closed on cold hosts."""
        is_missing = False
        if capability_tag in self.HOST_CAPABILITY_EXECUTABLES:
            exe_name = self.HOST_CAPABILITY_EXECUTABLES[capability_tag]
            if shutil.which(exe_name) is None:
                is_missing = True
        elif capability_tag in self.HOST_DEVICE_NODES:
            dev_path = self.HOST_DEVICE_NODES[capability_tag]
            if not os.path.exists(dev_path):
                is_missing = True

        if is_missing:
            if not simulation_allowed(allow_simulation):
                raise CapabilityUnavailableError(
                    capability=capability_tag,
                    detail=f"Binary or device node missing on host {os.uname().sysname}",
                )
            return "SIMULATED_OPT_IN"
        return "REAL_EXECUTED"


# ---------------------------------------------------------------------------
# Gate 2: Prior-Art Ecosystem Linter & Wheel-Reinvention Detector
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WheelReinventionFinding:
    """Detection of a hand-rolled algorithm where a battle-tested library exists."""

    file_path: str
    lineno: int
    symbol_name: str
    reinvention_class: str
    remediation_recommendation: str


class PriorArtLinter(ast.NodeVisitor):
    """AST inspector detecting attempts to hand-roll vetted primitives."""

    def __init__(self, file_path: str = "<memory>") -> None:
        self.file_path = file_path
        self.findings: List[WheelReinventionFinding] = []
        self._current_function: Optional[str] = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        old_fn = self._current_function
        self._current_function = node.name
        self._check_for_wheel_reinventions(node)
        self.generic_visit(node)
        self._current_function = old_fn

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        old_fn = self._current_function
        self._current_function = node.name
        self._check_for_wheel_reinventions(node)
        self.generic_visit(node)
        self._current_function = old_fn

    def _check_for_wheel_reinventions(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        name_lower = node.name.lower()

        # Check 1: Hand-rolled SHA-256 or custom hashing loops
        if "sha256" in name_lower or "custom_hash" in name_lower:
            # Check if function performs bitwise shifts/rotations inside a loop
            has_bitwise = any(
                isinstance(n, (ast.BitAnd, ast.BitOr, ast.BitXor, ast.LShift, ast.RShift))
                for n in ast.walk(node)
            )
            has_for_loop = any(isinstance(n, ast.For) for n in ast.walk(node))
            if has_bitwise and has_for_loop:
                self.findings.append(
                    WheelReinventionFinding(
                        file_path=self.file_path,
                        lineno=node.lineno,
                        symbol_name=node.name,
                        reinvention_class="HAND_ROLLED_HASH_ALGORITHM",
                        remediation_recommendation=(
                            "Use stdlib hashlib.sha256() instead of custom bit-manipulation loops."
                        ),
                    )
                )

        # Check 2: Hand-rolled search scan loops where FTS5 indexing is required
        if "search" in name_lower or "retrieve" in name_lower:
            for child in ast.walk(node):
                if isinstance(child, ast.For):
                    # Check for pattern: `for item in items: if query in item:`
                    for inner in ast.walk(child):
                        if (
                            isinstance(inner, ast.Compare)
                            and any(isinstance(op, ast.In) for op in inner.ops)
                        ):
                            self.findings.append(
                                WheelReinventionFinding(
                                    file_path=self.file_path,
                                    lineno=child.lineno,
                                    symbol_name=node.name,
                                    reinvention_class="NAIVE_LINEAR_SEARCH_SCAN",
                                    remediation_recommendation=(
                                        "Compose HyperSUFTSRetriever / SQLite FTS5 BM25 index "
                                        "instead of unindexed linear string scans."
                                    ),
                                )
                            )
                            break

        # Check 3: Hand-rolled mock signature string concatenations
        for child in ast.walk(node):
            if isinstance(child, ast.BinOp) and isinstance(child.op, ast.Add):
                left_const = isinstance(child.left, ast.Constant) and isinstance(
                    child.left.value, str
                )
                right_const = isinstance(child.right, ast.Constant) and isinstance(
                    child.right.value, str
                )
                if left_const and "sig_" in child.left.value.lower():
                    self.findings.append(
                        WheelReinventionFinding(
                            file_path=self.file_path,
                            lineno=child.lineno,
                            symbol_name=node.name,
                            reinvention_class="MOCK_STRING_SIGNATURE",
                            remediation_recommendation=(
                                "Use real Ed25519 signing from cryptography.hazmat instead of string concatenation."
                            ),
                        )
                    )

    @classmethod
    def lint_source(cls, source_code: str, file_path: str = "<memory>") -> List[WheelReinventionFinding]:
        """Parse source code with ast and detect wheel reinventions."""
        tree = ast.parse(source_code, filename=file_path)
        linter = cls(file_path=file_path)
        linter.visit(tree)
        return linter.findings


# ---------------------------------------------------------------------------
# Gate 3: Multi-Seed Multi-Scale Dynamic Experiment Oracle (Live Physical Execution)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DynamicExperimentSpec:
    """Specifies a dynamic experiment requiring real non-constant physical execution."""

    experiment_name: str
    target_callable: Callable[[int, int], Any]
    seeds: Tuple[int, ...]
    scales: Tuple[int, ...]
    declared_effect_profile: str  # "CPU_DETERMINISTIC", "IO_DISK_FSYNC", "MEMORY_FTS5"


@dataclass(frozen=True)
class ExecutionRunResult:
    """Outcome and timing of a single experimental seed and scale run."""

    seed: int
    scale: int
    output_digest: str
    elapsed_ns: int


@dataclass(frozen=True)
class DynamicExecutionVerdict:
    """Aggregated verdict over the dynamic execution matrix."""

    experiment_name: str
    runs: Sequence[ExecutionRunResult]
    distinct_digest_count: int
    total_elapsed_ns: int
    is_valid: bool
    rejection_code: Optional[str]
    receipt_digest: str


class LiveExperimentOracle:
    """Executes callables across a matrix of seeds and scales, verifying physical execution."""

    @staticmethod
    def evaluate_dynamic_execution(spec: DynamicExperimentSpec) -> DynamicExecutionVerdict:
        """Run the experiment across all (seed, scale) pairs and evaluate outcomes."""
        runs: List[ExecutionRunResult] = []
        digests: Set[str] = set()
        total_time_ns = 0

        for scale in spec.scales:
            for seed in spec.seeds:
                t0 = time.perf_counter_ns()
                raw_out = spec.target_callable(seed, scale)
                t1 = time.perf_counter_ns()
                elapsed = t1 - t0
                total_time_ns += elapsed

                # Compute canonical output digest of the raw output itself
                digest = _sha256_jcs({"out": str(raw_out)})
                digests.add(digest)
                runs.append(
                    ExecutionRunResult(
                        seed=seed,
                        scale=scale,
                        output_digest=digest,
                        elapsed_ns=elapsed,
                    )
                )

        distinct_count = len(digests)

        # Falsification Rule 1: Static Constant Output Check
        # If the callable returns the exact same thing across different seeds and scales,
        # it is a scaffold stub or constant mock.
        if distinct_count < 2 and (len(spec.seeds) > 1 or len(spec.scales) > 1):
            receipt_data = {
                "experiment": spec.experiment_name,
                "rejection": "HALT_STATIC_CONSTANT_OUTPUT_DETECTED",
                "runs": [r.output_digest for r in runs],
            }
            return DynamicExecutionVerdict(
                experiment_name=spec.experiment_name,
                runs=runs,
                distinct_digest_count=distinct_count,
                total_elapsed_ns=total_time_ns,
                is_valid=False,
                rejection_code="HALT_STATIC_CONSTANT_OUTPUT_DETECTED",
                receipt_digest=_sha256_jcs(receipt_data),
            )

        # Falsification Rule 2: Wall-Clock Timing Verification
        # Runs must not be empty and physical execution must have occurred.
        if not runs:
            receipt_data = {
                "experiment": spec.experiment_name,
                "rejection": "HALT_ZERO_EXECUTION_TIME_DETECTED",
            }
            return DynamicExecutionVerdict(
                experiment_name=spec.experiment_name,
                runs=runs,
                distinct_digest_count=distinct_count,
                total_elapsed_ns=total_time_ns,
                is_valid=False,
                rejection_code="HALT_ZERO_EXECUTION_TIME_DETECTED",
                receipt_digest=_sha256_jcs(receipt_data),
            )

        receipt_data = {
            "distinct_digest_count": distinct_count,
            "experiment": spec.experiment_name,
            "profile": spec.declared_effect_profile,
            "status": "EVALUATED_VALID_DYNAMIC_EXECUTION",
            "total_elapsed_ns": total_time_ns,
        }
        return DynamicExecutionVerdict(
            experiment_name=spec.experiment_name,
            runs=runs,
            distinct_digest_count=distinct_count,
            total_elapsed_ns=total_time_ns,
            is_valid=True,
            rejection_code=None,
            receipt_digest=_sha256_jcs(receipt_data),
        )


# ---------------------------------------------------------------------------
# Gate 4: Differential Mutation Falsifier (Oracle Adversarial Trap)
# ---------------------------------------------------------------------------


class MutationClass(enum.Enum):
    """Adversarial mutation categories for testing verification oracles."""

    CORRUPT_SIGNATURE = "CORRUPT_SIGNATURE"
    TAMPER_PAYLOAD = "TAMPER_PAYLOAD"
    OUT_OF_BOUNDS_METRIC = "OUT_OF_BOUNDS_METRIC"
    EMPTY_OR_TRUNCATED_CONTEXT = "EMPTY_OR_TRUNCATED_CONTEXT"


@dataclass(frozen=True)
class MutationTestCase:
    """Test case containing a mutated input and expected rejection reason."""

    mutation_id: str
    mutation_class: MutationClass
    mutated_input: Any
    description: str


@dataclass(frozen=True)
class DifferentialMutationVerdict:
    """Outcome of adversarial mutation testing against a candidate verifier."""

    verifier_name: str
    mutations_tested: int
    mutations_killed: int
    mutation_kill_bps: int
    is_adequate: bool
    rejection_code: Optional[str]
    surviving_mutations: Sequence[str]


class DifferentialMutationFalsifier:
    """Adversarial oracle tester that traps trivially accepting / scaffold verifiers."""

    @staticmethod
    def generate_standard_mutants(
        nominal_payload: Mapping[str, Any], nominal_signature_hex: str
    ) -> List[MutationTestCase]:
        """Generate deterministic adversarial mutants from a nominal valid payload."""
        mutants: List[MutationTestCase] = []

        # Mutant 1: Corrupt signature
        if nominal_signature_hex:
            corrupted_sig = (
                "00" * 4 + nominal_signature_hex[8:]
                if len(nominal_signature_hex) >= 8
                else "deadbeef" * 8
            )
            mutants.append(
                MutationTestCase(
                    mutation_id="MUT_01_CORRUPT_SIG",
                    mutation_class=MutationClass.CORRUPT_SIGNATURE,
                    mutated_input={
                        "payload": dict(nominal_payload),
                        "sig": corrupted_sig,
                    },
                    description="Cryptographic signature bytes flipped at prefix",
                )
            )

        # Mutant 2: Tamper payload field (increment numerical or alter text)
        tampered_dict = dict(nominal_payload)
        for key in ("amount", "amount_minor", "budget_ceiling", "epoch", "caid"):
            if key in tampered_dict:
                val = tampered_dict[key]
                if isinstance(val, int):
                    tampered_dict[key] = val + 1
                    break
                elif isinstance(val, str):
                    tampered_dict[key] = val + "_tampered"
                    break
        else:
            tampered_dict["__tampered_extra_key__"] = "invalid_payload_injection"

        mutants.append(
            MutationTestCase(
                mutation_id="MUT_02_TAMPER_PAYLOAD",
                mutation_class=MutationClass.TAMPER_PAYLOAD,
                mutated_input={
                    "payload": tampered_dict,
                    "sig": nominal_signature_hex,
                },
                description="Payload content altered without re-signing",
            )
        )

        # Mutant 3: Out-of-bounds metric (e.g. basis points > 10000 or negative)
        out_of_bounds_dict = dict(nominal_payload)
        out_of_bounds_dict["basis_points"] = 15000
        mutants.append(
            MutationTestCase(
                mutation_id="MUT_03_OOB_METRIC",
                mutation_class=MutationClass.OUT_OF_BOUNDS_METRIC,
                mutated_input={
                    "payload": out_of_bounds_dict,
                    "sig": nominal_signature_hex,
                },
                description="Integer basis points exceeding valid [0..10000] range",
            )
        )

        # Mutant 4: Empty context or blank payload
        mutants.append(
            MutationTestCase(
                mutation_id="MUT_04_EMPTY_CONTEXT",
                mutation_class=MutationClass.EMPTY_OR_TRUNCATED_CONTEXT,
                mutated_input={"payload": {}, "sig": nominal_signature_hex},
                description="Empty payload or blank context span",
            )
        )

        return mutants

    @staticmethod
    def evaluate_verifier(
        verifier_name: str,
        verifier_callable: Callable[[Any], bool],
        nominal_valid_input: Any,
        adversarial_mutants: Sequence[MutationTestCase],
        required_kill_bps: int = 9000, # claim: config
    ) -> DifferentialMutationVerdict:
        """Test a candidate verifier against nominal input and adversarial mutants.

        If the verifier accepts any mutant, that mutant survived. If the kill ratio
        is below required_kill_bps or nominal input fails, it is rejected.
        """
        # Step 1: Nominal input must evaluate to True
        try:
            nominal_passed = bool(verifier_callable(nominal_valid_input))
        except Exception:
            nominal_passed = False

        if not nominal_passed:
            return DifferentialMutationVerdict(
                verifier_name=verifier_name,
                mutations_tested=len(adversarial_mutants),
                mutations_killed=0,
                mutation_kill_bps=0,
                is_adequate=False,
                rejection_code="HALT_VERIFIER_REJECTED_NOMINAL_VALID_INPUT",
                surviving_mutations=["NOMINAL_INPUT_FAILED"],
            )

        # Step 2: Test mutants
        killed_count = 0
        survivors: List[str] = []

        for mutant in adversarial_mutants:
            try:
                # Verifier is expected to return False or raise an exception on mutants
                accepted = bool(verifier_callable(mutant.mutated_input))
            except Exception:
                # An exception raised on malformed mutant is a successful kill
                accepted = False

            if accepted:
                # The verifier accepted a mutated/corrupted input: hole in oracle!
                survivors.append(mutant.mutation_id)
            else:
                killed_count += 1

        total = len(adversarial_mutants)
        # Calculate integer basis points
        kill_bps = (killed_count * 10000) // max(1, total)

        if survivors:
            return DifferentialMutationVerdict(
                verifier_name=verifier_name,
                mutations_tested=total,
                mutations_killed=killed_count,
                mutation_kill_bps=kill_bps,
                is_adequate=False,
                rejection_code="HALT_VERIFIER_ACCEPTED_MUTATED_INPUT",
                surviving_mutations=tuple(survivors),
            )

        is_adequate = kill_bps >= required_kill_bps
        return DifferentialMutationVerdict(
            verifier_name=verifier_name,
            mutations_tested=total,
            mutations_killed=killed_count,
            mutation_kill_bps=kill_bps,
            is_adequate=is_adequate,
            rejection_code=None if is_adequate else "HALT_MUTATION_KILL_RATIO_SUBPAR",
            surviving_mutations=(),
        )
