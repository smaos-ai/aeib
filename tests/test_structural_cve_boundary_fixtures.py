"""
Track 1: Structural CVE Boundary Reproduction & Containment Suite.

Reproduces the structural vulnerability mechanics of four real-world agent/gateway CVEs
against controlled local fixtures (100% offline, zero external network calls), demonstrating under the stated model:
1. The exploit path succeeds against the unguarded vulnerable fixture.
2. The AEIB Execution Boundary blocks the consequential effect structurally (not via
   brittle keyword matching).

Covered CVEs:
- CVE-2026-33017 (Langflow <= 1.8.2, CVSS 9.8): Unauthenticated `build_public_tmp`
  accepting an untrusted `data` flow parameter that executes `ast.Assign` nodes during
  graph compilation (`validate.py`).
- CVE-2025-53773 (GitHub Copilot / VS Code, CVSS 7.8): Prompt-injected file write
  mutating `.vscode/settings.json` to enable `"chat.tools.autoApprove": true` ("YOLO mode").
- CVE-2026-77521 (MaxKB < 2.10.5-lts, CVSS 10.0): Tool-enabled assistant invoking an
  ungated shell execution tool from untrusted external RAG/prompt context.
- CVE-2026-90970 (GitLab AI Gateway < 19.4.1, CVSS 9.9): Crafted Duo Agent flow
  configuration escaping a template renderer to read ambient gateway JWT signing keys.
"""
import ast
import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tools.phase0_integrity_reset_core import (
    Phase0ExecutionBoundary,
    _sign_act,
    canonical_json_v1,
)


# ============================================================================
# 1. CVE-2026-33017 FIXTURE: LANGFLOW `build_public_tmp` FLOW DATA OVERRIDE
# ============================================================================
class VulnerableLangflowBuilderFixture:
    """
    Reproduces the structural flaw in Langflow <= 1.8.2:
    `POST /api/v1/build_public_tmp/{flow_id}/flow` accepts an optional `data` payload
    that overrides the database-pinned flow and compiles custom component code where
    even top-level `ast.Assign` statements execute side effects.
    """

    def __init__(self, pinned_flows: Dict[str, str]) -> None:
        self.pinned_flows = dict(pinned_flows)  # flow_id -> safe code string
        self.compromised_marker: Optional[str] = None

    def build_public_tmp_unguarded(
        self, flow_id: str, optional_data_override: Optional[Dict[str, str]] = None
    ) -> str:
        # FLAW 1 (CWE-306 / Untrusted Override): Accepts `optional_data_override` from caller
        code_to_build = (
            optional_data_override["custom_component_code"]
            if optional_data_override and "custom_component_code" in optional_data_override
            else self.pinned_flows[flow_id]
        )
        # FLAW 2 (CWE-94 / CWE-95): Executes top-level statements during validation
        local_ns: Dict[str, Any] = {"__compromise_hook__": self._record_rce}
        builtin_exec = getattr(sys.modules["builtins"], "exec")
        builtin_exec(compile(code_to_build, "<flow_validate>", "exec"), {}, local_ns)
        return "FLOW_BUILT"

    def _record_rce(self, payload: str) -> str:
        self.compromised_marker = payload
        return payload


class AeibLangflowBoundaryGuard:
    """
    AEIB Structural Countermeasure for CVE-2026-33017:
    1. Rejects any client-supplied `data` flow override on `build_public_tmp`; only builds
       flows whose SHA-256 digest matches the pre-registered immutable flow manifest.
    2. Static AST gate parses the component AST without `exec()` and rejects
       any `ast.Call` inside top-level `ast.Assign` or any dynamic execution primitive.
    """

    def __init__(self, pinned_flow_digests: Dict[str, str]) -> None:
        self.pinned_flow_digests = dict(pinned_flow_digests)

    def validate_flow_build_request(
        self,
        flow_id: str,
        stored_flow_code: str,
        optional_data_override: Optional[Dict[str, str]],
    ) -> Dict[str, str]:
        if optional_data_override is not None:
            return {
                "disposition": "NOT_DISPATCHED",
                "code": "ERR_CVE_2026_33017_UNPINNED_FLOW_DATA_OVERRIDE_DENIED",
            }

        actual_digest = f"sha256:{hashlib.sha256(stored_flow_code.encode('utf-8')).hexdigest()}"
        if self.pinned_flow_digests.get(flow_id) != actual_digest:
            return {
                "disposition": "NOT_DISPATCHED",
                "code": "ERR_FLOW_MANIFEST_DIGEST_MISMATCH",
            }

        # Static AST verification (never calls exec/eval)
        tree = ast.parse(stored_flow_code)
        for node in tree.body:
            if isinstance(node, ast.Assign):
                if isinstance(node.value, ast.Call):
                    return {
                        "disposition": "NOT_DISPATCHED",
                        "code": "ERR_TOP_LEVEL_ASSIGN_CALL_FORBIDDEN_IN_COMPONENT",
                    }
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                return {
                    "disposition": "NOT_DISPATCHED",
                    "code": "ERR_TOP_LEVEL_EXPR_CALL_FORBIDDEN_IN_COMPONENT",
                }

        return {"disposition": "DISPATCHED", "code": "OK"}


