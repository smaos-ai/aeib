"""
DIR (Detect, Isolate, Replace) Anti-Scaffold & Out-of-Scope Track Bisector,
Fail-Closed Grounded Health Monitor, Hardened x402 Escrow Interceptor, and
Live Hardware & SQLite Experiment Runner.

Remediates the four defects falsified in pasted prototype drafts:
1. Multi-statement / docstring-padded trivial verifiers and cold-host silent
   fallbacks (DirAntiScaffoldAndScopeBisector).
2. Fail-open vacuous truth (`return 1.0` on empty context or blank output) and
   float crash in JCS serialization in the pasted ModelHealthMonitor
   (FailClosedGroundedHealthMonitor).
3. Non-existent `EO1WriteBeforeExecuteLatch` import and missing epoch wallet-drain
   (smurfing) + challenge nonce replay defense in the pasted x402 interceptor
   (HardenedX402EscrowInterceptor wired to the real PreDispatchIntentInterlock).
4. Live hardware F_FULLFSYNC / os.fsync and SQLite FTS5 bm25 empirical experiment
   execution with zero hardcoded benchmark literals (LiveHardwareAndSqliteExperimentRunner).
"""

from __future__ import annotations

import ast
import base64
import hashlib
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.eo1_write_before_execute import (
    IntentLifecycleState,
    PreDispatchIntentInterlock,
    compute_caid,
)
from src.hypersu_fts import HyperSUFTSRetriever
from src.hypersu_store import FactRecord, HyperSUStore, compute_sha256_hex
from src.jcs_canonicalizer import encode_jcs


def _sha256_jcs(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(encode_jcs(payload)).hexdigest()


# ---------------------------------------------------------------------------
# Part I: DIR (Detect, Isolate, Replace) Anti-Scaffold & Out-of-Scope Router
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScaffoldFinding:
    """Single static or behavioral scaffold finding."""

    module_path: str
    symbol_name: str
    lineno: int
    anomaly_code: str
    details: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anomaly_code": self.anomaly_code,
            "details": self.details,
            "lineno": self.lineno,
            "module_path": self.module_path,
            "symbol_name": self.symbol_name,
        }


@dataclass(frozen=True)
class ParallelOutOfScopeTrackSpec:
    """
    Signed specification contract isolating an out-of-scope or host-unavailable
    subsystem into a dedicated parallel engineering track rather than allowing
    an inline LLM mock or fake fallback.
    """

    track_id: str
    subsystem_key: str
    routing_disposition: str
    existing_verified_provider: str
    required_host_capabilities: Tuple[str, ...]
    cold_host_fallback_error: str
    ffi_boundary_schema: Dict[str, str]
    spec_digest: str
    signature_b64: str

    def statement_dict(self) -> Dict[str, Any]:
        return {
            "cold_host_fallback_error": self.cold_host_fallback_error,
            "existing_verified_provider": self.existing_verified_provider,
            "ffi_boundary_schema": dict(self.ffi_boundary_schema),
            "required_host_capabilities": list(self.required_host_capabilities),
            "routing_disposition": self.routing_disposition,
            "subsystem_key": self.subsystem_key,
            "track_id": self.track_id,
        }


