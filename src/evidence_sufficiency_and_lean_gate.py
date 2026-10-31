#!/usr/bin/env python3
"""
SovereignNexus Phase VII Priority #2 & #3:
1. Remediated Narrow Formal Theorem & Axiom Audit Gate (`NarrowFormalTheoremGate`).
2. AEIB Benchmark v0.2 Track 6: Evidence Sufficiency Gate (`EvidenceSufficiencyGate`).
Status: INTERNAL PREVIEW COMMISSIONED

Enforces:
- Claims without machine-checkable artifacts -> `UNEVALUATED_NO_MACHINE_CHECKABLE_ARTIFACT`.
- Missing Lean 4 binary -> `UNEVALUATED_KERNEL_UNAVAILABLE` (`verified=False`, never simulated).
- Unapproved import namespaces (e.g., `OAI.MeasureTheory`), `lakefile.lean` packages, or
  banned keywords (`sorry`, `admit`, `axiom`, `unsafe`, `constant`, `extern`, `implemented_by`)
  -> `HALT_AXIOM_SCOPE_UNDECLARED`.
- Theorem statement signature mismatch -> `HALT_CLAIM_SCOPE_MISMATCH`.
- Code passes tests but mutation adequacy fails or has security-sensitive survivor
  -> `BLOCK_MERGE_TEST_ADEQUACY_FAILURE`.
- 100% (`10000 bps`) of required causal evidence receipts must exist in the provenance field
  plus a valid execution receipt -> otherwise `HALT_EPISTEMIC_DRIFT` (defeating 75% ratio smuggling).
- Transport timeout without reconciliation receipt -> `EFFECT_INDETERMINATE_RECONCILIATION_REQUIRED`.
"""

import math
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.adversarial_mutation_verifier import MutationAdequacyReport, sha256_caid
from src.jcs_canonicalizer import encode_jcs

REQUIRED_EVIDENCE_COUPLING_BPS: int = 10000  # claim: config

BANNED_LEAN4_KEYWORDS: FrozenSet[str] = frozenset(
    {"sorry", "admit", "unsafe", "axiom", "constant", "extern", "implemented_by"}
)

DEFAULT_TRUSTED_IMPORT_ROOTS: FrozenSet[str] = frozenset(
    {"Std", "Init", "Mathlib", "Lean"}
)

DEFAULT_TRUSTED_LAKE_PACKAGES: FrozenSet[str] = frozenset(
    {"mathlib", "std", "aesop", "proofwidgets"}
)

IMPORT_LINE_RE = re.compile(r"^\s*import\s+([A-Za-z0-9_.]+)", re.MULTILINE)
THEOREM_DECL_RE = re.compile(r"\btheorem\s+([A-Za-z0-9_']+)\s*(.+?):=", re.DOTALL)
LAKE_DEP_RE = re.compile(r"\brequire\s+([A-Za-z0-9_\"'-]+)", re.MULTILINE)


def wilson_95_interval_bps(successes: int, total: int) -> Tuple[int, int]:
    """Compute conservative Wilson 95% confidence interval in integer basis points [0..10000]."""
    if total <= 0 or successes < 0 or successes > total:
        raise ValueError("ERR_INVALID_WILSON_COUNTS")
    z = 1.959963984540054
    z2 = z * z
    phat = successes / total
    denom = 1.0 + z2 / total
    center = (phat + z2 / (2.0 * total)) / denom
    half = (z * math.sqrt((phat * (1.0 - phat) + z2 / (4.0 * total)) / total)) / denom
    low_bps = max(0, int(math.floor((center - half) * 10000.0)))
    high_bps = min(10000, int(math.ceil((center + half) * 10000.0)))
    return (low_bps, high_bps)


@dataclass(frozen=True)
class NarrowFormalProofReceipt:
    verified: bool
    status_code: str
    theorem_name: str
    expected_statement_signature: str
    actual_statement_signature: str
    declared_imports: Tuple[str, ...]
    toolchain_version: str
    source_digest_caid: str
    signature_hex: str
    receipt_caid: str

    def to_payload(self) -> Dict[str, Any]:
        return {
            "actual_statement_signature": self.actual_statement_signature,
            "declared_imports": list(self.declared_imports),
            "expected_statement_signature": self.expected_statement_signature,
            "source_digest_caid": self.source_digest_caid,
            "status_code": self.status_code,
            "theorem_name": self.theorem_name,
            "toolchain_version": self.toolchain_version,
            "verified": self.verified,
        }


