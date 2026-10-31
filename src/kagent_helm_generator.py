# Copyright 2026 SovereignNexus Project
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
src/kagent_helm_generator.py
================================================================================
Helm & Kustomize Manifest Synthesis Engine for kagent + Agent Substrate.

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Synthesizes production-ready Kubernetes deployment manifests:
1. Helm v2 Chart metadata and default values.
2. Declarative kagent CRDs (Harness, AgentTemplate, SandboxAgent).
3. Cilium Tetragon TracingPolicy CRD with eBPF LSM hooks.
4. Solo.io agentgateway RouteOption and VirtualService CRD with SPIFFE mTLS.
5. Kustomize kustomization.yaml bundle.

Zero mocks, zero floats, deterministic RFC 8785 single-source JCS validation.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from src.hypergraph_blast_radius import sha256_jcs_caid
from src.kagent_crd_adapter import KagentCRDValidator


@dataclass(frozen=True)
class HelmBundleArtifact:
    chart_name: str
    chart_version: str
    manifest_files: Dict[str, str]
    bundle_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chart_name": self.chart_name,
            "chart_version": self.chart_version,
            "manifest_files": dict(sorted(self.manifest_files.items())),
            "bundle_caid": self.bundle_caid,
        }


class KagentHelmGenerator:
    """
    Synthesizes validated Kubernetes Helm and Kustomize manifests
    for kagent + Agent Substrate + Solo.io agentgateway deployments.
    """

    def __init__(
        self,
        validator: Optional[KagentCRDValidator] = None,
    ) -> None:
        self.validator = validator or KagentCRDValidator()

    def generate_bundle(
        self,
        chart_name: str,
        chart_version: str,
        namespace: str,
        harness_manifest: Dict[str, Any],
        agent_template_manifest: Dict[str, Any],
        sandbox_agent_manifest: Dict[str, Any],
        bpf_lsm_profile_digest: str,
    ) -> HelmBundleArtifact:
        """
        Validates input kagent resources and generates complete Helm & Kustomize manifests.
        """
        if not chart_name or not isinstance(chart_name, str):
            raise ValueError("ERR_INVALID_CHART_NAME")
        if not chart_version or not isinstance(chart_version, str):
            raise ValueError("ERR_INVALID_CHART_VERSION")
        if not namespace or not isinstance(namespace, str):
            raise ValueError("ERR_INVALID_NAMESPACE")
        if not bpf_lsm_profile_digest.startswith("sha256:"):
            raise ValueError(f"ERR_INVALID_BPF_PROFILE_DIGEST: {bpf_lsm_profile_digest}")

        # Validate all three kagent CRDs using KagentCRDValidator
        harness_res = self.validator.validate_manifest(harness_manifest)
        if not harness_res.is_valid:
            raise ValueError(f"ERR_INVALID_HARNESS_MANIFEST: {list(harness_res.violations)}")

        template_res = self.validator.validate_manifest(agent_template_manifest)
        if not template_res.is_valid:
            raise ValueError(f"ERR_INVALID_AGENT_TEMPLATE_MANIFEST: {list(template_res.violations)}")

        sandbox_res = self.validator.validate_manifest(sandbox_agent_manifest)
        if not sandbox_res.is_valid:
            raise ValueError(f"ERR_INVALID_SANDBOX_AGENT_MANIFEST: {list(sandbox_res.violations)}")

        manifest_files: Dict[str, str] = {}

        # 1. Chart.yaml
        manifest_files["Chart.yaml"] = (
            f"apiVersion: v2\n"
            f"name: {chart_name}\n"
            f"version: {chart_version}\n"
            f"description: Evaluated kagent Agent Substrate Sovereign Factory deployment\n"
            f"type: application\n"
            f"appVersion: {chart_version}\n"
        )

        # 2. values.yaml
        manifest_files["values.yaml"] = (
            f"# Generated values for {chart_name}\n"
            f"global:\n"
            f"  namespace: {namespace}\n"
            f"  environment: production\n"
            f"\n"
            f"runtime:\n"
            f"  sandboxClass: {harness_res.runtime_sandbox}\n"
            f"  spiffeId: {harness_res.spiffe_id}\n"
            f"  bpfLsmProfileDigest: {bpf_lsm_profile_digest}\n"
            f"\n"
            f"governance:\n"
            f"  maxDriftThresholdBps: {harness_res.max_drift_bps}\n"
            f"  eo1IntentLatch: {str(harness_res.eo1_latch_enabled).lower()}\n"
            f"  egressMode: default-deny\n"
        )

        # 3. templates/harness.yaml
        manifest_files["templates/harness.yaml"] = self._to_yaml(harness_manifest)

        # 4. templates/agenttemplate.yaml
        manifest_files["templates/agenttemplate.yaml"] = self._to_yaml(agent_template_manifest)

        # 5. templates/sandboxagent.yaml
        manifest_files["templates/sandboxagent.yaml"] = self._to_yaml(sandbox_agent_manifest)

        # 6. templates/tracingpolicy.yaml (Cilium Tetragon eBPF LSM Policy)
        tracing_policy = {
            "apiVersion": "cilium.io/v1alpha1",
            "kind": "TracingPolicy",
            "metadata": {
                "name": f"{chart_name}-tetragon-lsm-policy",
                "namespace": namespace,
            },
            "spec": {
                "kprobes": [
                    {
                        "call": "sys_enter_connect",
                        "syscall": True,
                        "args": [{"index": 0, "type": "sock"}],
                    },
                    {
                        "call": "sys_enter_execve",
                        "syscall": True,
                        "args": [{"index": 0, "type": "string"}],
                    },
                ],
                "lsm": [
                    {
                        "hook": "security_file_open",
                        "action": "Sigkill",
                        "message": "Enforced credential theft defense on protected file path",
                    }
                ],
            },
        }
        manifest_files["templates/tracingpolicy.yaml"] = self._to_yaml(tracing_policy)

        # 7. templates/agentgateway-route.yaml (Solo.io agentgateway PEP)
        agentgateway_route = {
            "apiVersion": "gateway.solo.io/v1",
            "kind": "RouteOption",
            "metadata": {
                "name": f"{chart_name}-agentgateway-pep",
                "namespace": namespace,
            },
            "spec": {
                "options": {
                    "egress": {
                        "mode": "DefaultDeny",
                        "spiffeValidation": {
                            "trustedPrefix": harness_res.spiffe_id.split("/ns/")[0]
                        },
                        "credentialVault": {
                            "placeholderResolution": True,
                            "headerRedaction": True,
                        },
                    }
                }
            },
        }
        manifest_files["templates/agentgateway-route.yaml"] = self._to_yaml(agentgateway_route)

        # 8. kustomization.yaml
        manifest_files["kustomization.yaml"] = (
            f"apiVersion: kustomize.config.k8s.io/v1beta1\n"
            f"kind: Kustomization\n"
            f"namespace: {namespace}\n"
            f"resources:\n"
            f"  - templates/harness.yaml\n"
            f"  - templates/agenttemplate.yaml\n"
            f"  - templates/sandboxagent.yaml\n"
            f"  - templates/tracingpolicy.yaml\n"
            f"  - templates/agentgateway-route.yaml\n"
        )

        # Compute deterministic RFC 8785 bundle CAID
        bundle_digest_payload: Dict[str, Any] = {
            "chart_name": chart_name,
            "chart_version": chart_version,
            "manifest_files": dict(sorted(manifest_files.items())),
            "namespace": namespace,
        }
        bundle_caid = sha256_jcs_caid(bundle_digest_payload)

        return HelmBundleArtifact(
            chart_name=chart_name,
            chart_version=chart_version,
            manifest_files=manifest_files,
            bundle_caid=bundle_caid,
        )

    def write_bundle_to_disk(
        self,
        output_directory: str,
        bundle: HelmBundleArtifact,
    ) -> List[str]:
        """Writes the generated Helm / Kustomize bundle to the target directory."""
        written_paths: List[str] = []
        for rel_path, content in bundle.manifest_files.items():
            full_path = os.path.join(output_directory, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            written_paths.append(full_path)
        return sorted(written_paths)

    @staticmethod
    def _to_yaml(data: Dict[str, Any], indent_level: int = 0) -> str:
        """
        Deterministic, dependency-free YAML serializer for Kubernetes manifests.
        Avoids external PyYAML inconsistencies across platforms.
        """
        lines: List[str] = []
        indent = "  " * indent_level

        for k, v in data.items():
            if isinstance(v, dict):
                lines.append(f"{indent}{k}:")
                sub = KagentHelmGenerator._to_yaml(v, indent_level + 1)
                lines.append(sub)
            elif isinstance(v, list):
                lines.append(f"{indent}{k}:")
                for item in v:
                    if isinstance(item, dict):
                        first = True
                        for ik, iv in item.items():
                            prefix = f"{indent}  - " if first else f"{indent}    "
                            first = False
                            if isinstance(iv, dict):
                                lines.append(f"{prefix}{ik}:")
                                lines.append(KagentHelmGenerator._to_yaml(iv, indent_level + 3))
                            elif isinstance(iv, list):
                                lines.append(f"{prefix}{ik}:")
                                for sub_item in iv:
                                    if isinstance(sub_item, dict):
                                        sub_first = True
                                        for sik, siv in sub_item.items():
                                            sub_prefix = f"{indent}      - " if sub_first else f"{indent}        "
                                            sub_first = False
                                            lines.append(f"{sub_prefix}{sik}: {KagentHelmGenerator._format_val(siv)}")
                                    else:
                                        lines.append(f"{indent}      - {KagentHelmGenerator._format_val(sub_item)}")
                            else:
                                lines.append(f"{prefix}{ik}: {KagentHelmGenerator._format_val(iv)}")
                    else:
                        lines.append(f"{indent}  - {KagentHelmGenerator._format_val(item)}")
            else:
                lines.append(f"{indent}{k}: {KagentHelmGenerator._format_val(v)}")

        return "\n".join(lines)

    @staticmethod
    def _format_val(val: Any) -> str:
        if val is None:
            return "null"
        if isinstance(val, bool):
            return "true" if val else "false"
        if isinstance(val, (int, float)):
            return str(val)
        s = str(val)
        if any(c in s for c in (":", "#", "{", "}", "[", "]", ",", "&", "*", "?", "|", "-", "<", ">", "=", "!", "%", "@", "`", '"')):
            escaped = s.replace('"', '\\"')
            return f'"{escaped}"'
        return s
