#!/usr/bin/env python3
"""
src/parallel_tracks_abcde_engine.py — Parallel Tracks A–E Verification Engine

Evaluated under the stated model (prototype):
- Single-source RFC 8785 JCS delegation via `src.jcs_canonicalizer.encode_jcs`
  with strict rejection of float values and non-string dictionary keys.
- Track A: Offline structural and temporal gate (`BioDigitalNineSourceGate`)
  over pre-fetched `NineSourceOmicsRecord` structures and pre-registered
  hypotheses (`PreRegisteredHypothesis`). Does not query external databases
  over the network.
- Track B: 8-hook `OspreyPreToolUseHookChain` and `RealZeroMockSlopAndCVEFilter`
  static AST policy.
- Track C: Finite-state BFS model (`ExhaustiveF9StateSpaceProver`) over
  `ProtocolModelState` (companion to `tests/test_eo1_protocol_model_checker.py`).
- Track D: Integer Hawkes-process `HawkesContextRAMManager` with pinned `[C]`
  constraint blocks.
- Track E: In-memory `ReproducibleEvidenceBundleBuilder` using `fileobj=buf`
  in `gzip.GzipFile` and `verify_and_extract_bundle` digest verification.
"""

from __future__ import annotations

import ast
import collections
import gzip
import hashlib
import hmac
import io
import json
import tarfile
from dataclasses import dataclass
from typing import Any, Deque, Dict, FrozenSet, List, Optional, Tuple

from src.jcs_canonicalizer import encode_jcs


def _validate_no_float_or_non_str_keys(node: Any) -> None:
    """Reject floats and non-string mapping keys before RFC 8785 serialization."""
    if isinstance(node, float):
        raise ValueError("ERR_FLOAT_FORBIDDEN_IN_CANONICAL_JSON_V1")
    if isinstance(node, dict):
        for k, v in node.items():
            if not isinstance(k, str):
                raise ValueError("ERR_NON_STRING_KEY")
            _validate_no_float_or_non_str_keys(v)
    elif isinstance(node, (list, tuple)):
        for item in node:
            _validate_no_float_or_non_str_keys(item)


def _canonical_json_bytes(obj: Any) -> bytes:
    """
    Validate that no float values or non-string dict keys exist in `obj`,
    then delegate canonical serialization to `src.jcs_canonicalizer.encode_jcs`.
    """
    _validate_no_float_or_non_str_keys(obj)
    return encode_jcs(obj)


canonical_json_v1 = _canonical_json_bytes


def sha256_caid(payload: Any) -> str:
    """Compute content-addressed identifier (`sha256:<hex>`) over bytes, str, or JCS object."""
    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = _canonical_json_bytes(payload)
    return "sha256:" + hashlib.sha256(raw).hexdigest()


# ============================================================================
# TRACK A: 9-Database Bio-Digital Evidence Gate & Anti-HARKing Lock
# ============================================================================


@dataclass(frozen=True)
class PreRegisteredHypothesis:
    hypothesis_id: str
    rs_id: str
    grch38_chrom: str
    grch38_pos: int
    ref_allele: str
    alt_allele: str
    ensembl_gene_id: str
    expected_direction: str  # "LOSS_OF_FUNCTION" | "REGULATORY_GAIN" | "BENIGN"
    pre_registered_epoch_sec: int
    hypothesis_caid: str


@dataclass(frozen=True)
class NineSourceOmicsRecord:
    rs_id: str
    grch38_chrom: str
    grch38_pos: int
    ref_allele: str
    alt_allele: str
    dbsnp_build_id: int              # e.g., 157
    ensembl_gene_id: str             # e.g., "ENSG00000130203"
    uniprot_accession: str           # e.g., "P02649"
    alphagenome_avi_phred_bps: int   # 0..10000 bps (e.g., 9150 = 91.50%)
    encode4_ccre_id: str             # e.g., "EH38E2941922" or "NONE"
    jaspar_tfbs_motif_id: str        # e.g., "MA0139.1" or "NONE"
    ucsc_phylop_milli: int           # PhyloP * 1000 (e.g., 4200 = 4.200)
    reactome_pathway_id: str         # e.g., "R-HSA-174824"
    alphafold_plddt_bps: int         # 0..10000 bps (e.g., 9250 = 92.50 pLDDT)
    evidence_timestamp_sec: int