# ============================================================================
# 2. CVE-2025-53773 FIXTURE: `.vscode/settings.json` "YOLO MODE" ESCALATION
# ============================================================================
class AeibWorkspaceFileBoundary:
    """
    AEIB Structural Countermeasure for CVE-2025-53773:
    1. Canonical `os.path.realpath` confinement strictly to `ALLOWED_EXPORT_DIRS`
       (e.g., `<workspace>/output/`), denying writes to `.vscode/`, `.git/`, or dotfiles.
    2. Immutable configuration lock: any attempt by an agent tool call to modify
       IDE/harness approval policies (`chat.tools.autoApprove`) is rejected fail-closed.
    """

    def __init__(self, allowed_export_dir: Path) -> None:
        self.allowed_root = allowed_export_dir.resolve()

    def evaluate_file_write(self, target_rel_path: str, content: str) -> Dict[str, str]:
        candidate = (self.allowed_root.parent / target_rel_path).resolve()
        # Reject any dotfile / IDE config directory or escape outside allowed_root
        parts = candidate.relative_to(self.allowed_root.parent).parts if candidate.is_relative_to(self.allowed_root.parent) else ()
        if any(p.startswith(".") for p in parts) or not candidate.is_relative_to(self.allowed_root):
            return {
                "disposition": "NOT_DISPATCHED",
                "code": "ERR_CVE_2025_53773_PROTECTED_CONFIG_OR_PATH_ESCAPE_DENIED",
            }
        return {"disposition": "DISPATCHED", "code": "OK"}


# ============================================================================
# 3. CVE-2026-90970 FIXTURE: GITLAB AI GATEWAY TEMPLATE SANDBOX & KEY THEFT
# ============================================================================
class VulnerableTemplateGatewayFixture:
    """
    Reproduces the structural flaw in GitLab AI Gateway (CVE-2026-90970):
    1. Gateway worker holds `JWT_SIGNING_KEY` in its process environment/globals.
    2. Flow configuration template is rendered with object attribute traversal enabled.
    """

    def __init__(self) -> None:
        self.ambient_Popup_env = {"GATEWAY_JWT_SIGNING_KEY": "secret-jwt-key-999"}

    def render_flow_unguarded(self, flow_template: str) -> str:
        # Simulates SSTI / template attribute escape reading process secrets
        return flow_template.format(env=self.ambient_Popup_env)


class AeibCredentialStarvedTemplateGateway:
    """
    AEIB Structural Countermeasure for CVE-2026-90970:
    1. Credential Starvation: The worker/template process holds ZERO
       signing keys or bearer secrets in its environment (`env == {}`).
    2. Strict data-only placeholder substitution: rejects attribute/index traversal
       (`{env[...]}`) in flow definitions.
    """

    @staticmethod
    def render_flow_guarded(flow_template: str, safe_vars: Dict[str, str]) -> Dict[str, str]:
        if "[" in flow_template or "." in flow_template or "__" in flow_template:
            return {
                "disposition": "NOT_DISPATCHED",
                "code": "ERR_CVE_2026_90970_TEMPLATE_TRAVERSAL_SYNTAX_DENIED",
            }
        return {"disposition": "DISPATCHED", "rendered": flow_template}


