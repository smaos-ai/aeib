"""
Deterministic Air-Gapped Reproducible Evidence Archive Builder (`v1.0.0-rc.5-preprod`).
- Runs Phase 0 + Tracks 1, 2, 3, and 4.
- Produces canonical, timestamp-free JSON evidence reports.
- Packages all source modules, TLA+ models, and reports into a deterministic tarball
  with fixed mtime (`SOURCE_DATE_EPOCH = 1760918400`), uid=0, gid=0, and sorted entries.
- Extracts the archive into an isolated clean-room directory and verifies every SHA-256 digest.
"""
import gzip
import hashlib
import io
import json
import os
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_agent_deception_interlock import (
    test_deception_interlock_nominal_and_tripwire_catches,
)
from tests.test_leviathan_and_cross_tenant_isolation import (
    test_cross_tenant_governor_seven_isolation_properties,
    test_leviathan_fts5_bounded_cards_and_invariant_retention,
)
from tests.test_otel_genai_evidence_chain import (
    test_evidence_receipt_hash_chain_and_tamper_detection,
    test_human_override_ledger_warrant_validation,
    test_otel_genai_semantic_span_attributes,
)
from tests.test_runtime_boundary_and_state_machine import (
    test_runtime_boundary_falsifications_and_uncertainty_latch,
    test_runtime_boundary_nominal_and_consequential_flow,
)
from tests.test_structural_cve_boundary_fixtures import (
    test_all_four_structural_cve_fixtures_and_aeib_containment,
)
from tests.test_cve_2026_33017_langflow_rce import (
    test_cve_2026_33017_aeib_ast_policy_gate_containment,
    test_cve_2026_33017_aeib_station1_taint_and_authorization_gate,
)
from tests.test_vibe_coding_and_long_horizon_guard import (
    test_gitai_bisect_isolates_breaking_patch,
    test_iaps_agent_honeypot_detection_and_deterrence,
    test_vibe_coding_missing_auth_and_rls_detection,
)
from benchmarks.locomo_context_quality import evaluate_locomo_benchmark
from benchmarks.maseval_integration import run_maseval_comparative_benchmark
from tools.context_ram_and_maseval_harness import (
    test_context_ram_hawkes_and_dynamic_workflows,
)
from tools.phase0_integrity_reset_core import (
    canonical_json_v1,
    test_phase0_integrity_reset_all_blockers,
)
from tools.regulatory_three_tier_and_matrix import (
    generate_regulatory_applicability_matrix,
    test_three_tier_decision_gate_and_applicability_matrix,
)
from tools.smf_frontier_oct2026_upgrades import (
    test_smf_frontier_oct2026_upgrades,
)
from tools.tlaplus_model_conformance_checker import (
    explore_tla_state_space_and_verify_conformance,
)

FIXED_EPOCH = 1760918400  # 2025-10-20T00:00:00Z deterministic build timestamp