@dataclass(frozen=True)
class BioGateVerdict:
    verdict: str  # "SUPPORTS" | "REFUTES" | "UNKNOWN" | "HALT_*"
    reason_code: str
    lookup_caid: str
    content_caid: str


class BioDigitalNineSourceGate:
    """
    Track A: Offline structural and temporal gate over pre-fetched
    `NineSourceOmicsRecord` records and pre-registered hypotheses.

    Note: This class operates strictly on in-memory records supplied by the caller
    and does not query external databases (AlphaGenome, dbSNP, ENCODE4, JASPAR,
    Reactome, UCSC, Ensembl, UniProt, or AlphaFold) over the network.
    """

    VALID_BASES: FrozenSet[str] = frozenset({"A", "C", "G", "T"})

    @classmethod
    def register_hypothesis(
        cls,
        hypothesis_id: str,
        rs_id: str,
        grch38_chrom: str,
        grch38_pos: int,
        ref_allele: str,
        alt_allele: str,
        ensembl_gene_id: str,
        expected_direction: str,
        pre_registered_epoch_sec: int,
    ) -> PreRegisteredHypothesis:
        if (
            isinstance(grch38_pos, bool)
            or isinstance(pre_registered_epoch_sec, bool)
            or grch38_pos < 0
            or pre_registered_epoch_sec < 0
        ):
            raise ValueError("ERR_INVALID_HYPOTHESIS_BOUNDS")
        payload = {
            "alt_allele": alt_allele,
            "ensembl_gene_id": ensembl_gene_id,
            "expected_direction": expected_direction,
            "grch38_chrom": grch38_chrom,
            "grch38_pos": grch38_pos,
            "hypothesis_id": hypothesis_id,
            "pre_registered_epoch_sec": pre_registered_epoch_sec,
            "ref_allele": ref_allele,
            "rs_id": rs_id,
        }
        return PreRegisteredHypothesis(
            hypothesis_id=hypothesis_id,
            rs_id=rs_id,
            grch38_chrom=grch38_chrom,
            grch38_pos=grch38_pos,
            ref_allele=ref_allele,
            alt_allele=alt_allele,
            ensembl_gene_id=ensembl_gene_id,
            expected_direction=expected_direction,
            pre_registered_epoch_sec=pre_registered_epoch_sec,
            hypothesis_caid=sha256_caid(payload),
        )

    @classmethod
    def evaluate(
        cls,
        hypothesis: PreRegisteredHypothesis,
        record: NineSourceOmicsRecord,
    ) -> BioGateVerdict:
        lookup_caid = sha256_caid(
            {
                "chrom": record.grch38_chrom,
                "gene": record.ensembl_gene_id,
                "hypothesis_caid": hypothesis.hypothesis_caid,
                "pos": record.grch38_pos,
                "rs_id": record.rs_id,
            }
        )
        content_caid = sha256_caid(record.__dict__)

        int_fields = (
            record.grch38_pos,
            record.dbsnp_build_id,
            record.alphagenome_avi_phred_bps,
            record.ucsc_phylop_milli,
            record.alphafold_plddt_bps,
            record.evidence_timestamp_sec,
            hypothesis.grch38_pos,
            hypothesis.pre_registered_epoch_sec,
        )
        if (
            any(isinstance(v, bool) or not isinstance(v, int) for v in int_fields)
            or record.dbsnp_build_id <= 0
            or record.alphagenome_avi_phred_bps < 0
            or record.alphagenome_avi_phred_bps > 10000
            or record.alphafold_plddt_bps < 0
            or record.alphafold_plddt_bps > 10000
            or record.evidence_timestamp_sec < 0
        ):
            return BioGateVerdict(
                "HALT_INVALID_OMICS_METRIC_BOUNDS",
                "Integer field is boolean or metric is outside valid bounds",
                lookup_caid,
                content_caid,
            )

        # Vector 1: Anti-HARKing Temporal Lock (hypothesis must precede evidence fetch)
        if hypothesis.pre_registered_epoch_sec > record.evidence_timestamp_sec:
            return BioGateVerdict(
                "HALT_POST_HOC_HARKING_DETECTED",
                "Hypothesis timestamp is newer than evidence fetch timestamp",
                lookup_caid,
                content_caid,
            )

        # Vector 2: Coordinate & Variant Identity Parity
        if (
            record.rs_id != hypothesis.rs_id
            or record.grch38_chrom != hypothesis.grch38_chrom
            or record.grch38_pos != hypothesis.grch38_pos
            or record.ensembl_gene_id != hypothesis.ensembl_gene_id
        ):
            return BioGateVerdict(
                "HALT_VARIANT_COORDINATE_MISMATCH",
                "Record coordinates do not match pre-registered hypothesis",
                lookup_caid,
                content_caid,
            )

        # Vector 3: Allele & dbSNP Format Validation
        if (
            not record.rs_id.startswith("rs")
            or not record.rs_id[2:].isdigit()
            or record.grch38_pos <= 0
            or record.ref_allele not in cls.VALID_BASES
            or record.alt_allele not in cls.VALID_BASES
            or record.ref_allele == record.alt_allele
        ):
            return BioGateVerdict(
                "HALT_INVALID_ALLELE_OR_RSID",
                "Malformed rsID, non-positive position, or identical ref/alt allele",
                lookup_caid,
                content_caid,
            )

        # Vector 4: Accession Provenance (Ensembl, UniProt, Reactome)
        if (
            not record.ensembl_gene_id.startswith("ENSG")
            or not record.uniprot_accession
            or not record.reactome_pathway_id.startswith("R-HSA-")
        ):
            return BioGateVerdict(
                "HALT_MISSING_OMICS_ACCESSION",
                "Ensembl, UniProt, or Reactome accession invalid",
                lookup_caid,
                content_caid,
            )

        # Vector 5: AlphaFold Structural Confidence Floor (pLDDT >= 7000 bps)
        if record.alphafold_plddt_bps < 7000:
            return BioGateVerdict(
                "UNKNOWN",
                "INCONCLUSIVE_LOW_ALPHAFOLD_PLDDT",
                lookup_caid,
                content_caid,
            )

        # Vector 6: Concordant Multi-Omics Scoring (`SUPPORTS | REFUTES | UNKNOWN`)
        has_ccre = record.encode4_ccre_id.startswith("EH38E")
        has_tfbs = record.jaspar_tfbs_motif_id.startswith("MA")
        conserved = record.ucsc_phylop_milli >= 2000
        high_avi = record.alphagenome_avi_phred_bps >= 8000

        if high_avi and has_ccre and has_tfbs and conserved:
            return BioGateVerdict(
                "SUPPORTS",
                "OK_CONCORDANT_9_SOURCE_PATHOGENIC_SUPPORT",
                lookup_caid,
                content_caid,
            )

        if record.alphagenome_avi_phred_bps <= 2000 and record.ucsc_phylop_milli <= 0:
            return BioGateVerdict(
                "REFUTES",
                "OK_CONCORDANT_BENIGN_REFUTATION",
                lookup_caid,
                content_caid,
            )

        return BioGateVerdict(
            "UNKNOWN",
            "INCONCLUSIVE_DISCORDANT_OMICS_EVIDENCE",
            lookup_caid,
            content_caid,
        )


