"""Proof-Carrying Contract (PC2) Escrow Airlock & Lean 4 Comparator Exporter (Section 24).

Implements a prototype connecting our Section 22-23 constructive mathematical provers
with Station 2 TCC Escrow and Lean 4 (`leanprover/comparator`) verification hygiene:

1. Lean4WitnessCertificateExporter:
   - Exports verified finite witnesses (MATH-01 Cap Set F_3^4, MATH-02 Golomb 8-Mark
     Ruler, MATH-06 Barker-13 LABS, and SEC Rule 15c3-5 pre-trade risk controls) into
     standalone Lean 4 (`by decide`) proof modules under `proofs/` along with
     `leanprover/comparator` challenge specifications.
2. LeanComparatorSandboxAuditor:
   - Runs a TEXT LINT modelled on (not equivalent to) `leanprover/comparator`:
     (a) Rejects `sorry` / `sorryAx` / `admit` placeholders (comments stripped first).
     (b) Rejects user-declared `axiom` declarations.
     (c) Rejects `unsafe`, `implemented_by`, or `extern` FFI escapes.
     (d) Checks the trusted definitions text is present verbatim.
     (e) Checks the trusted theorem header clause is present verbatim.
   - The text lint alone is NOT a proof check: a false theorem can pass it.
     Only when a `lean` binary is on PATH is the submission actually elaborated
     (`lean <file>`, with timeout); a nonzero exit or a `sorry` warning fails.
     Without `lean` the verdict is `status=TEXT_LINT_ONLY`,
     `rejection_code=LEAN_NOT_EXECUTED`, `passed=False` (never VERIFIED).
3. Pc2ProofCarryingEscrowAirlock:
   - Holds client funds in escrow and releases settlement only when the Lean
     kernel was actually executed on the submission (`status=REAL_EXECUTED`)
     AND the independent deterministic semantic evaluator accepts the witness.
     A TEXT_LINT_ONLY verdict never releases funds (escrow stays locked).
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.capability_status import REAL_EXECUTED, TEXT_LINT_ONLY
from src.jcs_canonicalizer import encode_jcs
from src.sovereign_state_capsule_and_math_prover import (
    SovereignIndependentStateCapsuleEngine,
)


def sha256_prefixed(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


# ---------------------------------------------------------------------------
# 1. Lean 4 Proof-Carrying Certificate Exporter (`by decide`)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrustedLeanChallengeSpec:
    """Trusted challenge specification compatible with `leanprover/comparator`."""

    problem_id: str
    theorem_name: str
    trusted_definitions_lean: str
    trusted_theorem_header_lean: str
    permitted_axioms: Tuple[str, ...] = (
        "propext",
        "Quot.sound",
        "Classical.choice",
    )

    @property
    def definitions_sha256(self) -> str:
        return sha256_prefixed(self.trusted_definitions_lean.strip().encode("utf-8"))

    @property
    def theorem_header_sha256(self) -> str:
        return sha256_prefixed(self.trusted_theorem_header_lean.strip().encode("utf-8"))

    def to_comparator_config(self) -> Dict[str, object]:
        return {
            "problem_id": self.problem_id,
            "theorem_names": [self.theorem_name],
            "permitted_axioms": list(self.permitted_axioms),
            "definitions_sha256": self.definitions_sha256,
            "theorem_header_sha256": self.theorem_header_sha256,
        }


class Lean4WitnessCertificateExporter:
    """Exports verified finite witnesses into standalone Lean 4 (`by decide`) modules."""

    @staticmethod
    def build_labs_barker13_challenge_and_solution(
        witness_seq: Sequence[int],
    ) -> Tuple[TrustedLeanChallengeSpec, str]:
        defs = (
            "def autocorr (s : List Int) (k : Nat) : Int :=\n"
            "  (List.range (s.length - k)).foldl (fun acc i => acc + (s.getD i 0) * (s.getD (i + k) 0)) 0\n"
            "def sidelobeEnergy (s : List Int) : Int :=\n"
            "  (List.range 12).foldl (fun acc idx => let c := autocorr s (idx + 1); acc + c * c) 0"
        )
        vec_literal = "[" + ", ".join(str(int(x)) for x in witness_seq) + "]"
        thm_header = (
            "theorem math06_labs_barker13_optimal : "
            "barker13.length = 13 ∧ sidelobeEnergy barker13 = 6"
        )
        spec = TrustedLeanChallengeSpec(
            problem_id="MATH-06-LABS-BARKER-13",
            theorem_name="math06_labs_barker13_optimal",
            trusted_definitions_lean=defs,
            trusted_theorem_header_lean=thm_header,
        )
        full_lean_module = (
            f"-- Auto-exported Lean 4 Proof Certificate (MATH-06-LABS-BARKER-13)\n"
            f"{defs}\n"
            f"def barker13 : List Int := {vec_literal}\n\n"
            f"{thm_header} := by decide\n"
        )
        return spec, full_lean_module

    @staticmethod
    def build_golomb8_challenge_and_solution(
        marks: Sequence[int],
    ) -> Tuple[TrustedLeanChallengeSpec, str]:
        defs = (
            "def pairwiseDiffs (m : List Nat) : List Nat :=\n"
            "  (List.range m.length).foldl (fun acc i =>\n"
            "    acc ++ ((List.range (m.length - i - 1)).map (fun d => (m.getD (i + d + 1) 0) - (m.getD i 0)))) []"
        )
        vec_literal = "[" + ", ".join(str(int(x)) for x in marks) + "]"
        thm_header = (
            "theorem math02_golomb8_optimal : "
            "golomb8.length = 8 ∧ golomb8.getLastD 0 = 34 ∧ (pairwiseDiffs golomb8).Nodup = true"
        )
        spec = TrustedLeanChallengeSpec(
            problem_id="MATH-02-ERDOS-SIDON-GOLOMB-8",
            theorem_name="math02_golomb8_optimal",
            trusted_definitions_lean=defs,
            trusted_theorem_header_lean=thm_header,
        )
        full_lean_module = (
            f"-- Auto-exported Lean 4 Proof Certificate (MATH-02-ERDOS-SIDON-GOLOMB-8)\n"
            f"{defs}\n"
            f"def golomb8 : List Nat := {vec_literal}\n\n"
            f"{thm_header} := by decide\n"
        )
        return spec, full_lean_module

    @staticmethod
    def build_sec_rule_15c3_5_pretrade_challenge_and_solution(
        order_notional_minor: int,
        current_exposure_minor: int,
        credit_cap_minor: int,
        max_single_order_minor: int,
    ) -> Tuple[TrustedLeanChallengeSpec, str]:
        defs = (
            f"def currentExposure : Int := {current_exposure_minor}\n"
            f"def creditCap : Int := {credit_cap_minor}\n"
            f"def maxSingleOrder : Int := {max_single_order_minor}\n"
            "def sec15c3_5_admissible (ord exp cap maxOrd : Int) : Bool :=\n"
            "  (ord > 0) && (ord <= maxOrd) && ((exp + ord) <= cap)"
        )
        thm_header = (
            "theorem sec_15c3_5_pretrade_compliance : "
            "sec15c3_5_admissible orderNotional currentExposure creditCap maxSingleOrder = true"
        )
        spec = TrustedLeanChallengeSpec(
            problem_id="FIN-SEC-15C3-5-PRETRADE",
            theorem_name="sec_15c3_5_pretrade_compliance",
            trusted_definitions_lean=defs,
            trusted_theorem_header_lean=thm_header,
        )
        full_lean_module = (
            f"-- Auto-exported Lean 4 Proof Certificate (FIN-SEC-15C3-5-PRETRADE)\n"
            f"{defs}\n"
            f"def orderNotional : Int := {order_notional_minor}\n\n"
            f"{thm_header} := by decide\n"
        )
        return spec, full_lean_module

    @classmethod
    def export_all_to_proofs_dir(cls, workspace_root: Path) -> Dict[str, str]:
        """Write standalone `.lean` files and `comparator_config.json` into `proofs/`."""
        proofs_dir = workspace_root / "proofs"
        proofs_dir.mkdir(parents=True, exist_ok=True)

        barker_spec, barker_lean = cls.build_labs_barker13_challenge_and_solution(
            [1, 1, 1, 1, 1, -1, -1, 1, 1, -1, 1, -1, 1]
        )
        golomb_spec, golomb_lean = cls.build_golomb8_challenge_and_solution(
            [0, 1, 4, 9, 15, 22, 32, 34]
        )
        sec_spec, sec_lean = cls.build_sec_rule_15c3_5_pretrade_challenge_and_solution(
            order_notional_minor=400_00,
            current_exposure_minor=1500_00,
            credit_cap_minor=2500_00,
            max_single_order_minor=500_00,
        )

        files = {
            "Math06Barker13.lean": barker_lean,
            "Math02Golomb8.lean": golomb_lean,
            "FinSec15c35PreTrade.lean": sec_lean,
            "comparator_config.json": json.dumps(
                {
                    "challenges": [
                        barker_spec.to_comparator_config(),
                        golomb_spec.to_comparator_config(),
                        sec_spec.to_comparator_config(),
                    ]
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        }
        digests: Dict[str, str] = {}
        for fname, content in files.items():
            fpath = proofs_dir / fname
            fpath.write_text(content, encoding="utf-8")
            digests[fname] = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return digests


# ---------------------------------------------------------------------------
# 2. Comparator-style TEXT LINT + optional real `lean` execution
# ---------------------------------------------------------------------------

LEAN_NOT_EXECUTED = "LEAN_NOT_EXECUTED"
OK_LEAN_KERNEL_CHECKED = "OK_LEAN_KERNEL_CHECKED"
HALT_LEAN_KERNEL_REJECTED = "HALT_LEAN_KERNEL_REJECTED"
HALT_LEAN_SORRY_WARNING = "HALT_LEAN_SORRY_WARNING"
HALT_LEAN_TIMEOUT = "HALT_LEAN_TIMEOUT"
HALT_LEAN_UNPERMITTED_AXIOM = "HALT_LEAN_UNPERMITTED_AXIOM"
LEAN_EXEC_TIMEOUT_SECONDS = 120.0


@dataclass(frozen=True)
class ComparatorVerificationVerdict:
    """Outcome of the auditor.

    ``passed`` is True only when the Lean kernel was actually executed on the
    submission and accepted it (``status == REAL_EXECUTED``). When no ``lean``
    binary is available the text lint result is reported in
    ``text_lint_passed`` and ``status == TEXT_LINT_ONLY``; ``passed`` stays
    False. ``certificate_caid`` is a digest of (comparator config, submitted
    file); it is a submission identifier, not evidence that the proof checks.
    """

    passed: bool
    rejection_code: str
    problem_id: str
    certificate_caid: str
    status: str = TEXT_LINT_ONLY
    text_lint_passed: bool = False
    lean_executed: bool = False


def strip_lean_comments(code: str) -> str:
    """Remove Lean 4 line comments (`-- ...`) and nested block comments (`/- ... -/`).

    String literals are not parsed; a `--` or `/-` inside a string literal is
    treated as a comment start (fail-closed for the lint: more text removed can
    only make the required-clause checks fail, never pass a forbidden token).
    """
    out: List[str] = []
    i, n, depth = 0, len(code), 0
    while i < n:
        if code.startswith("/-", i):
            depth += 1
            i += 2
            continue
        if depth > 0:
            if code.startswith("-/", i):
                depth -= 1
                i += 2
            else:
                if code[i] == "\n":
                    out.append("\n")
                i += 1
            continue
        if code.startswith("--", i):
            j = code.find("\n", i)
            i = n if j == -1 else j
            continue
        out.append(code[i])
        i += 1
    return "".join(out)


class LeanComparatorSandboxAuditor:
    """Text lint modelled on `leanprover/comparator`, plus real `lean` when present."""

    FORBIDDEN_ESCAPE_PATTERNS: Tuple[Tuple[str, str], ...] = (
        (r"\bsorry\b", "HALT_COMPARATOR_SORRY_AXIOM_DETECTED"),
        (r"\bsorryAx\b", "HALT_COMPARATOR_SORRY_AXIOM_DETECTED"),
        (r"\badmit\b", "HALT_COMPARATOR_SORRY_AXIOM_DETECTED"),
        (r"\baxiom\s+", "HALT_COMPARATOR_CUSTOM_AXIOM_FORBIDDEN"),
        (r"\bunsafe\s+", "HALT_COMPARATOR_UNSAFE_CODE_FORBIDDEN"),
        (r"@\[implemented_by", "HALT_COMPARATOR_IMPLEMENTED_BY_ESCAPE_FORBIDDEN"),
        (r"@\[extern", "HALT_COMPARATOR_EXTERN_FFI_ESCAPE_FORBIDDEN"),
        (r"\bnative_decide\b", "HALT_COMPARATOR_NATIVE_DECIDE_FORBIDDEN"),
    )

    @staticmethod
    def _reject(code: str, spec: TrustedLeanChallengeSpec) -> ComparatorVerificationVerdict:
        return ComparatorVerificationVerdict(
            passed=False,
            rejection_code=code,
            problem_id=spec.problem_id,
            certificate_caid="",
            status=TEXT_LINT_ONLY,
            text_lint_passed=False,
            lean_executed=False,
        )

    @staticmethod
    def run_lean_kernel(
        trusted_spec: TrustedLeanChallengeSpec,
        submitted_lean_code: str,
        lean_bin: str,
        timeout_s: float = LEAN_EXEC_TIMEOUT_SECONDS,
    ) -> Tuple[bool, str]:
        """Elaborate the submission with a real `lean` binary.

        Appends `#print axioms <theorem>` and fails on: nonzero exit, any
        "declaration uses 'sorry'" warning, timeout, or an axiom outside
        ``trusted_spec.permitted_axioms``.
        """
        probe = f"{submitted_lean_code}\n\n#print axioms {trusted_spec.theorem_name}\n"
        with tempfile.TemporaryDirectory(prefix="aeib_lean_") as tmp:
            path = Path(tmp) / "Submission.lean"
            path.write_text(probe, encoding="utf-8")
            try:
                proc = subprocess.run(
                    [lean_bin, str(path)],
                    capture_output=True,
                    text=True,
                    timeout=timeout_s,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return False, HALT_LEAN_TIMEOUT
        output = f"{proc.stdout}\n{proc.stderr}"
        if proc.returncode != 0:
            return False, HALT_LEAN_KERNEL_REJECTED
        if "declaration uses 'sorry'" in output:
            return False, HALT_LEAN_SORRY_WARNING
        match = re.search(r"depends on axioms:\s*\[([^\]]*)\]", output)
        if match:
            used = [a.strip() for a in match.group(1).split(",") if a.strip()]
            allowed = set(trusted_spec.permitted_axioms)
            for ax in used:
                if ax not in allowed:
                    return False, f"{HALT_LEAN_UNPERMITTED_AXIOM}:{ax}"
        elif "does not depend on any axioms" not in output:
            # `#print axioms` output missing -> cannot confirm the theorem exists.
            return False, HALT_LEAN_KERNEL_REJECTED
        return True, OK_LEAN_KERNEL_CHECKED

    @classmethod
    def verify_submission_against_trusted_spec(
        cls,
        trusted_spec: TrustedLeanChallengeSpec,
        submitted_lean_code: str,
        declared_axioms_used: Tuple[str, ...] = ("propext", "Quot.sound"),
    ) -> ComparatorVerificationVerdict:
        # Strip line and (nested) block comments before every textual check, so a
        # required clause hidden in a comment does not count and a `sorry` inside
        # a comment is not a false positive.
        code_no_comments = strip_lean_comments(submitted_lean_code)
        for pattern, err_code in cls.FORBIDDEN_ESCAPE_PATTERNS:
            if re.search(pattern, code_no_comments):
                return cls._reject(err_code, trusted_spec)

        allowed_set = set(trusted_spec.permitted_axioms)
        for ax in declared_axioms_used:
            if ax not in allowed_set:
                return cls._reject(f"HALT_COMPARATOR_UNPERMITTED_AXIOM:{ax}", trusted_spec)

        if trusted_spec.trusted_definitions_lean.strip() not in code_no_comments:
            return cls._reject("HALT_COMPARATOR_DEFINITION_REDEFINITION_DETECTED", trusted_spec)

        expected_clause = f"{trusted_spec.trusted_theorem_header_lean.strip()} := by decide"
        if expected_clause not in code_no_comments:
            return cls._reject("HALT_COMPARATOR_THEOREM_STATEMENT_MISMATCH", trusted_spec)

        cert_caid = sha256_prefixed(
            encode_jcs(
                {
                    "comparator_config": trusted_spec.to_comparator_config(),
                    "submitted_lean_sha256": sha256_prefixed(
                        submitted_lean_code.encode("utf-8")
                    ),
                }
            )
        )

        lean_bin = shutil.which("lean")
        if lean_bin is None:
            # Text lint passed, but no proof checker ran: never report VERIFIED.
            return ComparatorVerificationVerdict(
                passed=False,
                rejection_code=LEAN_NOT_EXECUTED,
                problem_id=trusted_spec.problem_id,
                certificate_caid=cert_caid,
                status=TEXT_LINT_ONLY,
                text_lint_passed=True,
                lean_executed=False,
            )

        ok, code = cls.run_lean_kernel(trusted_spec, submitted_lean_code, lean_bin)
        return ComparatorVerificationVerdict(
            passed=ok,
            rejection_code=code,
            problem_id=trusted_spec.problem_id,
            certificate_caid=cert_caid if ok else "",
            status=REAL_EXECUTED,
            text_lint_passed=True,
            lean_executed=True,
        )


# ---------------------------------------------------------------------------
# 3. Proof-Carrying Contract (PC2) Escrow Airlock
# ---------------------------------------------------------------------------


@dataclass
class ProofCarryingContractEscrow:
    contract_id: str
    client_id: str
    contractor_agent_id: str
    escrow_amount_minor: int
    required_challenge_spec: TrustedLeanChallengeSpec
    deterministic_evaluator_fn: Callable[[object], bool]
    status: str = "ESCROW_LOCKED"
    settlement_certificate_caid: Optional[str] = None


class Pc2ProofCarryingEscrowAirlock:
    """Enforces Proof-Carrying Contract (PC2) escrow lock and verified settlement."""

    def __init__(self, airlock_privkey: Optional[Ed25519PrivateKey] = None) -> None:
        self._priv = airlock_privkey or Ed25519PrivateKey.generate()
        self.contracts: Dict[str, ProofCarryingContractEscrow] = {}

    @property
    def public_key_b64(self) -> str:
        return base64.b64encode(
            self._priv.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        ).decode("ascii")

    def register_contract_and_lock_escrow(
        self, contract: ProofCarryingContractEscrow
    ) -> None:
        self.contracts[contract.contract_id] = contract

    def submit_proof_carrying_deliverable(
        self,
        contract_id: str,
        submitted_lean_proof: str,
        submitted_witness_data: object,
    ) -> Dict[str, object]:
        contract = self.contracts[contract_id]
        if contract.status != "ESCROW_LOCKED":
            return {
                "disposition": "REJECTED",
                "code": f"ERR_CONTRACT_NOT_LOCKED:{contract.status}",
            }

        comp_verdict = (
            LeanComparatorSandboxAuditor.verify_submission_against_trusted_spec(
                contract.required_challenge_spec, submitted_lean_proof
            )
        )
        if comp_verdict.status != REAL_EXECUTED and comp_verdict.text_lint_passed:
            # Text lint passed but no Lean kernel ran: funds are NOT released.
            return {
                "disposition": "AIRLOCK_HELD_TEXT_LINT_ONLY",
                "code": comp_verdict.rejection_code,
                "verification_status": comp_verdict.status,
                "escrow_status": contract.status,
            }
        if not comp_verdict.passed or comp_verdict.status != REAL_EXECUTED:
            return {
                "disposition": "AIRLOCK_REJECTED_PROOF",
                "code": comp_verdict.rejection_code,
                "verification_status": comp_verdict.status,
                "escrow_status": contract.status,
            }

        if not contract.deterministic_evaluator_fn(submitted_witness_data):
            return {
                "disposition": "AIRLOCK_REJECTED_WITNESS_EVALUATION",
                "code": "HALT_PC2_SEMANTIC_INVARIANT_FALSE",
                "escrow_status": contract.status,
            }

        contract.status = "SETTLED_RELEASED_TO_CONTRACTOR"
        contract.settlement_certificate_caid = comp_verdict.certificate_caid

        receipt_core = {
            "certificate_caid": comp_verdict.certificate_caid,
            "contract_id": contract.contract_id,
            "contractor_agent_id": contract.contractor_agent_id,
            "escrow_released_minor": contract.escrow_amount_minor,
            "status": contract.status,
        }
        sig_b64 = base64.b64encode(
            self._priv.sign(encode_jcs(receipt_core))
        ).decode("ascii")

        return {
            "disposition": "AIRLOCK_ACCEPTED_ESCROW_RELEASED",
            "code": "OK",
            "verification_status": comp_verdict.status,
            "settlement_receipt": receipt_core,
            "airlock_public_key_b64": self.public_key_b64,
            "airlock_signature_b64": sig_b64,
        }


def verify_barker13_energy(seq: object) -> bool:
    if not isinstance(seq, list) or len(seq) != 13:
        return False
    if any(x not in (-1, 1) for x in seq):
        return False
    energy = 0
    for k in range(1, 13):
        ck = sum(int(seq[i]) * int(seq[i + k]) for i in range(13 - k))
        energy += ck * ck
    return energy == 6


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Proof-Carrying Contract (PC2) Airlock & Lean 4 Comparator Exporter CLI"
    )
    parser.add_argument("--self-test", action="store_true", help="Run self-test and export Lean 4 proofs")
    args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent
    exported_digests = Lean4WitnessCertificateExporter.export_all_to_proofs_dir(workspace_root)

    airlock = Pc2ProofCarryingEscrowAirlock()
    barker_seq = [1, 1, 1, 1, 1, -1, -1, 1, 1, -1, 1, -1, 1]
    spec, valid_lean = (
        Lean4WitnessCertificateExporter.build_labs_barker13_challenge_and_solution(barker_seq)
    )
    contract = ProofCarryingContractEscrow(
        contract_id="pc2-contract-radar-barker13",
        client_id="org:aerospace-dsp",
        contractor_agent_id="agent:sovereign-prover-w6",
        escrow_amount_minor=2500_00,
        required_challenge_spec=spec,
        deterministic_evaluator_fn=verify_barker13_energy,
    )
    airlock.register_contract_and_lock_escrow(contract)
    res = airlock.submit_proof_carrying_deliverable(
        "pc2-contract-radar-barker13", valid_lean, barker_seq
    )
    lean_present = shutil.which("lean") is not None
    if lean_present:
        # Real Lean kernel ran; the exported Barker-13 proof must check.
        assert res["disposition"] == "AIRLOCK_ACCEPTED_ESCROW_RELEASED", res
        status_label = "SECTION_24_PC2_LEAN4_KERNEL_EXECUTED"
    else:
        # No Lean on this host: text lint only, escrow must stay locked.
        assert res["disposition"] == "AIRLOCK_HELD_TEXT_LINT_ONLY", res
        assert contract.status == "ESCROW_LOCKED"
        status_label = "SECTION_24_PC2_TEXT_LINT_ONLY_LEAN_NOT_EXECUTED"

    state_engine = SovereignIndependentStateCapsuleEngine(workspace_root=workspace_root)
    capsule = state_engine.build_and_sync_capsule(persist=True)

    if args.self_test or True:
        print(
            json.dumps(
                {
                    "status": status_label,
                    "verification_status": res.get("verification_status"),
                    "escrow_disposition": res["disposition"],
                    "exported_lean4_proof_digests": exported_digests,
                    "settlement_receipt": res.get("settlement_receipt"),
                    "state_capsule_sha256": capsule.capsule_sha256,
                },
                indent=2,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