class DirAntiScaffoldAndScopeBisector:
    """
    Implements the 3-Phase DIR (Detect, Isolate, Replace) Protocol:
    1. Detect: AST multi-statement trivial-verifier inspection (ignoring docstrings)
       and behavioral differential probing on corrupted inputs.
    2. Replace: Checks the Verified Ecosystem & Local Primitive Registry so the
       agent reuses battle-tested components instead of reinventing fragile stubs.
    3. Isolate: Carves out genuinely out-of-scope or host-unavailable subsystems
       (e.g., Linux eBPF LSM, hardware TPM 2.0, Lean 4 kernel, robotic liquid
       handlers) into signed ParallelOutOfScopeTrackSpec contracts that fail
       closed with ERR_CAPABILITY_UNAVAILABLE_ON_HOST on cold hosts.
    """

    VERIFIED_PRIMITIVE_REGISTRY: Mapping[str, Dict[str, Any]] = {
        "durable_write_before_execute_latch": {
            "provider": "src.eo1_write_before_execute.PreDispatchIntentInterlock",
            "host_capabilities": ("posix_filesystem", "fcntl_flock", "os_fsync"),
        },
        "provenance_fts5_bm25_hypergraph": {
            "provider": "src.hypersu_store.HyperSUStore",
            "host_capabilities": ("sqlite3_fts5",),
        },
        "ed25519_jcs_cryptographic_signing": {
            "provider": "cryptography.hazmat.primitives.asymmetric.ed25519 + src.jcs_canonicalizer.encode_jcs",
            "host_capabilities": ("openssl_ed25519",),
        },
        "alphafold_mmcif_pae_domain_analyzer": {
            "provider": "alphafold_database_fetch_and_analyze.analyze_structure + src.model_integrity_layer_and_bio_aeib_gate.GenomicScittReceiptEngine",
            "host_capabilities": ("python3_stdlib",),
        },
    }

    OUT_OF_SCOPE_SUBSYSTEM_CATALOG: Mapping[str, Dict[str, Any]] = {
        "linux_ebpf_lsm_kernel_probe": {
            "required_capabilities": ("linux_kernel_6_8_btf", "bpftool", "cap_bpf"),
            "recommended_ecosystem_crate_or_pkg": "aya-rs / libbpf-bootstrap",
            "ffi_schema": {"socket_path": "str", "cgroup_id": "int", "verdict": "str"},
        },
        "hardware_tpm2_pcr_quote_oracle": {
            "required_capabilities": ("dev_tpmrm0", "tpm2_quote_binary"),
            "recommended_ecosystem_crate_or_pkg": "rust-tss-esapi / tpm2-tools",
            "ffi_schema": {"pcr_Slot": "int", "nonce_hex": "str", "quote_der_b64": "str"},
        },
        "lean4_kernel_proof_checker": {
            "required_capabilities": ("lean4_binary", "lake_build_toolchain"),
            "recommended_ecosystem_crate_or_pkg": "leanprover/lean4 + lean4export",
            "ffi_schema": {"theorem_file": "str", "exit_code": "int", "kernel_log": "str"},
        },
        "wetlab_opentrons_microfluidic_driver": {
            "required_capabilities": ("opentrons_ot2_usb_serial", "inline_ph_sensor_bus"),
            "recommended_ecosystem_crate_or_pkg": "opentrons-http-api-client",
            "ffi_schema": {"reactor_id": "str", "valve_state": "str", "temp_c": "float"},
        },
    }

    _VERIFIER_PREFIXES = ("verify", "check", "validate", "attest", "is_valid", "audit")

    @classmethod
    def inspect_source_for_scaffolds(
        cls,
        source_code: str,
        module_path: str = "<memory>",
    ) -> List[ScaffoldFinding]:
        tree = ast.parse(source_code, filename=module_path)
        findings: List[ScaffoldFinding] = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Strip leading docstring expression if present
            exec_body = list(node.body)
            if (
                exec_body
                and isinstance(exec_body[0], ast.Expr)
                and isinstance(exec_body[0].value, ast.Constant)
                and isinstance(exec_body[0].value.value, str)
            ):
                exec_body = exec_body[1:]

            if not exec_body:
                continue

            has_branch_or_raise = any(
                isinstance(sub, (ast.If, ast.Raise, ast.Try, ast.Assert, ast.For, ast.While))
                for stmt in exec_body
                for sub in ast.walk(stmt)
            )
            returns = [
                sub
                for stmt in exec_body
                for sub in ast.walk(stmt)
                if isinstance(sub, ast.Return)
            ]

            fn_lower = node.name.lower()
            is_verifier_named = fn_lower.startswith(cls._VERIFIER_PREFIXES)

            if is_verifier_named and returns and not has_branch_or_raise:
                for ret in returns:
                    val = ret.value
                    if isinstance(val, ast.Constant) and val.value is True:
                        findings.append(
                            ScaffoldFinding(
                                module_path=module_path,
                                symbol_name=node.name,
                                lineno=ret.lineno,
                                anomaly_code="HALT_UNCONDITIONAL_TRUE_VERIFIER_STUB",
                                details=f"Verifier '{node.name}' returns True without conditional or raise.",
                            )
                        )
                    elif isinstance(val, ast.Dict):
                        findings.append(
                            ScaffoldFinding(
                                module_path=module_path,
                                symbol_name=node.name,
                                lineno=ret.lineno,
                                anomaly_code="HALT_UNCONDITIONAL_DICT_VERIFIER_STUB",
                                details=f"Verifier '{node.name}' returns a static dict without conditional or raise.",
                            )
                        )

            # Check return dicts anywhere in the function for simulated-success markers
            for ret in returns:
                val = ret.value
                if isinstance(val, ast.Dict):
                    kv_pairs: Dict[str, Any] = {}
                    for k_node, v_node in zip(val.keys, val.values):
                        if isinstance(k_node, ast.Constant) and isinstance(k_node.value, str):
                            if isinstance(v_node, ast.Constant):
                                kv_pairs[k_node.value.lower()] = v_node.value
                    has_sim_val = any(
                        isinstance(v, str) and "simulated" in v.lower()
                        for v in kv_pairs.values()
                    )
                    has_truthy_ok = any(
                        kv_pairs.get(k) is True
                        for k in ("verified", "valid", "is_valid", "ok", "success")
                    )
                    if has_sim_val and (has_truthy_ok or not has_branch_or_raise):
                        findings.append(
                            ScaffoldFinding(
                                module_path=module_path,
                                symbol_name=node.name,
                                lineno=ret.lineno,
                                anomaly_code="HALT_SIMULATED_SUCCESS_DICT_STUB",
                                details=f"Function '{node.name}' returns a simulated dictionary claiming verification.",
                            )
                        )

        return findings

    @staticmethod
    def probe_callable_for_static_scaffold(
        fn: Callable[[Any], Any],
        valid_input: Any,
        corrupted_input: Any,
    ) -> Dict[str, Any]:
        """
        Executes a behavioral differential falsification probe:
        - Calls `fn(valid_input)` to confirm nominal operation.
        - Calls `fn(corrupted_input)`: a real verifier MUST either raise an
          exception or return False / a dict with a falsy verification flag.
        - If `fn(corrupted_input)` returns True or matches `valid_out`, raises
          ValueError('HALT_STATIC_SCAFFOLD_BEHAVIOR_DETECTED').
        """
        valid_out = fn(valid_input)
        try:
            corrupted_out = fn(corrupted_input)
        except Exception as exc:
            return {
                "probe_status": "REAL_DISCRIMINATING_VERIFIER",
                "valid_output": valid_out,
                "corrupted_exception": type(exc).__name__,
            }

        if corrupted_out is True or corrupted_out == valid_out:
            raise ValueError(
                "HALT_STATIC_SCAFFOLD_BEHAVIOR_DETECTED: callable accepted corrupted input without raising or rejecting"
            )
        if isinstance(corrupted_out, Mapping) and any(
            corrupted_out.get(k) is True for k in ("verified", "valid", "ok", "is_valid")
        ):
            raise ValueError(
                "HALT_STATIC_SCAFFOLD_BEHAVIOR_DETECTED: callable returned truthy verification flag on corrupted input"
            )

        return {
            "probe_status": "REAL_DISCRIMINATING_VERIFIER",
            "valid_output": valid_out,
            "corrupted_output": corrupted_out,
        }

    @classmethod
    def route_subsystem_requirement(
        cls,
        subsystem_key: str,
        available_host_capabilities: Sequence[str],
        signer_private_key: Ed25519PrivateKey,
    ) -> ParallelOutOfScopeTrackSpec:
        host_set = set(available_host_capabilities)

        if subsystem_key in cls.VERIFIED_PRIMITIVE_REGISTRY:
            entry = cls.VERIFIED_PRIMITIVE_REGISTRY[subsystem_key]
            req_caps = tuple(entry["host_capabilities"])
            disposition = "REUSE_EXISTING_VERIFIED_PRIMITIVE"
            provider = str(entry["provider"])
            ffi_schema = {"module_import": provider, "mode": "in_process_verified"}
        elif subsystem_key in cls.OUT_OF_SCOPE_SUBSYSTEM_CATALOG:
            entry = cls.OUT_OF_SCOPE_SUBSYSTEM_CATALOG[subsystem_key]
            req_caps = tuple(entry["required_capabilities"])
            missing = [c for c in req_caps if c not in host_set]
            disposition = (
                "ISOLATE_PARALLEL_OUT_OF_SCOPE_TRACK"
                if missing
                else "EXECUTE_EXTERNAL_BINARY_BRIDGE"
            )
            provider = str(entry["recommended_ecosystem_crate_or_pkg"])
            ffi_schema = dict(entry["ffi_schema"])
        else:
            raise ValueError(f"HALT_UNKNOWN_SUBSYSTEM_REQUIREMENT: {subsystem_key!r}")

        temp = ParallelOutOfScopeTrackSpec(
            track_id=f"track-{subsystem_key}",
            subsystem_key=subsystem_key,
            routing_disposition=disposition,
            existing_verified_provider=provider,
            required_host_capabilities=req_caps,
            cold_host_fallback_error="ERR_CAPABILITY_UNAVAILABLE_ON_HOST",
            ffi_boundary_schema=ffi_schema,
            spec_digest="",
            signature_b64="",
        )
        stmt = temp.statement_dict()
        digest = _sha256_jcs(stmt)
        sig_b64 = base64.b64encode(
            signer_private_key.sign(encode_jcs({**stmt, "spec_digest": digest}))
        ).decode("ascii")
        return ParallelOutOfScopeTrackSpec(
            track_id=temp.track_id,
            subsystem_key=temp.subsystem_key,
            routing_disposition=temp.routing_disposition,
            existing_verified_provider=temp.existing_verified_provider,
            required_host_capabilities=temp.required_host_capabilities,
            cold_host_fallback_error=temp.cold_host_fallback_error,
            ffi_boundary_schema=temp.ffi_boundary_schema,
            spec_digest=digest,
            signature_b64=sig_b64,
        )