# ============================================================================
# TRACK B: Osprey 8-Hook `PreToolUse` Chain, Structural CVE Filter, & Cache Policy
# ============================================================================


@dataclass(frozen=True)
class ExactActionProposal:
    tool_name: str
    arguments: Dict[str, Any]
    risk_tier: str                 # "T0" | "T1" | "T2" | "T3"
    tenant_id: str
    data_jurisdiction: str         # "EU" | "US"
    target_model_jurisdiction: str  # "EU" | "US" | "RESTRICTED_EXPORT"
    amount_minor: int
    idempotency_key: str
    model_manifest_digest: str
    operator_signed_action_caid: Optional[str] = None
    co_tenant_count_on_host: int = 0

    def action_caid(self) -> str:
        return sha256_caid(
            {
                "amount_minor": self.amount_minor,
                "arguments": self.arguments,
                "idempotency_key": self.idempotency_key,
                "model_manifest_digest": self.model_manifest_digest,
                "risk_tier": self.risk_tier,
                "tenant_id": self.tenant_id,
                "tool_name": self.tool_name,
            }
        )


@dataclass(frozen=True)
class PreToolHookVerdict:
    allowed: bool
    failed_hook: str
    reason_code: str
    action_caid: str


class OspreyPreToolUseHookChain:
    """
    Implements the 8-Hook `PreToolUse` Chain:
      1. `HOOK_1_KILL_SWITCH`
      2. `HOOK_2_LIMITS`
      3. `HOOK_3_JURISDICTION`
      4. `HOOK_4_TOOL_MANIFEST`
      5. `HOOK_5_MODEL_MANIFEST`
      6. `HOOK_6_CACHE_ISOLATION`: Checks scheduler host-dedication metadata
         (`co_tenant_count_on_host == 0`) for T3 actions, because OS core pinning
         (`taskset -c`) on a shared socket does NOT isolate the shared L3 cache.
      7. `HOOK_7_IDEMPOTENCY`
      8. `HOOK_8_EXACT_APPROVAL`
    """

    def __init__(
        self,
        frozen_tenants: FrozenSet[str],
        max_per_call_minor: int,
        allowed_tools: FrozenSet[str],
        live_model_manifest_digest: str,
    ) -> None:
        self.frozen_tenants = frozen_tenants
        self.max_per_call_minor = max_per_call_minor
        self.allowed_tools = allowed_tools
        self.live_model_manifest_digest = live_model_manifest_digest
        self._committed_idempotency_keys: set[str] = set()

    def evaluate(self, call: ExactActionProposal) -> PreToolHookVerdict:
        caid = call.action_caid()

        # Hook 1: Tenant Kill-Switch
        if call.tenant_id in self.frozen_tenants:
            return PreToolHookVerdict(
                False, "HOOK_1_KILL_SWITCH", "HALT_TENANT_KILL_SWITCH_ACTIVE", caid
            )

        # Hook 2: Budget & Setpoint Limits
        if (
            isinstance(call.amount_minor, bool)
            or call.amount_minor < 0
            or call.amount_minor > self.max_per_call_minor
        ):
            return PreToolHookVerdict(
                False, "HOOK_2_LIMITS", "HALT_AMOUNT_EXCEEDS_PER_CALL_LIMIT", caid
            )

        # Hook 3: Sovereign Data Jurisdiction
        if call.target_model_jurisdiction == "RESTRICTED_EXPORT":
            return PreToolHookVerdict(
                False, "HOOK_3_JURISDICTION", "HALT_GEOPOLITICAL_EXPORT_VIOLATION", caid
            )
        if call.data_jurisdiction == "EU" and call.target_model_jurisdiction != "EU":
            return PreToolHookVerdict(
                False, "HOOK_3_JURISDICTION", "HALT_EU_DATA_RESIDENCY_VIOLATION", caid
            )

        # Hook 4: Dynamic Tool Registry Allowlist
        if call.tool_name not in self.allowed_tools:
            return PreToolHookVerdict(
                False, "HOOK_4_TOOL_MANIFEST", f"HALT_UNREGISTERED_TOOL:{call.tool_name}", caid
            )

        # Hook 5: Model Manifest Provenance
        if call.model_manifest_digest != self.live_model_manifest_digest:
            return PreToolHookVerdict(
                False, "HOOK_5_MODEL_MANIFEST", "HALT_MODEL_MANIFEST_EXPIRED", caid
            )

        # Hook 6: Host Dedication Metadata Check (core pinning on a shared socket does not isolate L3 cache)
        if call.risk_tier == "T3" and (
            isinstance(call.co_tenant_count_on_host, bool)
            or call.co_tenant_count_on_host != 0
        ):
            return PreToolHookVerdict(
                False,
                "HOOK_6_CACHE_ISOLATION",
                "HALT_T3_SHARED_L3_CACHE_CO_TENANT_FORBIDDEN",
                caid,
            )

        # Hook 7: Idempotency & Replay Guard
        if not call.idempotency_key or call.idempotency_key in self._committed_idempotency_keys:
            return PreToolHookVerdict(
                False, "HOOK_7_IDEMPOTENCY", "HALT_DUPLICATE_OR_MISSING_IDEMPOTENCY_KEY", caid
            )

        # Hook 8: Exact-Action Human Approval for T3
        if call.risk_tier == "T3":
            if not hmac.compare_digest(call.operator_signed_action_caid or "", caid):
                return PreToolHookVerdict(
                    False,
                    "HOOK_8_EXACT_APPROVAL",
                    "HALT_T3_EXACT_ACTION_DIGEST_UNAPPROVED",
                    caid,
                )

        self._committed_idempotency_keys.add(call.idempotency_key)
        return PreToolHookVerdict(True, "NONE", "OK_ALL_8_PRE_TOOL_HOOKS_PASSED", caid)


