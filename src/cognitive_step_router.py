#!/usr/bin/env python3
"""
SovereignNexus Phase VIII: 5-Step Cognitive Division-of-Labor & Monotonic Speculative Router.
Status: INTERNAL PREVIEW COMMISSIONED

Evaluated under the stated model to implement:
1. 5-Step Cognitive Division of Labor:
   - Step 1 (`STEP_1_OBSERVE_AND_SCOPE`): `TIER_0_DETERMINISTIC_KERNEL` ($0, 0 tokens).
     Computes reverse-dependency blast radius (`HypergraphBlastRadiusGovernor`), slices AST
     context (`AlibabaASTDiffSlicer`), and audits the test oracle against degenerate constant
     stubs (`audit_test_oracle_non_vacuity`) to halt tautological test poisoning before any
     LLM tokens are spent.
   - Step 2 (`STEP_2_ARCHITECTURAL_SPEC_CONTRACT`): Routes to `TIER_3_OPUS_ARCHITECT`
     (or `TIER_3_DEEPSEEK_R1_ARCHITECT`) when `blast_radius_bps > 2500` or the target path
     is security-sensitive; routes to `TIER_1_FAST_PLANNER` for low-risk leaf modules.
   - Step 3 (`STEP_3_SYNTHESIZE_CODE`): `TIER_2_FAST_CODER` (single-branch or Best-of-K
     speculative branches) constrained by `ArchitecturalSpecContract`.
   - Step 4 (`STEP_4_PAULI_AUDIT`): `TIER_0_DETERMINISTIC_KERNEL` ($0, 0 tokens).
     Enforces contract boundaries, `TemporalAuthorityGuard` async-daemon AST checks, and
     `AdversarialMutationVerifier` semantic mutation adequacy.
   - Step 5 (`STEP_5_EO1_WAL_AND_SCITT_SEAL`): `TIER_0_DETERMINISTIC_KERNEL` ($0, 0 tokens).
2. Monotonic Contract Refinement (`reconcile_contract_import_request`):
   Remediates the "Unilateral Contract Mutiny" vulnerability by forbidding child coder
   escalation to third-party packages (`numpy`, `requests`) or I/O/process modules (`urllib`,
   `socket`, `subprocess`, `os`), permitting import amendments only for pure side-effect-free
   stdlib modules (`PURE_STDLIB_SAFE_MODULES`) explicitly pre-authorized in the Architect's
   `secondary_stdlib_allowlist` (S_amended <= S_architect_envelope).

Note on Token & Cost Accounting (`AGENTS.md` §6):
Exact UTF-8 byte lengths (`input_bytes`, `output_bytes`) are recorded on every step. When
provider usage metadata is not supplied (offline evaluation), `input_tokens` and `output_tokens`
are computed as deterministic byte-derived synthetic proxies (`(utf8_bytes + 3) // 4`) under
the configured pricing schedule (`# claim: assumption`).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

from src.adversarial_mutation_verifier import (
    AdversarialMutationVerifier,
    sha256_caid,
)
from src.hypergraph_blast_radius import HypergraphBlastRadiusGovernor
from src.jcs_canonicalizer import encode_jcs
from src.sovereign_token_decree import AlibabaASTDiffSlicer, HeadroomLogCompactor
from src.temporal_authority_guard import TemporalAuthorityGuard

DEFAULT_BLAST_RADIUS_OPUS_THRESHOLD_BPS: int = 2500  # claim: config
DEFAULT_MINIMUM_MUTATION_SCORE_BPS: int = 9000  # claim: config
DEFAULT_MAX_REPAIR_ATTEMPTS: int = 2  # claim: config

# Configured synthetic pricing schedule per 1,000 tokens in integer nano-USD
# (1,000,000,000 nano-USD = $1.00).
TIER_COST_PER_1K_INPUT_NANO_USD: Mapping[str, int] = {
    "TIER_0_DETERMINISTIC_KERNEL": 0,  # claim: config
    "TIER_1_FAST_PLANNER": 150_000,  # claim: assumption
    "TIER_2_FAST_CODER": 300_000,  # claim: assumption
    "TIER_3_DEEPSEEK_R1_ARCHITECT": 550_000,  # claim: assumption
    "TIER_3_OPUS_ARCHITECT": 15_000_000,  # claim: assumption
}

TIER_COST_PER_1K_OUTPUT_NANO_USD: Mapping[str, int] = {
    "TIER_0_DETERMINISTIC_KERNEL": 0,  # claim: config
    "TIER_1_FAST_PLANNER": 600_000,  # claim: assumption
    "TIER_2_FAST_CODER": 1_200_000,  # claim: assumption
    "TIER_3_DEEPSEEK_R1_ARCHITECT": 2_190_000,  # claim: assumption
    "TIER_3_OPUS_ARCHITECT": 75_000_000,  # claim: assumption
}

# Pure computation stdlib modules with zero filesystem, network, or process side effects
PURE_STDLIB_SAFE_MODULES: FrozenSet[str] = frozenset(
    {
        "math",
        "decimal",
        "fractions",
        "itertools",
        "collections",
        "functools",
        "typing",
        "dataclasses",
    }
)


@dataclass(frozen=True)
class ArchitecturalSpecContract:
    """
    Compact Poka-Yoke Contract emitted by Step 2 (`TIER_3_OPUS_ARCHITECT`,
    `TIER_3_DEEPSEEK_R1_ARCHITECT`, or `TIER_1_FAST_PLANNER`) to constrain Step 3 (`TIER_2_FAST_CODER`).
    """

    task_id: str
    architect_tier: str
    allowed_files: Tuple[str, ...]
    allowed_imports: Tuple[str, ...]
    required_function_name: str
    max_lines_changed: int
    invariant_summary: str
    contract_caid: str
    secondary_stdlib_allowlist: Tuple[str, ...] = ()


@dataclass(frozen=True)
class StepExecutionRecord:
    step_number: int
    step_name: str
    actor_tier: str
    input_bytes: int
    output_bytes: int
    input_tokens: int
    output_tokens: int
    step_cost_nano_usd: int
    verdict_code: str
    artifact_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actor_tier": self.actor_tier,
            "artifact_caid": self.artifact_caid,
            "input_bytes": self.input_bytes,
            "input_tokens": self.input_tokens,
            "output_bytes": self.output_bytes,
            "output_tokens": self.output_tokens,
            "step_cost_nano_usd": self.step_cost_nano_usd,
            "step_name": self.step_name,
            "step_number": self.step_number,
            "verdict_code": self.verdict_code,
        }


@dataclass(frozen=True)
class FiveStepTrajectoryResult:
    task_id: str
    final_status: str
    opus_invocations: int
    fast_coder_invocations: int
    zero_cost_kernel_steps: int
    total_cost_nano_usd: int
    monolithic_opus_baseline_nano_usd: int
    cost_savings_bps: int
    mutation_score_bps: int
    step_records: Tuple[StepExecutionRecord, ...]
    trajectory_caid: str


class SovereignCognitiveStepRouter:
    """
    Routes the 5-step reasoning & implementation loop across specialized actor tiers
    so high-cost frontier reasoning (`TIER_3_OPUS_ARCHITECT` / `TIER_3_DEEPSEEK_R1_ARCHITECT`)
    is invoked strictly for high-blast-radius or security-sensitive architectural specs,
    `TIER_2_FAST_CODER` handles bounded code synthesis, and `TIER_0_DETERMINISTIC_KERNEL`
    executes scoping, vacuous-test detection, AST/mutation verification, and sealing at $0 token cost.
    """

    def __init__(
        self,
        repo_sources: Mapping[str, str],
        blast_radius_opus_threshold_bps: int = DEFAULT_BLAST_RADIUS_OPUS_THRESHOLD_BPS,
        minimum_mutation_score_bps: int = DEFAULT_MINIMUM_MUTATION_SCORE_BPS,
        max_repair_attempts: int = DEFAULT_MAX_REPAIR_ATTEMPTS,
        high_tier_architect: str = "TIER_3_OPUS_ARCHITECT",
    ) -> None:
        if blast_radius_opus_threshold_bps < 0 or blast_radius_opus_threshold_bps > 10000:
            raise ValueError("ERR_INVALID_BLAST_RADIUS_THRESHOLD")
        if max_repair_attempts < 0:
            raise ValueError("ERR_INVALID_MAX_REPAIR_ATTEMPTS")
        if high_tier_architect not in TIER_COST_PER_1K_INPUT_NANO_USD:
            raise ValueError(f"ERR_UNKNOWN_ARCHITECT_TIER:{high_tier_architect}")

        self.repo_sources = dict(repo_sources)
        self.blast_governor = HypergraphBlastRadiusGovernor(
            repo_sources=self.repo_sources,
            max_auto_merge_radius_bps=blast_radius_opus_threshold_bps,
        )
        self.mutation_verifier = AdversarialMutationVerifier(
            minimum_score_bps=minimum_mutation_score_bps
        )
        self.blast_radius_opus_threshold_bps = blast_radius_opus_threshold_bps
        self.max_repair_attempts = max_repair_attempts
        self.high_tier_architect = high_tier_architect

    @classmethod
    def from_disk_repo(
        cls,
        repo_root: Path,
        relative_paths: Sequence[str],
        blast_radius_opus_threshold_bps: int = DEFAULT_BLAST_RADIUS_OPUS_THRESHOLD_BPS,
        minimum_mutation_score_bps: int = DEFAULT_MINIMUM_MUTATION_SCORE_BPS,
        max_repair_attempts: int = DEFAULT_MAX_REPAIR_ATTEMPTS,
        high_tier_architect: str = "TIER_3_OPUS_ARCHITECT",
    ) -> "SovereignCognitiveStepRouter":
        """Loads real on-disk Python source files from `repo_root` without synthetic stubs."""
        sources: Dict[str, str] = {}
        for rel in relative_paths:
            full_path = Path(repo_root) / rel
            sources[rel] = full_path.read_text(encoding="utf-8")
        return cls(
            repo_sources=sources,
            blast_radius_opus_threshold_bps=blast_radius_opus_threshold_bps,
            minimum_mutation_score_bps=minimum_mutation_score_bps,
            max_repair_attempts=max_repair_attempts,
            high_tier_architect=high_tier_architect,
        )

    @staticmethod
    def compute_step_cost_nano_usd(
        actor_tier: str, input_tokens: int, output_tokens: int
    ) -> int:
        in_rate = TIER_COST_PER_1K_INPUT_NANO_USD[actor_tier]
        out_rate = TIER_COST_PER_1K_OUTPUT_NANO_USD[actor_tier]
        return ((input_tokens * in_rate) + (output_tokens * out_rate)) // 1000

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Byte-derived synthetic token proxy (`(utf8_bytes + 3) // 4`) for offline modeling."""
        byte_len = len(text.encode("utf-8"))
        return (byte_len + 3) // 4 if byte_len > 0 else 0

    @staticmethod
    def audit_test_oracle_non_vacuity(
        required_function_name: str,
        test_oracle_fn: Callable[[Dict[str, Any]], None],
    ) -> Tuple[bool, str]:
        """
        Step 1 ($0 Kernel) Anti-Poisoning Meta-Oracle:
        Probes `test_oracle_fn` against 4 mutually incompatible constant stubs
        (`None`, `0`, `1`, `"__DEGENERATE_STUB__"`). A legitimate test oracle may at most
        coincidentally match 1 constant stub, never >= 2 incompatible constant stubs.
        If >= 2 constant stubs pass `test_oracle_fn` without raising an AssertionError,
        the test oracle is tautological/vacuous (e.g., `assert fn(...) is not None`) and
        halts at Step 1 before spending any LLM tokens.
        """
        stubs: Tuple[Any, ...] = (None, 0, 1, "__DEGENERATE_STUB__")
        passed_stubs = 0
        for val in stubs:
            stub_ns: Dict[str, Any] = {
                required_function_name: (lambda *_a, _v=val, **_kw: _v)
            }
            try:
                test_oracle_fn(stub_ns)
            except Exception:
                continue
            else:
                passed_stubs += 1

        if passed_stubs >= 2:
            return (
                False,
                f"HALT_VACUOUS_TEST_ORACLE_AT_STEP_1:PASSED_{passed_stubs}_DEGENERATE_STUBS",
            )
        return True, "OK_ORACLE_DISCRIMINATING"

    @staticmethod
    def verify_code_obeys_architect_contract(
        contract: ArchitecturalSpecContract,
        target_file: str,
        candidate_code: str,
    ) -> Tuple[bool, str]:
        """
        Enforces Law 2 & Law 3:
        Verifies that `TIER_2_FAST_CODER` did not touch unapproved files, import
        unapproved packages, introduce async daemons, omit the required function,
        or exceed `max_lines_changed`.
        """
        if target_file not in contract.allowed_files:
            return False, f"HALT_CONTRACT_FILE_VIOLATION:{target_file}"

        lines = [ln for ln in candidate_code.splitlines() if ln.strip()]
        if len(lines) > contract.max_lines_changed:
            return (
                False,
                f"HALT_CONTRACT_LINE_BUDGET_EXCEEDED:{len(lines)}>{contract.max_lines_changed}",
            )

        ok_ast, ast_reason = TemporalAuthorityGuard.audit_ast_for_async_daemons(
            candidate_code, target_file
        )
        if not ok_ast:
            return False, ast_reason

        tree = ast.parse(candidate_code, filename=target_file)
        allowed_imp_set = set(contract.allowed_imports)
        found_required_fn = False

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    if root_mod not in allowed_imp_set:
                        return False, f"HALT_CONTRACT_UNAPPROVED_IMPORT:{root_mod}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                root_mod = node.module.split(".")[0]
                if root_mod not in allowed_imp_set:
                    return False, f"HALT_CONTRACT_UNAPPROVED_IMPORT:{root_mod}"
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == contract.required_function_name:
                    found_required_fn = True

        if not found_required_fn:
            return (
                False,
                f"HALT_CONTRACT_MISSING_REQUIRED_FUNCTION:{contract.required_function_name}",
            )

        return True, "OK_CONTRACT_SATISFIED"

    @staticmethod
    def reconcile_contract_import_request(
        contract: ArchitecturalSpecContract,
        requested_module: str,
    ) -> Tuple[bool, str, Optional[ArchitecturalSpecContract]]:
        """
        Remediated Monotonic Contract Refinement (Defeats Unilateral Contract Mutiny):
        Child coder cannot unilaterally grant itself third-party dependencies (`numpy`, `requests`)
        or I/O/network/process modules (`urllib`, `socket`, `subprocess`, `os`).
        Amendment succeeds ONLY if `requested_module` is in `PURE_STDLIB_SAFE_MODULES` AND
        was pre-authorized by the Step 2 Architect in `contract.secondary_stdlib_allowlist`
        (preserving S_amended <= S_architect_envelope).
        """
        clean_mod = requested_module.strip().split(".")[0]
        if clean_mod not in PURE_STDLIB_SAFE_MODULES:
            return (
                False,
                f"HALT_MUTINY_FORBIDDEN_CAPABILITY_ESCALATION:{clean_mod}",
                None,
            )
        if clean_mod not in contract.secondary_stdlib_allowlist:
            return (
                False,
                f"HALT_MUTINY_NOT_IN_ARCHITECT_ENVELOPE:{clean_mod}",
                None,
            )
        new_imports = tuple(sorted(set(contract.allowed_imports) | {clean_mod}))
        amended_payload = {
            "allowed_files": list(contract.allowed_files),
            "allowed_imports": list(new_imports),
            "architect_tier": contract.architect_tier,
            "invariant_summary": contract.invariant_summary,
            "max_lines_changed": contract.max_lines_changed,
            "parent_contract_caid": contract.contract_caid,
            "required_function_name": contract.required_function_name,
            "secondary_stdlib_allowlist": list(contract.secondary_stdlib_allowlist),
            "task_id": contract.task_id,
        }
        amended_contract = ArchitecturalSpecContract(
            task_id=contract.task_id,
            architect_tier=contract.architect_tier,
            allowed_files=contract.allowed_files,
            allowed_imports=new_imports,
            required_function_name=contract.required_function_name,
            max_lines_changed=contract.max_lines_changed,
            invariant_summary=contract.invariant_summary,
            contract_caid=sha256_caid(encode_jcs(amended_payload)),
            secondary_stdlib_allowlist=contract.secondary_stdlib_allowlist,
        )
        return True, f"AMENDED_WITHIN_ARCHITECT_ENVELOPE:{clean_mod}", amended_contract

    @staticmethod
    def _kernel_step_record(
        step_number: int,
        step_name: str,
        verdict_code: str,
        artifact_caid: str,
        input_bytes: int = 0,
        output_bytes: int = 0,
    ) -> StepExecutionRecord:
        return StepExecutionRecord(
            step_number=step_number,
            step_name=step_name,
            actor_tier="TIER_0_DETERMINISTIC_KERNEL",
            input_bytes=input_bytes,
            output_bytes=output_bytes,
            input_tokens=0,
            output_tokens=0,
            step_cost_nano_usd=0,
            verdict_code=verdict_code,
            artifact_caid=artifact_caid,
        )

    def execute_5_step_development_flow(
        self,
        task_id: str,
        target_file: str,
        required_function_name: str,
        allowed_imports: Tuple[str, ...],
        max_lines_changed: int,
        coder_generator_fn: Callable[[ArchitecturalSpecContract, int, Optional[str]], str],
        test_oracle_fn: Callable[[Dict[str, Any]], None],
        force_opus_architect: bool = False,
        secondary_stdlib_allowlist: Tuple[str, ...] = (),
        speculative_branches: int = 1,
        check_oracle_non_vacuity: bool = False,
    ) -> FiveStepTrajectoryResult:
        """
        Executes the 5-step cognitive division-of-labor loop and compares actual multi-actor
        cost against a monolithic `TIER_3_OPUS_ARCHITECT` 5-step baseline.
        """
        if speculative_branches <= 0:
            raise ValueError("ERR_INVALID_SPECULATIVE_BRANCHES")

        records: List[StepExecutionRecord] = []
        opus_calls = 0
        fast_coder_calls = 0
        zero_cost_steps = 0

        full_repo_text = "\n".join(self.repo_sources.values())
        full_repo_tokens = self.estimate_tokens(full_repo_text)
        baseline_file_code = self.repo_sources.get(target_file, "")
        target_file_tokens = self.estimate_tokens(baseline_file_code)

        # ======================================================================
        # STEP 1: OBSERVE & SCOPE BLAST RADIUS -> TIER_0_DETERMINISTIC_KERNEL ($0)
        # ======================================================================
        blast = self.blast_governor.calculate_blast_radius((target_file,))
        is_sec_path = AdversarialMutationVerifier.is_security_sensitive_path(target_file)
        sliced_context = AlibabaASTDiffSlicer.slice_modified_ast(
            baseline_file_code, baseline_file_code
        )
        zero_cost_steps += 1

        if check_oracle_non_vacuity:
            oracle_ok, oracle_reason = self.audit_test_oracle_non_vacuity(
                required_function_name, test_oracle_fn
            )
            if not oracle_ok:
                records.append(
                    self._kernel_step_record(
                        step_number=1,
                        step_name="STEP_1_OBSERVE_AND_SCOPE",
                        verdict_code=oracle_reason,
                        artifact_caid=sha256_caid(oracle_reason),
                        input_bytes=len(baseline_file_code.encode("utf-8")),
                    )
                )
                return self._finalize_trajectory(
                    task_id=task_id,
                    final_status="HALT_VACUOUS_TEST_ORACLE",
                    opus_calls=0,
                    fast_coder_calls=0,
                    zero_cost_steps=zero_cost_steps,
                    mutation_score_bps=0,
                    records=records,
                    full_repo_tokens=full_repo_tokens,
                    target_file_tokens=target_file_tokens,
                )

        step1_caid = sha256_caid(
            {
                "blast_radius_bps": blast.blast_radius_bps,
                "security_sensitive": is_sec_path,
                "target_file": target_file,
                "transitive_dependents": list(blast.transitive_dependents),
            }
        )
        records.append(
            self._kernel_step_record(
                step_number=1,
                step_name="STEP_1_OBSERVE_AND_SCOPE",
                verdict_code=f"SCOPED_BLAST_{blast.blast_radius_bps}_BPS",
                artifact_caid=step1_caid,
                input_bytes=len(baseline_file_code.encode("utf-8")),
                output_bytes=len(sliced_context.encode("utf-8")),
            )
        )

        # ======================================================================
        # STEP 2: ARCHITECTURAL SPEC -> Conditional Routing (High Tier vs Fast Planner)
        # ======================================================================
        needs_high_architect = (
            force_opus_architect
            or blast.blast_radius_bps > self.blast_radius_opus_threshold_bps
            or is_sec_path
        )
        architect_tier = (
            self.high_tier_architect if needs_high_architect else "TIER_1_FAST_PLANNER"
        )
        if architect_tier == "TIER_3_OPUS_ARCHITECT":
            opus_calls += 1

        sliced_bytes = len(sliced_context.encode("utf-8"))
        arch_in_tokens = self.estimate_tokens(sliced_context)
        contract_payload = {
            "allowed_files": [target_file],
            "allowed_imports": list(sorted(allowed_imports)),
            "architect_tier": architect_tier,
            "invariant_summary": "Enforce strict boundary conditions and zero async daemons",
            "max_lines_changed": max_lines_changed,
            "required_function_name": required_function_name,
            "secondary_stdlib_allowlist": list(sorted(secondary_stdlib_allowlist)),
            "task_id": task_id,
        }
        contract_bytes = encode_jcs(contract_payload)
        arch_out_tokens = self.estimate_tokens(contract_bytes.decode("utf-8"))
        arch_cost = self.compute_step_cost_nano_usd(
            architect_tier, arch_in_tokens, arch_out_tokens
        )
        contract = ArchitecturalSpecContract(
            task_id=task_id,
            architect_tier=architect_tier,
            allowed_files=(target_file,),
            allowed_imports=tuple(sorted(allowed_imports)),
            required_function_name=required_function_name,
            max_lines_changed=max_lines_changed,
            invariant_summary="Enforce strict boundary conditions and zero async daemons",
            contract_caid=sha256_caid(contract_bytes),
            secondary_stdlib_allowlist=tuple(sorted(secondary_stdlib_allowlist)),
        )
        records.append(
            StepExecutionRecord(
                step_number=2,
                step_name="STEP_2_ARCHITECTURAL_SPEC_CONTRACT",
                actor_tier=architect_tier,
                input_bytes=sliced_bytes,
                output_bytes=len(contract_bytes),
                input_tokens=arch_in_tokens,
                output_tokens=arch_out_tokens,
                step_cost_nano_usd=arch_cost,
                verdict_code=f"CONTRACT_MINTED_BY_{architect_tier}",
                artifact_caid=contract.contract_caid,
            )
        )

        # ======================================================================
        # STEP 3 & STEP 4 LOOP: Fast Coder Synthesis + $0 Pauli Mutation Audit
        # ======================================================================
        feedback_prompt: Optional[str] = None
        final_mutation_bps = 0
        winning_code = ""
        verified_ok = False

        for attempt in range(1, self.max_repair_attempts + 2):
            candidates: List[str] = []
            for branch_idx in range(1, speculative_branches + 1):
                fast_coder_calls += 1
                branch_seed = attempt if speculative_branches == 1 else branch_idx
                cand = coder_generator_fn(contract, branch_seed, feedback_prompt)
                candidates.append(cand)
                coder_in_bytes = len(contract_bytes) + len((feedback_prompt or "").encode("utf-8"))
                coder_out_bytes = len(cand.encode("utf-8"))
                coder_in_tokens = arch_out_tokens + self.estimate_tokens(feedback_prompt or "")
                coder_out_tokens = self.estimate_tokens(cand)
                coder_cost = self.compute_step_cost_nano_usd(
                    "TIER_2_FAST_CODER", coder_in_tokens, coder_out_tokens
                )
                records.append(
                    StepExecutionRecord(
                        step_number=3,
                        step_name=f"STEP_3_SYNTHESIZE_CODE_ATTEMPT_{attempt}_B{branch_idx}",
                        actor_tier="TIER_2_FAST_CODER",
                        input_bytes=coder_in_bytes,
                        output_bytes=coder_out_bytes,
                        input_tokens=coder_in_tokens,
                        output_tokens=coder_out_tokens,
                        step_cost_nano_usd=coder_cost,
                        verdict_code="CANDIDATE_PATCH_GENERATED",
                        artifact_caid=sha256_caid(cand),
                    )
                )

            # Step 4: Deterministic Contract + Pauli Mutation Verification ($0, 0 tokens!)
            zero_cost_steps += 1
            last_contract_error: Optional[str] = None
            last_mut_report = None

            for cand in candidates:
                contract_ok, contract_reason = self.verify_code_obeys_architect_contract(
                    contract, target_file, cand
                )
                if not contract_ok:
                    # Check if this is an unapproved import that can be monotonically reconciled
                    if contract_reason.startswith("HALT_CONTRACT_UNAPPROVED_IMPORT:"):
                        req_mod = contract_reason.partition(":")[2]
                        _rec_ok, _rec_msg, amended = self.reconcile_contract_import_request(
                            contract, req_mod
                        )
                        if amended is not None:
                            contract = amended
                            contract_ok, contract_reason = self.verify_code_obeys_architect_contract(
                                contract, target_file, cand
                            )
                    if not contract_ok:
                        last_contract_error = contract_reason
                        continue

                try:
                    mut_report = self.mutation_verifier.evaluate_mutation_adequacy(
                        target_file, cand, test_oracle_fn
                    )
                except Exception as exc:
                    last_contract_error = f"HALT_CANDIDATE_TEST_FAILURE:{type(exc).__name__}"
                    continue

                last_mut_report = mut_report
                final_mutation_bps = mut_report.mutation_score_bps
                if mut_report.verdict == "ALLOW_MERGE":
                    winning_code = cand
                    verified_ok = True
                    records.append(
                        self._kernel_step_record(
                            step_number=4,
                            step_name=f"STEP_4_PAULI_AUDIT_ATTEMPT_{attempt}",
                            verdict_code=f"{mut_report.verdict}:{mut_report.mutation_score_bps}_BPS",
                            artifact_caid=mut_report.report_caid,
                            input_bytes=len(cand.encode("utf-8")),
                        )
                    )
                    break

            if verified_ok:
                break

            if last_mut_report is None and last_contract_error is not None:
                records.append(
                    self._kernel_step_record(
                        step_number=4,
                        step_name=f"STEP_4_PAULI_AUDIT_ATTEMPT_{attempt}",
                        verdict_code=last_contract_error,
                        artifact_caid=sha256_caid(last_contract_error),
                    )
                )
                return self._finalize_trajectory(
                    task_id=task_id,
                    final_status="HALT_CONTRACT_VIOLATION",
                    opus_calls=opus_calls,
                    fast_coder_calls=fast_coder_calls,
                    zero_cost_steps=zero_cost_steps,
                    mutation_score_bps=final_mutation_bps,
                    records=records,
                    full_repo_tokens=full_repo_tokens,
                    target_file_tokens=target_file_tokens,
                )

            assert last_mut_report is not None
            records.append(
                self._kernel_step_record(
                    step_number=4,
                    step_name=f"STEP_4_PAULI_AUDIT_ATTEMPT_{attempt}",
                    verdict_code=f"{last_mut_report.verdict}:{last_mut_report.mutation_score_bps}_BPS",
                    artifact_caid=last_mut_report.report_caid,
                )
            )
            first_survivor = last_mut_report.survivors[0]
            feedback_prompt = HeadroomLogCompactor.compact_test_log(
                f"FAILED {first_survivor.mutant_id}: {first_survivor.mutation} ({first_survivor.reason})"
            )

        if not verified_ok:
            return self._finalize_trajectory(
                task_id=task_id,
                final_status="HALT_ANSI_86_LOCKOUT",
                opus_calls=opus_calls,
                fast_coder_calls=fast_coder_calls,
                zero_cost_steps=zero_cost_steps,
                mutation_score_bps=final_mutation_bps,
                records=records,
                full_repo_tokens=full_repo_tokens,
                target_file_tokens=target_file_tokens,
            )

        # ======================================================================
        # STEP 5: EO1 WAL LATCH & SCITT RECEIPT -> TIER_0_DETERMINISTIC_KERNEL ($0)
        # ======================================================================
        zero_cost_steps += 1
        step5_payload = {
            "candidate_caid": sha256_caid(winning_code),
            "contract_caid": contract.contract_caid,
            "mutation_score_bps": final_mutation_bps,
            "task_id": task_id,
        }
        step5_bytes = encode_jcs(step5_payload)
        step5_caid = sha256_caid(step5_bytes)
        records.append(
            self._kernel_step_record(
                step_number=5,
                step_name="STEP_5_EO1_WAL_AND_SCITT_SEAL",
                verdict_code="COMMITTED_SCITT_RECEIPT_MINTED",
                artifact_caid=step5_caid,
                input_bytes=len(winning_code.encode("utf-8")),
                output_bytes=len(step5_bytes),
            )
        )

        return self._finalize_trajectory(
            task_id=task_id,
            final_status="COMMITTED",
            opus_calls=opus_calls,
            fast_coder_calls=fast_coder_calls,
            zero_cost_steps=zero_cost_steps,
            mutation_score_bps=final_mutation_bps,
            records=records,
            full_repo_tokens=full_repo_tokens,
            target_file_tokens=target_file_tokens,
        )

    def _finalize_trajectory(
        self,
        task_id: str,
        final_status: str,
        opus_calls: int,
        fast_coder_calls: int,
        zero_cost_steps: int,
        mutation_score_bps: int,
        records: Sequence[StepExecutionRecord],
        full_repo_tokens: int,
        target_file_tokens: int,
    ) -> FiveStepTrajectoryResult:
        total_actual_nano = sum(r.step_cost_nano_usd for r in records)

        # Monolithic Opus Baseline: running TIER_3_OPUS_ARCHITECT across all 5 steps
        # over actual repository tokens (`full_repo_tokens` input + `target_file_tokens` output per step)
        mono_step_cost = self.compute_step_cost_nano_usd(
            "TIER_3_OPUS_ARCHITECT", full_repo_tokens, target_file_tokens
        )
        mono_baseline_nano = mono_step_cost * 5

        savings_bps = max(
            0,
            ((mono_baseline_nano - total_actual_nano) * 10000) // max(1, mono_baseline_nano),
        )
        payload = {
            "cost_savings_bps": savings_bps,
            "fast_coder_invocations": fast_coder_calls,
            "final_status": final_status,
            "monolithic_opus_baseline_nano_usd": mono_baseline_nano,
            "mutation_score_bps": mutation_score_bps,
            "opus_invocations": opus_calls,
            "steps": [r.to_dict() for r in records],
            "task_id": task_id,
            "total_cost_nano_usd": total_actual_nano,
            "zero_cost_kernel_steps": zero_cost_steps,
        }
        return FiveStepTrajectoryResult(
            task_id=task_id,
            final_status=final_status,
            opus_invocations=opus_calls,
            fast_coder_invocations=fast_coder_calls,
            zero_cost_kernel_steps=zero_cost_steps,
            total_cost_nano_usd=total_actual_nano,
            monolithic_opus_baseline_nano_usd=mono_baseline_nano,
            cost_savings_bps=savings_bps,
            mutation_score_bps=mutation_score_bps,
            step_records=tuple(records),
            trajectory_caid=sha256_caid(payload),
        )