# ---------------------------------------------------------------------------
# Part II: Fail-Closed Grounded Health Monitor (Fixes Pasted ModelHealthMonitor)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GroundedStepReceipt:
    """
    Signed per-step grounding & compound-drift receipt using integer basis points
    (0..10000) so RFC 8785 JCS canonicalization never fails on floating-point values.
    """

    step_id: str
    model_id: str
    caid: str
    context_digest: str
    grounding_score_bps: int
    status: str
    signature_b64: str

    def statement_dict(self) -> Dict[str, Any]:
        return {
            "caid": self.caid,
            "context_digest": self.context_digest,
            "grounding_score_bps": self.grounding_score_bps,
            "model_id": self.model_id,
            "status": self.status,
            "step_id": self.step_id,
        }


class FailClosedGroundedHealthMonitor:
    """
    Remediates the two defects in the pasted ModelHealthMonitor prototype:
    1. Empty `context_spans` or blank `generated_output` fails closed with
       `grounding_score_bps = 0` and `status = "HALTED_EMPTY_CONTEXT_OR_OUTPUT"`
       (instead of returning `1.0` / `HEALTHY`).
    2. Serializes integer `grounding_score_bps` (`0..10000`) via RFC 8785 `encode_jcs`
       and signs with Ed25519, triggering `HALTED_COMPOUND_DRIFT` when >= 2 of the
       last 3 steps are degraded.
    """

    def __init__(
        self,
        signer_private_key: Ed25519PrivateKey,
        min_grounding_bps: int = 5000,
    ) -> None:
        if min_grounding_bps <= 0 or min_grounding_bps > 10000:
            raise ValueError("min_grounding_bps must be in 1..10000")
        self._priv = signer_private_key
        self.public_key = signer_private_key.public_key()
        self.min_grounding_bps = min_grounding_bps
        self.step_history: List[GroundedStepReceipt] = []

    @staticmethod
    def compute_grounding_bps(context_spans: Sequence[str], generated_output: str) -> int:
        clean_spans = [s.strip() for s in context_spans if s.strip()]
        out_tokens = [
            tok.strip(".,;:!?()[]{}\"'").lower()
            for tok in generated_output.split()
            if tok.strip(".,;:!?()[]{}\"'")
        ]
        if not clean_spans or not out_tokens:
            return 0
        ctx_vocab: Set[str] = {
            tok.strip(".,;:!?()[]{}\"'").lower()
            for span in clean_spans
            for tok in span.split()
            if tok.strip(".,;:!?()[]{}\"'")
        }
        matched = sum(1 for tok in out_tokens if tok in ctx_vocab)
        return (matched * 10000) // len(out_tokens)

    def evaluate_and_sign_step(
        self,
        *,
        step_id: str,
        model_id: str,
        caid: str,
        context_spans: Sequence[str],
        generated_output: str,
    ) -> GroundedStepReceipt:
        clean_spans = [s.strip() for s in context_spans if s.strip()]
        ctx_digest = _sha256_jcs(clean_spans)
        score_bps = self.compute_grounding_bps(clean_spans, generated_output)

        if not clean_spans or not generated_output.strip():
            status = "HALTED_EMPTY_CONTEXT_OR_OUTPUT"
        elif score_bps < self.min_grounding_bps:
            status = "DEGRADED"
        else:
            status = "HEALTHY"

        prior_window = self.step_history[-2:]
        has_prior_degraded = any(r.status != "HEALTHY" for r in prior_window)
        if status == "DEGRADED" and has_prior_degraded and len(prior_window) >= 2:
            status = "HALTED_COMPOUND_DRIFT"

        temp = GroundedStepReceipt(
            step_id=step_id,
            model_id=model_id,
            caid=caid,
            context_digest=ctx_digest,
            grounding_score_bps=score_bps,
            status=status,
            signature_b64="",
        )
        sig_b64 = base64.b64encode(
            self._priv.sign(encode_jcs(temp.statement_dict()))
        ).decode("ascii")
        receipt = GroundedStepReceipt(
            step_id=temp.step_id,
            model_id=temp.model_id,
            caid=temp.caid,
            context_digest=temp.context_digest,
            grounding_score_bps=temp.grounding_score_bps,
            status=temp.status,
            signature_b64=sig_b64,
        )
        self.step_history.append(receipt)
        return receipt

    @staticmethod
    def verify_receipt(receipt: GroundedStepReceipt, public_key: Ed25519PublicKey) -> bool:
        try:
            public_key.verify(
                base64.b64decode(receipt.signature_b64),
                encode_jcs(receipt.statement_dict()),
            )
            return True
        except (InvalidSignature, ValueError) as exc:
            raise ValueError(f"HALT_INVALID_GROUNDED_STEP_SIGNATURE: {exc}") from exc