class RealZeroMockSlopAndCVEFilter:
    """
    Track B: Static AST and SBOM policy filter.
    1. Note on CVE-2026-33017: CVE-2026-33017 is an unauthenticated RCE in Langflow <1.9.0
       via `POST /api/v1/build_public_tmp/{flow_id}/flow` reaching `exec()` on attacker-supplied
       component code. Forbidding `ast.Call` inside module-level `ast.Assign`, `ast.AnnAssign`,
       or `ast.Expr` is a static AST policy against top-level call execution during module load.
    2. Blocks template/dunder injection tokens (`__globals__`, `__subclasses__`, `__builtins__`,
       `{{config`, `{% import`).
    3. Checks every top-level package imported via `ast.Import` or non-relative `ast.ImportFrom`
       (`node.level == 0`) against `self.pinned_sbom_packages`.
    """

    DANGEROUS_TEMPLATE_TOKENS: Tuple[str, ...] = (
        "__globals__",
        "__subclasses__",
        "__builtins__",
        "{{config",
        "{% import",
    )

    def __init__(self, pinned_sbom_packages: FrozenSet[str]) -> None:
        self.pinned_sbom_packages = pinned_sbom_packages

    def inspect_code_and_templates(
        self, python_source: str, template_payload: str = ""
    ) -> Tuple[bool, str]:
        for tok in self.DANGEROUS_TEMPLATE_TOKENS:
            if tok in template_payload or tok in python_source:
                return False, f"HALT_TEMPLATE_OR_DUNDER_INJECTION:{tok}"

        try:
            tree = ast.parse(python_source)
        except SyntaxError as exc:
            return False, f"HALT_AST_SYNTAX_ERROR:{exc.msg}"

        for stmt in tree.body:
            if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.Expr)):
                for sub in ast.walk(stmt):
                    if isinstance(sub, ast.Call):
                        return (
                            False,
                            "HALT_CVE_2026_33017_TOP_LEVEL_CALL_IN_ASSIGN_OR_EXPR",
                        )

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_pkg = alias.name.split(".")[0]
                    if root_pkg not in self.pinned_sbom_packages:
                        return False, f"HALT_UNPINNED_SBOM_IMPORT:{root_pkg}"
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                root_pkg = node.module.split(".")[0]
                if root_pkg not in self.pinned_sbom_packages:
                    return False, f"HALT_UNPINNED_SBOM_IMPORT:{root_pkg}"

        return True, "OK_AST_AND_SBOM_CLEAN"