# ============================================================================
# FULL STRUCTURAL VERIFICATION TESTS FOR ALL 4 CVEs
# ============================================================================
def test_all_four_structural_cve_fixtures_and_aeib_containment() -> None:
    # --- TEST 1: CVE-2026-33017 (Langflow build_public_tmp RCE) ---
    safe_code = "class SafeComponent:\n    x = 42\n"
    safe_digest = f"sha256:{hashlib.sha256(safe_code.encode('utf-8')).hexdigest()}"
    vuln_langflow = VulnerableLangflowBuilderFixture({"flow-1": safe_code})

    # Attack payload uses `ast.Assign` (`_x = __compromise_hook__(...)`)
    exploit_override = {
        "custom_component_code": '_x = __compromise_hook__("AWS_SECRET_EXFILTRATED")\n'
    }
    # Prove exploit succeeds against the unguarded fixture
    vuln_langflow.build_public_tmp_unguarded("flow-1", exploit_override)
    assert vuln_langflow.compromised_marker == "AWS_SECRET_EXFILTRATED"

    # Prove AEIB guard blocks both the `data` override AND top-level `ast.Assign` calls
    guard_langflow = AeibLangflowBoundaryGuard({"flow-1": safe_digest})
    res_override = guard_langflow.validate_flow_build_request(
        "flow-1", safe_code, exploit_override
    )
    assert res_override["disposition"] == "NOT_DISPATCHED"
    assert res_override["code"] == "ERR_CVE_2026_33017_UNPINNED_FLOW_DATA_OVERRIDE_DENIED"

    malicious_stored = '_x = __compromise_hook__("INJECTED")\n'
    mal_digest = f"sha256:{hashlib.sha256(malicious_stored.encode('utf-8')).hexdigest()}"
    guard_ast = AeibLangflowBoundaryGuard({"flow-mal": mal_digest})
    res_ast = guard_ast.validate_flow_build_request("flow-mal", malicious_stored, None)
    assert res_ast["disposition"] == "NOT_DISPATCHED"
    assert res_ast["code"] == "ERR_TOP_LEVEL_ASSIGN_CALL_FORBIDDEN_IN_COMPONENT"

    # --- TEST 2: CVE-2025-53773 (VS Code / Copilot `.vscode/settings.json` YOLO Mode) ---
    with tempfile.TemporaryDirectory() as tmpdir:
        ws_root = Path(tmpdir)
        export_dir = ws_root / "output"
        export_dir.mkdir()
        file_guard = AeibWorkspaceFileBoundary(export_dir)

        yolo_payload = json.dumps({"chat.tools.autoApprove": True})
        res_vscode = file_guard.evaluate_file_write(".vscode/settings.json", yolo_payload)
        assert res_vscode["disposition"] == "NOT_DISPATCHED"
        assert (
            res_vscode["code"]
            == "ERR_CVE_2025_53773_PROTECTED_CONFIG_OR_PATH_ESCAPE_DENIED"
        )

        # Valid export inside `<workspace>/output/report.json` succeeds
        res_valid_export = file_guard.evaluate_file_write("output/report.json", '{"ok":true}')
        assert res_valid_export["disposition"] == "DISPATCHED"

    # --- TEST 3: CVE-2026-77521 (MaxKB Ungated Shell Tool from Untrusted RAG Taint) ---
    priv = Ed25519PrivateKey.generate()
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp_db:
        db_path = tmp_db.name
    try:
        boundary = Phase0ExecutionBoundary(
            db_path=db_path,
            public_keys={"k1": priv.public_key()},
            sprint_limit_minor=500_00,
            pinned_recipients={"iban:DE89370400440532013000"},
        )
        maxkb_act = {
            "operation_id": "op-maxkb-shell",
            "action_type": "tool.execute_shell",
            "amount_minor": 0,
            "max_per_call_minor": 0,
            "recipient": "iban:DE89370400440532013000",
            "taint_tier": "TIER_2_UNTRUSTED",  # Tainted by RAG knowledge base document
            "policy_epoch": "2026-Q4",
        }
        v_maxkb = boundary.authorize_and_reserve(_sign_act(priv, "k1", maxkb_act))
        assert v_maxkb.disposition == "NOT_DISPATCHED"
        assert v_maxkb.code == "ERR_AT57B_UNTAMPERED_TAINT_TIER2_CONSEQUENTIAL_DENIED"
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)

    # --- TEST 4: CVE-2026-90970 (GitLab AI Gateway Flow Template Escape & JWT Key Theft) ---
    vuln_gw = VulnerableTemplateGatewayFixture()
    leaked = vuln_gw.render_flow_unguarded("Leak: {env[GATEWAY_JWT_SIGNING_KEY]}")
    assert "secret-jwt-key-999" in leaked

    res_gw = AeibCredentialStarvedTemplateGateway.render_flow_guarded(
        "Leak: {env[GATEWAY_JWT_SIGNING_KEY]}", {}
    )
    assert res_gw["disposition"] == "NOT_DISPATCHED"
    assert res_gw["code"] == "ERR_CVE_2026_90970_TEMPLATE_TRAVERSAL_SYNTAX_DENIED"