class NarrowFormalTheoremGate:
    """
    Narrow Formal Verification & Axiom Audit Gate for Lean 4 artifacts.
    Records kernel acceptance strictly relative to the audited import closure,
    absence of banned axiom keywords, exact theorem statement signature, and toolchain.
    When the Lean kernel binary is absent, returns `UNEVALUATED_KERNEL_UNAVAILABLE` (`verified=False`).
    """

    def __init__(
        self,
        trusted_import_roots: FrozenSet[str] = DEFAULT_TRUSTED_IMPORT_ROOTS,
        trusted_lake_packages: FrozenSet[str] = DEFAULT_TRUSTED_LAKE_PACKAGES,
        signing_key: Optional[ed25519.Ed25519PrivateKey] = None,
        lean_executable: str = "lean",
        timeout_seconds: int = 15,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("ERR_INVALID_TIMEOUT_SECONDS")
        self.trusted_import_roots = trusted_import_roots
        self.trusted_lake_packages = trusted_lake_packages
        self._priv_key = signing_key or ed25519.Ed25519PrivateKey.generate()
        self.pubkey = self._priv_key.public_key()
        self.lean_executable = lean_executable
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def normalize_signature(sig_text: str) -> str:
        return " ".join(sig_text.strip().split())

    def evaluate_formal_artifact(
        self,
        claimed_theorem_name: str,
        expected_statement_signature: str,
        lean_source_code: Optional[str],
        lakefile_content: str = "",
        toolchain_version: str = "leanprover/lean4:v4.12.0",
    ) -> NarrowFormalProofReceipt:
        # Case 1: Natural-language claim with no formal machine-checkable artifact
        if not lean_source_code or not lean_source_code.strip():
            return self._seal(
                verified=False,
                status_code="UNEVALUATED_NO_MACHINE_CHECKABLE_ARTIFACT",
                theorem_name=claimed_theorem_name,
                expected_sig=expected_statement_signature,
                actual_sig="",
                imports=(),
                toolchain=toolchain_version,
                source_caid=sha256_caid(b""),
            )

        source_caid = sha256_caid(lean_source_code.encode("utf-8"))
        imports = tuple(sorted(set(IMPORT_LINE_RE.findall(lean_source_code))))

        # Case 2A: Audit `lakefile.lean` for unapproved external packages
        for req_pkg in LAKE_DEP_RE.findall(lakefile_content):
            clean_pkg = req_pkg.strip("\"'")
            if clean_pkg.lower() not in self.trusted_lake_packages:
                return self._seal(
                    verified=False,
                    status_code=f"HALT_AXIOM_SCOPE_UNDECLARED:LAKE_PKG_{clean_pkg}",
                    theorem_name=claimed_theorem_name,
                    expected_sig=expected_statement_signature,
                    actual_sig="",
                    imports=imports,
                    toolchain=toolchain_version,
                    source_caid=source_caid,
                )

        # Case 2B: Audit `import` closure against trusted foundation roots (blocks `OAI.*` custom namespaces)
        for imp in imports:
            root_ns = imp.split(".")[0]
            if root_ns not in self.trusted_import_roots:
                return self._seal(
                    verified=False,
                    status_code=f"HALT_AXIOM_SCOPE_UNDECLARED:UNTRUSTED_IMPORT_{imp}",
                    theorem_name=claimed_theorem_name,
                    expected_sig=expected_statement_signature,
                    actual_sig="",
                    imports=imports,
                    toolchain=toolchain_version,
                    source_caid=source_caid,
                )

        # Case 2C: Scan for banned axiom/cheating keywords (`sorry`, `admit`, `axiom`, `unsafe`, `extern`)
        for kw in sorted(BANNED_LEAN4_KEYWORDS):
            if re.search(r"\b" + re.escape(kw) + r"\b", lean_source_code):
                return self._seal(
                    verified=False,
                    status_code=f"HALT_AXIOM_SCOPE_UNDECLARED:BANNED_KEYWORD_{kw.upper()}",
                    theorem_name=claimed_theorem_name,
                    expected_sig=expected_statement_signature,
                    actual_sig="",
                    imports=imports,
                    toolchain=toolchain_version,
                    source_caid=source_caid,
                )

        # Case 3: Verify theorem declaration name & normalized statement signature match claimed spec
        matches = THEOREM_DECL_RE.findall(lean_source_code)
        matched_sig: Optional[str] = None
        first_found_sig: str = ""
        for found_name, found_sig in matches:
            norm_found = self.normalize_signature(found_sig)
            if not first_found_sig:
                first_found_sig = norm_found
            if found_name == claimed_theorem_name:
                matched_sig = norm_found
                break

        norm_expected = self.normalize_signature(expected_statement_signature)
        if matched_sig is None or matched_sig != norm_expected:
            return self._seal(
                verified=False,
                status_code="HALT_CLAIM_SCOPE_MISMATCH",
                theorem_name=claimed_theorem_name,
                expected_sig=norm_expected,
                actual_sig=matched_sig if matched_sig is not None else first_found_sig,
                imports=imports,
                toolchain=toolchain_version,
                source_caid=source_caid,
            )

        # Case 4: Hermetic out-of-process Lean 4 kernel invocation (Never simulate a pass)
        with tempfile.TemporaryDirectory(prefix="aeib_lean4_") as tmpdir:
            file_path = os.path.join(tmpdir, "artifact.lean")
            with open(file_path, "w", encoding="utf-8") as fh:
                fh.write(lean_source_code)

            try:
                proc = subprocess.run(
                    [self.lean_executable, file_path],
                    capture_output=True,
                    text=True,
                    cwd=tmpdir,
                    env={"PATH": "/usr/bin:/bin", "HOME": tmpdir},
                    timeout=self.timeout_seconds,
                    check=False,
                )
            except FileNotFoundError:
                return self._seal(
                    verified=False,
                    status_code="UNEVALUATED_KERNEL_UNAVAILABLE",
                    theorem_name=claimed_theorem_name,
                    expected_sig=norm_expected,
                    actual_sig=matched_sig,
                    imports=imports,
                    toolchain=toolchain_version,
                    source_caid=source_caid,
                )
            except subprocess.TimeoutExpired:
                return self._seal(
                    verified=False,
                    status_code="UNEVALUATED_KERNEL_TIMEOUT",
                    theorem_name=claimed_theorem_name,
                    expected_sig=norm_expected,
                    actual_sig=matched_sig,
                    imports=imports,
                    toolchain=toolchain_version,
                    source_caid=source_caid,
                )

        if proc.returncode != 0:
            return self._seal(
                verified=False,
                status_code="KERNEL_REJECTED",
                theorem_name=claimed_theorem_name,
                expected_sig=norm_expected,
                actual_sig=matched_sig,
                imports=imports,
                toolchain=toolchain_version,
                source_caid=source_caid,
            )

        return self._seal(
            verified=True,
            status_code="KERNEL_ACCEPTED",
            theorem_name=claimed_theorem_name,
            expected_sig=norm_expected,
            actual_sig=matched_sig,
            imports=imports,
            toolchain=toolchain_version,
            source_caid=source_caid,
        )

    def verify_receipt_signature(self, receipt: NarrowFormalProofReceipt) -> bool:
        try:
            self.pubkey.verify(
                bytes.fromhex(receipt.signature_hex),
                encode_jcs(receipt.to_payload()),
            )
            return True
        except (InvalidSignature, ValueError):
            return False

    def _seal(
        self,
        verified: bool,
        status_code: str,
        theorem_name: str,
        expected_sig: str,
        actual_sig: str,
        imports: Tuple[str, ...],
        toolchain: str,
        source_caid: str,
    ) -> NarrowFormalProofReceipt:
        payload = {
            "actual_statement_signature": actual_sig,
            "declared_imports": list(imports),
            "expected_statement_signature": expected_sig,
            "source_digest_caid": source_caid,
            "status_code": status_code,
            "theorem_name": theorem_name,
            "toolchain_version": toolchain,
            "verified": verified,
        }
        sig_hex = self._priv_key.sign(encode_jcs(payload)).hex()
        receipt_caid = sha256_caid({**payload, "signature_hex": sig_hex})
        return NarrowFormalProofReceipt(
            verified=verified,
            status_code=status_code,
            theorem_name=theorem_name,
            expected_statement_signature=expected_sig,
            actual_statement_signature=actual_sig,
            declared_imports=imports,
            toolchain_version=toolchain,
            source_digest_caid=source_caid,
            signature_hex=sig_hex,
            receipt_caid=receipt_caid,
        )


@dataclass(frozen=True)
class EvidenceClaimSubmission:
    submission_id: str
    claim_category: str  # "FORMAL_THEOREM" | "CODE_CHANGE" | "ACTION_EXECUTION"
    claimed_theorem_name: str = ""
    expected_statement_signature: str = ""
    lean_source_code: Optional[str] = None
    lakefile_content: str = ""
    mutation_report: Optional[MutationAdequacyReport] = None
    required_dependencies: Tuple[str, ...] = ()
    execution_receipt_caid: Optional[str] = None
    timeout_occurred: bool = False
    reconciliation_receipt_caid: Optional[str] = None


@dataclass(frozen=True)
class EvidenceSufficiencyVerdict:
    submission_id: str
    authorized: bool
    verdict_code: str
    verified_dependency_ratio_bps: int
    verdict_caid: str


class EvidenceSufficiencyGate:
    """
    AEIB Benchmark v0.2 Track 6: Evidence Sufficiency Gate.
    Replaces naive 50% ratio thresholds (`HiggsEvidenceCoupling`) and simulated formal gates
    with 100% (`10000 bps`) causal receipt enforcement and explicit unevaluated classification.
    """

    def __init__(
        self,
        formal_gate: NarrowFormalTheoremGate,
        verified_provenance_receipts: Mapping[str, str],
    ) -> None:
        self.formal_gate = formal_gate
        self.provenance_receipts: Dict[str, str] = dict(verified_provenance_receipts)

    def evaluate_submission(
        self, submission: EvidenceClaimSubmission
    ) -> EvidenceSufficiencyVerdict:
        # Case 6: Transport timeout without reconciliation receipt -> indeterminate state
        if submission.timeout_occurred:
            rec_caid = submission.reconciliation_receipt_caid or ""
            if not rec_caid.startswith("sha256:"):
                return self._mint(
                    submission.submission_id,
                    authorized=False,
                    verdict_code="EFFECT_INDETERMINATE_RECONCILIATION_REQUIRED",
                    ratio_bps=0,
                )

        if submission.claim_category == "FORMAL_THEOREM":
            proof_receipt = self.formal_gate.evaluate_formal_artifact(
                claimed_theorem_name=submission.claimed_theorem_name,
                expected_statement_signature=submission.expected_statement_signature,
                lean_source_code=submission.lean_source_code,
                lakefile_content=submission.lakefile_content,
            )
            if proof_receipt.status_code.startswith("HALT_AXIOM_SCOPE_UNDECLARED"):
                return self._mint(
                    submission.submission_id,
                    authorized=False,
                    verdict_code="HALT_AXIOM_SCOPE_UNDECLARED",
                    ratio_bps=0,
                )
            if proof_receipt.status_code.startswith("HALT_CLAIM_SCOPE_MISMATCH"):
                return self._mint(
                    submission.submission_id,
                    authorized=False,
                    verdict_code="HALT_CLAIM_SCOPE_MISMATCH",
                    ratio_bps=0,
                )
            if not proof_receipt.verified:
                return self._mint(
                    submission.submission_id,
                    authorized=False,
                    verdict_code=proof_receipt.status_code,
                    ratio_bps=0,
                )
            return self._mint(
                submission.submission_id,
                authorized=True,
                verdict_code="KERNEL_ACCEPTED",
                ratio_bps=REQUIRED_EVIDENCE_COUPLING_BPS,
            )

        if submission.claim_category == "CODE_CHANGE":
            rep = submission.mutation_report
            if rep is None or rep.verdict != "ALLOW_MERGE":
                return self._mint(
                    submission.submission_id,
                    authorized=False,
                    verdict_code="BLOCK_MERGE_TEST_ADEQUACY_FAILURE",
                    ratio_bps=rep.mutation_score_bps if rep is not None else 0,
                )
            return self._mint(
                submission.submission_id,
                authorized=True,
                verdict_code="ALLOW_MERGE_ADEQUACY_VERIFIED",
                ratio_bps=rep.mutation_score_bps,
            )

        if submission.claim_category == "ACTION_EXECUTION":
            deps = submission.required_dependencies
            if not deps:
                return self._mint(
                    submission.submission_id,
                    authorized=False,
                    verdict_code="HALT_EPISTEMIC_DRIFT",
                    ratio_bps=0,
                )
            verified_count = 0
            for dep_id in deps:
                caid = self.provenance_receipts.get(dep_id, "")
                if caid.startswith("sha256:"):
                    verified_count += 1
            ratio_bps = (verified_count * 10000) // len(deps)
            exec_rcpt = submission.execution_receipt_caid or ""
            # Requires 100% (10000 bps) of causal dependencies AND a valid execution receipt
            if ratio_bps < REQUIRED_EVIDENCE_COUPLING_BPS or not exec_rcpt.startswith("sha256:"):
                return self._mint(
                    submission.submission_id,
                    authorized=False,
                    verdict_code="HALT_EPISTEMIC_DRIFT",
                    ratio_bps=ratio_bps,
                )
            return self._mint(
                submission.submission_id,
                authorized=True,
                verdict_code="ALLOW_CAUSAL_CLOSURE_VERIFIED",
                ratio_bps=ratio_bps,
            )

        raise ValueError(f"ERR_UNKNOWN_CLAIM_CATEGORY:{submission.claim_category}")

    @staticmethod
    def _mint(
        submission_id: str,
        authorized: bool,
        verdict_code: str,
        ratio_bps: int,
    ) -> EvidenceSufficiencyVerdict:
        payload = {
            "authorized": authorized,
            "submission_id": submission_id,
            "verdict_code": verdict_code,
            "verified_dependency_ratio_bps": ratio_bps,
        }
        return EvidenceSufficiencyVerdict(
            submission_id=submission_id,
            authorized=authorized,
            verdict_code=verdict_code,
            verified_dependency_ratio_bps=ratio_bps,
            verdict_caid=sha256_caid(payload),
        )