# ============================================================================
# TRACK C: Exhaustive BFS State-Space Model-Code Conformance Prover
# ============================================================================


@dataclass(frozen=True)
class ProtocolModelState:
    client_state: str          # "IDLE" | "IN_FLIGHT" | "INDETERMINATE" | "FENCED_READY" | "DONE"
    attempt_seq: int           # 0, 1, 2
    min_accepted_seq: int      # Target fence register (1 or 2)
    stalled_attempt_1: bool    # Whether Attempt 1 is still in flight in slow queue
    committed_count: int       # Number of times mutation committed on target
    escrow_locked: int         # 0 or 1000 minor units


@dataclass(frozen=True)
class BFSModelCheckReport:
    explored_states: int
    max_committed_count_observed: int
    budget_conservation_holds: bool
    at_most_once_holds: bool


class ExhaustiveF9StateSpaceProver:
    """
    Track C: Finite-state Breadth-First Search (BFS) model over `ProtocolModelState`
    (companion to `tests/test_eo1_protocol_model_checker.py`).
    Evaluates across reachable states of the finite model:
    1. `committed_count <= 1` when target fencing is enabled (`at_most_once_holds`).
    2. `escrow_locked == 1000` whenever `committed_count > 0` (`budget_conservation_holds`).
    """

    @staticmethod
    def prove_fenced_protocol_invariants(enable_target_fencing: bool = True) -> BFSModelCheckReport:
        initial = ProtocolModelState(
            client_state="IDLE",
            attempt_seq=0,
            min_accepted_seq=1,
            stalled_attempt_1=False,
            committed_count=0,
            escrow_locked=0,
        )
        visited: set[ProtocolModelState] = {initial}
        queue: Deque[ProtocolModelState] = collections.deque([initial])

        max_commits = 0
        budget_ok = True
        at_most_once_ok = True

        while queue:
            s = queue.popleft()
            max_commits = max(max_commits, s.committed_count)
            if s.committed_count > 1:
                at_most_once_ok = False
            if (s.committed_count > 0 or s.client_state != "IDLE") and s.escrow_locked != 1000:
                budget_ok = False
            if s.client_state == "DONE" and s.committed_count < 1:
                budget_ok = False
            if s.committed_count > 2:
                break

            next_states: List[ProtocolModelState] = []

            # Transition 1: IDLE -> reserve escrow & send Attempt 1
            if s.client_state == "IDLE":
                next_states.append(
                    ProtocolModelState(
                        client_state="IN_FLIGHT",
                        attempt_seq=1,
                        min_accepted_seq=s.min_accepted_seq,
                        stalled_attempt_1=False,
                        committed_count=s.committed_count,
                        escrow_locked=1000,
                    )
                )

            # Transition 2a & 2b: IN_FLIGHT (attempt 1) commits normally or stalls on timeout
            if s.client_state == "IN_FLIGHT":
                next_states.append(
                    ProtocolModelState(
                        client_state="DONE",
                        attempt_seq=1,
                        min_accepted_seq=s.min_accepted_seq,
                        stalled_attempt_1=False,
                        committed_count=s.committed_count + 1,
                        escrow_locked=s.escrow_locked,
                    )
                )
                next_states.append(
                    ProtocolModelState(
                        client_state="INDETERMINATE",
                        attempt_seq=1,
                        min_accepted_seq=s.min_accepted_seq,
                        stalled_attempt_1=True,
                        committed_count=s.committed_count,
                        escrow_locked=s.escrow_locked,
                    )
                )

            # Transition 3: Stalled Attempt 1 wakes up and tries to commit
            if s.stalled_attempt_1:
                late_delta = 1 if 1 >= s.min_accepted_seq else 0
                next_states.append(
                    ProtocolModelState(
                        client_state=s.client_state,
                        attempt_seq=s.attempt_seq,
                        min_accepted_seq=s.min_accepted_seq,
                        stalled_attempt_1=False,
                        committed_count=s.committed_count + late_delta,
                        escrow_locked=s.escrow_locked,
                    )
                )

            # Transition 4: INDETERMINATE -> Read-back probe & retry decision
            if s.client_state == "INDETERMINATE" and s.committed_count == 0:
                fenced_seq = 2 if enable_target_fencing else 1
                next_states.append(
                    ProtocolModelState(
                        client_state="FENCED_READY",
                        attempt_seq=1,
                        min_accepted_seq=fenced_seq,
                        stalled_attempt_1=s.stalled_attempt_1,
                        committed_count=s.committed_count,
                        escrow_locked=s.escrow_locked,
                    )
                )

            # Transition 5: FENCED_READY -> Dispatch Attempt 2 (`seq = 2`)
            if s.client_state == "FENCED_READY":
                next_states.append(
                    ProtocolModelState(
                        client_state="DONE",
                        attempt_seq=2,
                        min_accepted_seq=s.min_accepted_seq,
                        stalled_attempt_1=s.stalled_attempt_1,
                        committed_count=s.committed_count + 1,
                        escrow_locked=s.escrow_locked,
                    )
                )

            for ns in next_states:
                if ns not in visited:
                    visited.add(ns)
                    queue.append(ns)

        return BFSModelCheckReport(
            explored_states=len(visited),
            max_committed_count_observed=max_commits,
            budget_conservation_holds=budget_ok,
            at_most_once_holds=at_most_once_ok,
        )