def _sanitize_for_canonical_json(val: Any) -> Any:
    if isinstance(val, float):
        return f"{val:.4f}"
    if isinstance(val, dict):
        return {k: _sanitize_for_canonical_json(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_sanitize_for_canonical_json(x) for x in val]
    return val


def build_and_verify_deterministic_archive(output_dir: Path) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Execute all verification tracks
    test_phase0_integrity_reset_all_blockers()
    test_all_four_structural_cve_fixtures_and_aeib_containment()
    test_three_tier_decision_gate_and_applicability_matrix()
    test_context_ram_hawkes_and_dynamic_workflows()
    test_smf_frontier_oct2026_upgrades()
    test_runtime_boundary_nominal_and_consequential_flow()
    test_runtime_boundary_falsifications_and_uncertainty_latch()
    test_otel_genai_semantic_span_attributes()
    test_evidence_receipt_hash_chain_and_tamper_detection()
    test_human_override_ledger_warrant_validation()
    test_deception_interlock_nominal_and_tripwire_catches()
    test_leviathan_fts5_bounded_cards_and_invariant_retention()
    test_cross_tenant_governor_seven_isolation_properties()
    test_cve_2026_33017_aeib_ast_policy_gate_containment()
    test_cve_2026_33017_aeib_station1_taint_and_authorization_gate()
    test_vibe_coding_missing_auth_and_rls_detection()
    test_gitai_bisect_isolates_breaking_patch()
    test_iaps_agent_honeypot_detection_and_deterrence()
    locomo_report = _sanitize_for_canonical_json(evaluate_locomo_benchmark())
    maseval_report = _sanitize_for_canonical_json(run_maseval_comparative_benchmark())
    tla_report = explore_tla_state_space_and_verify_conformance()

    # 2. Generate deterministic, timestamp-free canonical JSON evidence artifacts
    summary_payload = {
        "baseline_version": "v1.0.0-rc.5-preprod",
        "epistemic_status": "locally_reproducible_development_baseline_ready_for_external_reproduction",
        "phase0_blockers_closed": [
            "0.1_canonical_json_caid",
            "0.2_at57b_pure_taint",
            "0.3_at58_escrow_wal",
            "0.4_g3_boot_reverify",
        ],
        "structural_cve_fixtures_verified": [
            "CVE-2026-33017_langflow_build_public_tmp",
            "CVE-2025-53773_vscode_autoapprove_yolo",
            "CVE-2026-77521_maxkb_tainted_shell",
            "CVE-2026-90970_gitlab_gateway_template_escape",
        ],
        "locomo_context_quality": locomo_report,
        "maseval_consequential_mutations": maseval_report,
        "tla_conformance": tla_report,
        "regulatory_matrix": generate_regulatory_applicability_matrix(),
    }

    report_bytes = canonical_json_v1(summary_payload) + b"\n"
    report_path = output_dir / "rc5_canonical_evidence_report.json"
    report_path.write_bytes(report_bytes)

    # 3. Build deterministic tar.gz in memory twice to prove bit-identical reproducibility
    files_to_pack: List[Tuple[str, bytes]] = [
        ("rc5_canonical_evidence_report.json", report_bytes),
    ]
    for rel_file in sorted(
        [
            "benchmarks/locomo_context_quality.py",
            "benchmarks/maseval_integration.py",
            "docs/benchmarks/maseval_results.md",
            "docs/compliance/china_agent_regulation_crosswalk.md",
            "formal/tlaplus/AEIBStation1And2.tla",
            "formal/tlaplus/TLC_OUTPUT.md",
            "src/context/__init__.py",
            "src/context/leviathan_context_engine.py",
            "src/deception/__init__.py",
            "src/deception/agent_deception_interlock.py",
            "src/governance/cross_tenant_sovereign_governor.py",
            "src/observability/__init__.py",
            "src/observability/otel_genai_evidence_chain.py",
            "src/runtime_boundary/__init__.py",
            "src/runtime_boundary/runtime_execution_boundary.py",
            "tests/test_agent_deception_interlock.py",
            "tests/test_cve_2026_33017_langflow_rce.py",
            "tests/test_leviathan_and_cross_tenant_isolation.py",
            "tests/test_otel_genai_evidence_chain.py",
            "tests/test_runtime_boundary_and_state_machine.py",
            "tests/test_structural_cve_boundary_fixtures.py",
            "tests/test_vibe_coding_and_long_horizon_guard.py",
            "tools/context_ram_and_maseval_harness.py",
            "tools/phase0_integrity_reset_core.py",
            "tools/regulatory_three_tier_and_matrix.py",
            "tools/smf_frontier_oct2026_upgrades.py",
            "tools/tlaplus_model_conformance_checker.py",
            "tools/vibe_coding_and_long_horizon_guard.py",
        ]
    ):
        p = Path(rel_file)
        if p.exists():
            files_to_pack.append((rel_file, p.read_bytes()))

    manifest_lines: List[str] = []
    for arcname, content in files_to_pack:
        h = hashlib.sha256(content).hexdigest()
        manifest_lines.append(f"{h}  {arcname}")
    manifest_bytes = ("\n".join(manifest_lines) + "\n").encode("utf-8")
    files_to_pack.append(("SHA256SUMS.txt", manifest_bytes))

    def _create_deterministic_tar_gz() -> bytes:
        raw_buf = io.BytesIO()
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=raw_buf, mtime=FIXED_EPOCH
        ) as gz:
            with tarfile.open(mode="w", fileobj=gz) as tar:
                for arcname, data in sorted(files_to_pack, key=lambda x: x[0]):
                    info = tarfile.TarInfo(name=arcname)
                    info.size = len(data)
                    info.mtime = FIXED_EPOCH
                    info.uid = 0
                    info.gid = 0
                    info.uname = "root"
                    info.gname = "root"
                    info.mode = 0o644
                    tar.addfile(info, io.BytesIO(data))
        return raw_buf.getvalue()

    archive_bytes_1 = _create_deterministic_tar_gz()
    archive_bytes_2 = _create_deterministic_tar_gz()
    assert archive_bytes_1 == archive_bytes_2, "Archive generation is not bit-identical!"

    archive_path = output_dir / "aeib_v1.0.0_rc5_preprod_reproducible_bundle.tar.gz"
    archive_path.write_bytes(archive_bytes_1)
    archive_sha256 = hashlib.sha256(archive_bytes_1).hexdigest()

    # 4. Clean-room extraction & SHA256SUMS verification
    with tempfile.TemporaryDirectory() as clean_dir:
        with tarfile.open(archive_path, mode="r:gz") as tar:
            tar.extractall(path=clean_dir, filter="data")
        extracted_manifest = (
            (Path(clean_dir) / "SHA256SUMS.txt").read_text("utf-8").splitlines()
        )
        for line in extracted_manifest:
            if not line.strip():
                continue
            expected_hash, rel_name = line.split("  ", 1)
            actual_hash = hashlib.sha256(
                (Path(clean_dir) / rel_name).read_bytes()
            ).hexdigest()
            assert actual_hash == expected_hash, f"Hash mismatch on {rel_name}"

    return {
        "archive_path": str(archive_path),
        "archive_sha256": archive_sha256,
        "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
        "files_verified_in_cleanroom": len(files_to_pack),
    }


def test_deterministic_rc5_archive_builder() -> None:
    with tempfile.TemporaryDirectory() as out_dir:
        res = build_and_verify_deterministic_archive(Path(out_dir))
        assert len(res["archive_sha256"]) == 64
        assert res["files_verified_in_cleanroom"] >= 2


if __name__ == "__main__":
    receipt = build_and_verify_deterministic_archive(Path("output/rc5_reproducible"))
    print(json.dumps(receipt, indent=2))