# ---------------------------------------------------------------------------
# Part III: Hardened x402 Payment Escrow Interceptor (Wired to Real EO1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class X402PaymentIntent:
    """Canonical x402 payment challenge request."""

    recipient_url: str
    amount_minor: int
    currency: str
    challenge_nonce: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "amount_minor": self.amount_minor,
            "currency": self.currency,
            "challenge_nonce": self.challenge_nonce,
            "recipient_url": self.recipient_url,
        }


class HardenedX402EscrowInterceptor:
    """
    Defends against the October 2026 x402 SDK token-drain and smurfing attacks,
    wired directly to the real `PreDispatchIntentInterlock` (`src/eo1_write_before_execute.py`):
    1. SIWx Origin & Destination URL Binding (`HALT_X402_URL_MISMATCH`).
    2. Per-Intent Spend Cap (`HALT_X402_SPEND_CAP_EXCEEDED`).
    3. Cumulative Epoch Wallet-Drain Cap (`HALT_X402_EPOCH_WALLET_DRAIN_BLOCKED`).
    4. Challenge Nonce Replay Protection (`HALT_X402_NONCE_REPLAY`).
    5. Stablecoin Allowlist (`HALT_X402_UNRECOGNIZED_CURRENCY`).
    6. Durable `EO1` Write-Before-Execute Commit (`F_FULLFSYNC` + `fcntl.flock`).
    """

    ALLOWED_CURRENCIES = ("USDC", "USD_STABLE")

    def __init__(
        self,
        interlock: PreDispatchIntentInterlock,
        *,
        max_per_intent_minor: int = 100,
        max_epoch_wallet_minor: int = 500,
    ) -> None:
        if max_per_intent_minor <= 0 or max_epoch_wallet_minor < max_per_intent_minor:
            raise ValueError("Invalid x402 spend cap configuration")
        self.interlock = interlock
        self.max_per_intent_minor = max_per_intent_minor
        self.max_epoch_wallet_minor = max_epoch_wallet_minor
        self.cumulative_epoch_spend_minor = 0
        self.consumed_nonces: Set[str] = set()

    def authorize_and_dispatch_x402(
        self,
        req: X402PaymentIntent,
        expected_402_url: str,
    ) -> Dict[str, Any]:
        if req.recipient_url != expected_402_url:
            raise RuntimeError(
                f"HALT_X402_URL_MISMATCH: {req.recipient_url!r} != {expected_402_url!r}"
            )
        if req.currency not in self.ALLOWED_CURRENCIES:
            raise RuntimeError(f"HALT_X402_UNRECOGNIZED_CURRENCY: {req.currency!r}")
        if req.amount_minor <= 0 or req.amount_minor > self.max_per_intent_minor:
            raise RuntimeError(
                f"HALT_X402_SPEND_CAP_EXCEEDED: {req.amount_minor} outside 1..{self.max_per_intent_minor}"
            )
        if not req.challenge_nonce.strip() or req.challenge_nonce in self.consumed_nonces:
            raise RuntimeError(f"HALT_X402_NONCE_REPLAY: {req.challenge_nonce!r}")
        if self.cumulative_epoch_spend_minor + req.amount_minor > self.max_epoch_wallet_minor:
            raise RuntimeError(
                f"HALT_X402_EPOCH_WALLET_DRAIN_BLOCKED: cumulative spend would reach "
                f"{self.cumulative_epoch_spend_minor + req.amount_minor} > {self.max_epoch_wallet_minor}"
            )

        payload = req.to_dict()
        caid = compute_caid(payload)
        res = self.interlock.dispatch(
            target_uri=req.recipient_url,
            tool_name="x402.sign_and_settle",
            payload=payload,
            dispatch_fn=lambda: caid,
        )
        if res.lifecycle_state != IntentLifecycleState.RECONCILED:
            raise RuntimeError(f"HALT_X402_EO1_NOT_RECONCILED: {res.lifecycle_state}")

        self.consumed_nonces.add(req.challenge_nonce)
        self.cumulative_epoch_spend_minor += req.amount_minor
        return {
            "caid": caid,
            "lifecycle_state": res.lifecycle_state.value,
            "amount_minor": req.amount_minor,
            "cumulative_epoch_spend_minor": self.cumulative_epoch_spend_minor,
            "remaining_epoch_wallet_minor": self.max_epoch_wallet_minor - self.cumulative_epoch_spend_minor,
            "receipt_chain_tip": res.receipt.chain_tip if res.receipt else "",
        }