# ============================================================================
# TRACK D: Integer Hawkes-Process Context-as-RAM Manager (<= 1500 Tokens)
# ============================================================================


@dataclass(frozen=True)
class ContextRAMBlock:
    block_id: str
    tier: str                # "[C]" | "[P]" | "[B]" | "[F]" | "[E]"
    token_count: int
    base_salience_bps: int   # 0..10000
    last_event_turn: int
    excitation_count: int
    content: str


class HawkesContextRAMManager:
    """
    Track D: Treats active LLM context strictly as bounded working RAM (default <= 1500 tokens).
    - `[C]` (Constraints) blocks are pinned at `100_000` (never evicted).
    - `[E]` / `[F]` / `[B]` / `[P]` blocks decay with integer Hawkes intensity:
      `intensity_bps = base_salience_bps + excitation_count * alpha_bps - age_turns * decay_bps_per_turn`.
    """

    def __init__(
        self,
        ram_token_ceiling: int = 1500,
        alpha_bps: int = 1200,
        decay_bps_per_turn: int = 800,
    ) -> None:
        if isinstance(ram_token_ceiling, bool) or ram_token_ceiling <= 0:
            raise ValueError("ERR_INVALID_RAM_TOKEN_CEILING")
        self.ram_token_ceiling = ram_token_ceiling
        self.alpha_bps = alpha_bps
        self.decay_bps_per_turn = decay_bps_per_turn
        self._blocks: Dict[str, ContextRAMBlock] = {}

    def compute_hawkes_intensity_bps(self, block: ContextRAMBlock, current_turn: int) -> int:
        if block.tier == "[C]":
            return 100_000
        age = max(0, current_turn - block.last_event_turn)
        raw = (
            block.base_salience_bps
            + (block.excitation_count * self.alpha_bps)
            - (age * self.decay_bps_per_turn)
        )
        return max(0, raw)

    def upsert_and_compact(
        self, new_block: ContextRAMBlock, current_turn: int
    ) -> Tuple[Tuple[str, ...], int]:
        if isinstance(new_block.token_count, bool) or new_block.token_count <= 0:
            raise ValueError("ERR_INVALID_BLOCK_TOKEN_COUNT")

        self._blocks[new_block.block_id] = new_block

        c_tokens = sum(b.token_count for b in self._blocks.values() if b.tier == "[C]")
        if c_tokens > self.ram_token_ceiling:
            raise RuntimeError("HALT_CONSTRAINT_TIER_EXCEEDS_RAM_CEILING")

        ranked = sorted(
            self._blocks.values(),
            key=lambda b: (
                1 if b.tier == "[C]" else 0,
                self.compute_hawkes_intensity_bps(b, current_turn),
                b.block_id,
            ),
            reverse=True,
        )

        retained: Dict[str, ContextRAMBlock] = {}
        used_tokens = 0
        for blk in ranked:
            if blk.tier == "[C]" or (used_tokens + blk.token_count <= self.ram_token_ceiling):
                retained[blk.block_id] = blk
                used_tokens += blk.token_count

        self._blocks = retained
        return tuple(sorted(self._blocks.keys())), used_tokens