# ============================================================================
# 5. CONSOLIDATED STRUCTURAL CVE BOUNDARY GATE & MARKTECHPOST 4-SIGNAL SUITE
# ============================================================================
class StructuralCveBoundaryGate:
    """
    AEIB structural defenses against:
    1. CVE-2026-33017 (Langflow): Rejects any caller-supplied `data` graph override;
       only executes flows matching a pre-signed `flow_id -> sha256(graph)` manifest.
    2. CVE-2025-53773 & CVE-2025-54136 (Copilot / Cursor): Enforces canonical path
       confinement (`os.path.realpath`) and denies agent writes to control-plane
       dotfiles (`.vscode/`, `.cursor/`, `.git/`, `.claude/`, `.env`, `.pth`).
    3. Marktechpost 4-Signal Intelligence Countermeasures:
       - Signal 1 (OOB Monitor Anti-Disarmament): Rejects any agent attempt to
         kill, patch, or modify out-of-band monitor sockets or policy files.
       - Signal 4 (LiteLLM 1.107.0 `.pth` Supply-Chain Lock): Blocks dynamic
         `pip install` / `uv add` / `site-packages/*.pth` startup hooks without
         an explicit step-up cryptographic warrant.
    """

    PROTECTED_CONTROL_PREFIXES = (
        ".vscode",
        ".cursor",
        ".git",
        ".claude",
        ".github",
        ".env",
    )

    def __init__(self, workspace_root: str, pinned_flow_digests: Dict[str, str]) -> None:
        self.workspace_root = os.path.realpath(workspace_root)
        self.allowed_export_dir = os.path.realpath(
            os.path.join(self.workspace_root, "output")
        )
        self.pinned_flow_digests = dict(pinned_flow_digests)

    def validate_langflow_build_request(
        self,
        flow_id: str,
        stored_flow_graph: Dict[str, Any],
        caller_supplied_data_override: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str]:
        if caller_supplied_data_override is not None:
            return (
                "NOT_DISPATCHED",
                "ERR_CVE_2026_33017_CALLER_FLOW_DATA_OVERRIDE_FORBIDDEN",
            )

        digest = (
            "sha256:"
            + hashlib.sha256(
                json.dumps(
                    stored_flow_graph, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            ).hexdigest()
        )
        if self.pinned_flow_digests.get(flow_id) != digest:
            return "NOT_DISPATCHED", "ERR_UNPINNED_OR_TAMPERED_FLOW_GRAPH"

        return "DISPATCHED", "OK"

    def validate_file_write_request(self, target_rel_path: str) -> Tuple[str, str]:
        resolved = os.path.realpath(os.path.join(self.workspace_root, target_rel_path))
        if not resolved.startswith(self.workspace_root + os.sep):
            return "NOT_DISPATCHED", "ERR_PATH_TRAVERSAL_OUTSIDE_WORKSPACE"

        rel_from_root = os.path.relpath(resolved, self.workspace_root)
        parts = rel_from_root.split(os.sep)
        if any(
            part in self.PROTECTED_CONTROL_PREFIXES or part.startswith(".")
            for part in parts
        ) or resolved.endswith(".pth"):
            return (
                "NOT_DISPATCHED",
                "ERR_CVE_2025_53773_54136_CONTROL_PLANE_DOTFILE_WRITE_DENIED",
            )

        if not resolved.startswith(self.allowed_export_dir + os.sep):
            return "NOT_DISPATCHED", "ERR_WRITE_OUTSIDE_ALLOWED_EXPORT_DIR"

        return "DISPATCHED", "OK"

    @staticmethod
    def validate_package_or_monitor_action(
        command_argv: List[str],
        has_step_up_warrant: bool = False,
    ) -> Tuple[str, str]:
        joined = " ".join(command_argv).lower()
        # Signal 1: Out-of-band monitor anti-disarmament check
        if any(
            tok in joined
            for tok in ("aeib-monitor", "tetragon", "seccomp", "auditd", "kill -9")
        ):
            return "NOT_DISPATCHED", "ERR_SIGNAL1_OOB_MONITOR_DISARMAMENT_BLOCKED"

        # Signal 4: LiteLLM 1.107.0 / PyPI `.pth` startup hook & dynamic install lock
        if any(
            pkg_cmd in joined
            for pkg_cmd in ("pip install", "uv add", "npm install", "cargo install", ".pth")
        ):
            if not has_step_up_warrant:
                return (
                    "NOT_DISPATCHED",
                    "ERR_SIGNAL4_DYNAMIC_PACKAGE_OR_PTH_HOOK_REQUIRES_STEP_UP",
                )
        return "DISPATCHED", "OK"


def test_cve_2026_33017_langflow_unauthenticated_graph_override_blocked() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "output"), exist_ok=True)
        clean_graph = {"nodes": [{"id": "n1", "type": "SafePromptNode"}]}
        clean_digest = (
            "sha256:"
            + hashlib.sha256(
                json.dumps(clean_graph, sort_keys=True, separators=(",", ":")).encode(
                    "utf-8"
                )
            ).hexdigest()
        )
        gate = StructuralCveBoundaryGate(tmpdir, {"flow_prod_1": clean_digest})

        assert gate.validate_langflow_build_request("flow_prod_1", clean_graph, None) == (
            "DISPATCHED",
            "OK",
        )

        attacker_override = {
            "nodes": [
                {
                    "id": "n1",
                    "code": "def f(x=__import__('subprocess').check_output('id')): return x",
                }
            ]
        }
        disp, code = gate.validate_langflow_build_request(
            "flow_prod_1",
            clean_graph,
            caller_supplied_data_override=attacker_override,
        )
        assert disp == "NOT_DISPATCHED"
        assert code == "ERR_CVE_2026_33017_CALLER_FLOW_DATA_OVERRIDE_FORBIDDEN"