# ---------------------------------------------------------------------------
# Part IV: Live Hardware F_FULLFSYNC & SQLite FTS5 Experiment Runner
# ---------------------------------------------------------------------------


class LiveHardwareAndSqliteExperimentRunner:
    """
    Executes real on-disk EO1 F_FULLFSYNC / os.fsync durability dispatches and
    real SQLite FTS5 bm25 queries via HyperSUStore, returning live empirical
    measurements with zero hardcoded benchmark literals.
    """

    @staticmethod
    def run_live_durability_and_fts5_experiment(
        *,
        eo1_iterations: int = 8,
        fts_fact_count: int = 40,
    ) -> Dict[str, Any]:
        if eo1_iterations <= 0 or fts_fact_count <= 0:
            raise ValueError("Experiment counts must be positive")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            ledger_path = tmp_root / "live_eo1_ledger.jsonl"
            state_dir = tmp_root / "live_eo1_state"
            interlock = PreDispatchIntentInterlock(
                ledger_path=ledger_path,
                output_state_dir=state_dir,
            )

            eo1_elapsed_ns: List[int] = []
            for idx in range(eo1_iterations):
                t0 = time.perf_counter_ns()
                interlock.dispatch(
                    target_uri="https://paid-api.example.org/v1/compute",
                    tool_name="live_experiment.step",
                    payload={"iteration": idx, "experiment": "real_hardware_fsync"},
                    dispatch_fn=lambda: {"ok": True},
                )
                eo1_elapsed_ns.append(time.perf_counter_ns() - t0)

            eo1_elapsed_ns.sort()
            median_eo1_ns = eo1_elapsed_ns[len(eo1_elapsed_ns) // 2]

            db_path = tmp_root / "live_hypersu.db"
            src_file = tmp_root / "genomic_anchor.txt"
            src_text = (
                "ABL1 P00520 rigid kinase domain spans residues 75 to 512 in AlphaFold v6; "
                "TP53 chr17:7675088 phyloP100way is 6.16111."
            )
            src_file.write_text(src_text, encoding="utf-8")

            store = HyperSUStore(db_path)
            try:
                for idx in range(fts_fact_count):
                    fact_text = f"Fact {idx}: {src_text}"
                    store.add_fact(
                        FactRecord(
                            fact_id=f"fact-{idx:04d}",
                            episode_id="ep-live-experiment",
                            label="GENOMIC_ANCHOR",
                            text=fact_text,
                            source_id=f"src-{idx:04d}",
                            file_path=str(src_file),
                            start_char=0,
                            end_char=len(fact_text),
                            content_sha256=compute_sha256_hex(fact_text.encode("utf-8")),
                        )
                    )
                retriever = HyperSUFTSRetriever(store)
                t_fts0 = time.perf_counter_ns()
                hits = retriever.coarse_to_fine_retrieve(
                    "P00520 kinase phyloP100way",
                    limit=5,
                )
                fts_query_ns = time.perf_counter_ns() - t_fts0
            finally:
                store.close()

            ledger_lines = [
                ln
                for ln in ledger_path.read_text(encoding="utf-8").splitlines()
                if ln.strip()
            ]

            return {
                "eo1_iterations_executed": eo1_iterations,
                "eo1_ledger_records_persisted": len(ledger_lines),
                "eo1_median_latency_ns": median_eo1_ns,
                "fts_facts_indexed": fts_fact_count,
                "fts_hits_returned": len(hits),
                "fts_query_latency_ns": fts_query_ns,
            }