# ============================================================================
# TRACK E: Deterministic Bit-Identical Evidence Archive Builder (`SOURCE_DATE_EPOCH`)
# ============================================================================


class ReproducibleEvidenceBundleBuilder:
    """
    Track E: Produces a deterministic, bit-identical `.tar.gz` evidence bundle in memory
    using a pinned `FIXED_EPOCH`, sorted filenames, zeroed uid/gid, and canonical JSON
    manifests via `fileobj=buf` in `gzip.GzipFile`.
    """

    FIXED_EPOCH = 1761523200  # 2025-10-27T00:00:00Z deterministic timestamp

    @classmethod
    def build_deterministic_bundle_bytes(
        cls, artifacts: Dict[str, Dict[str, Any]]
    ) -> Tuple[bytes, str]:
        if not artifacts:
            raise ValueError("HALT_EMPTY_EVIDENCE_BUNDLE")
        buf = io.BytesIO()
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=buf,
            compresslevel=9,
            mtime=cls.FIXED_EPOCH,
        ) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for rel_path in sorted(artifacts.keys()):
                    payload_bytes = _canonical_json_bytes(artifacts[rel_path])
                    info = tarfile.TarInfo(name=rel_path)
                    info.size = len(payload_bytes)
                    info.mtime = cls.FIXED_EPOCH
                    info.mode = 0o644
                    info.uid = 0
                    info.gid = 0
                    info.uname = "root"
                    info.gname = "root"
                    tar.addfile(info, io.BytesIO(payload_bytes))
        archive_bytes = buf.getvalue()
        return archive_bytes, sha256_caid(archive_bytes)

    @classmethod
    def verify_and_extract_bundle(
        cls, archive_bytes: bytes, expected_caid: str
    ) -> Dict[str, Dict[str, Any]]:
        if not archive_bytes:
            raise ValueError("HALT_EMPTY_ARCHIVE_BYTES")
        actual_caid = sha256_caid(archive_bytes)
        if not hmac.compare_digest(actual_caid, expected_caid):
            raise ValueError("HALT_EVIDENCE_BUNDLE_CAID_MISMATCH")
        extracted: Dict[str, Dict[str, Any]] = {}
        with gzip.GzipFile(fileobj=io.BytesIO(archive_bytes), mode="rb") as gz:
            with tarfile.open(fileobj=gz, mode="r:*") as tar:
                for member in tar.getmembers():
                    reader = tar.extractfile(member)
                    assert reader is not None
                    extracted[member.name] = json.loads(reader.read().decode("utf-8"))
        return extracted