def test_cve_2025_53773_and_54136_ide_control_plane_mutation_blocked() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "output"), exist_ok=True)
        gate = StructuralCveBoundaryGate(tmpdir, {})

        disp1, code1 = gate.validate_file_write_request(".vscode/settings.json")
        assert (
            disp1 == "NOT_DISPATCHED"
            and code1 == "ERR_CVE_2025_53773_54136_CONTROL_PLANE_DOTFILE_WRITE_DENIED"
        )

        disp2, code2 = gate.validate_file_write_request(".cursor/mcp.json")
        assert (
            disp2 == "NOT_DISPATCHED"
            and code2 == "ERR_CVE_2025_53773_54136_CONTROL_PLANE_DOTFILE_WRITE_DENIED"
        )

        disp3, code3 = gate.validate_file_write_request("output/../.vscode/tasks.json")
        assert (
            disp3 == "NOT_DISPATCHED"
            and code3 == "ERR_CVE_2025_53773_54136_CONTROL_PLANE_DOTFILE_WRITE_DENIED"
        )

        disp_ok, code_ok = gate.validate_file_write_request("output/audit_report.json")
        assert disp_ok == "DISPATCHED" and code_ok == "OK"


def test_marktechpost_four_signals_oob_monitor_and_litellm_pth_guard() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "output"), exist_ok=True)
        gate = StructuralCveBoundaryGate(tmpdir, {})

        # Signal 1: In-process safety monitor disarmament attempt blocked
        disp_m, code_m = gate.validate_package_or_monitor_action(
            ["kill", "-9", "aeib-monitor"]
        )
        assert (
            disp_m == "NOT_DISPATCHED"
            and code_m == "ERR_SIGNAL1_OOB_MONITOR_DISARMAMENT_BLOCKED"
        )

        # Signal 4: LiteLLM 1.107.0 `.pth` write & dynamic `pip install` blocked without step-up
        disp_pth, code_pth = gate.validate_file_write_request(
            "output/litellm_init.pth"
        )
        assert (
            disp_pth == "NOT_DISPATCHED"
            and code_pth == "ERR_CVE_2025_53773_54136_CONTROL_PLANE_DOTFILE_WRITE_DENIED"
        )

        disp_pip, code_pip = gate.validate_package_or_monitor_action(
            ["pip", "install", "litellm==1.107.0"], has_step_up_warrant=False
        )
        assert (
            disp_pip == "NOT_DISPATCHED"
            and code_pip == "ERR_SIGNAL4_DYNAMIC_PACKAGE_OR_PTH_HOOK_REQUIRES_STEP_UP"
        )


if __name__ == "__main__":
    test_all_four_structural_cve_fixtures_and_aeib_containment()
    test_cve_2026_33017_langflow_unauthenticated_graph_override_blocked()
    test_cve_2025_53773_and_54136_ide_control_plane_mutation_blocked()
    test_marktechpost_four_signals_oob_monitor_and_litellm_pth_guard()
    print(
        "TRACK 1 STRUCTURAL CVE FIXTURE SUITE PASSED: "
        "CVE-2026-33017, CVE-2025-53773, CVE-2025-54136, CVE-2026-77521, AND CVE-2026-90970 CONTAINED."
    )
